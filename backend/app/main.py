from datetime import datetime, date
from pathlib import Path
import uuid, json, io, csv
import httpx
import pandas as pd
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .config import APP_ENV, APP_VERSION, UPLOAD_DIR, MAX_UPLOAD_MB, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from .database import Base, engine, get_db
from .models import Vehicle, ImportBatch, DailyStatus, AuditLog
from .schemas import LoginRequest, LoginResponse, CorrectionRequest, ChatRequest
from .security import require_admin
from .importer import inspect_workbook

Base.metadata.create_all(bind=engine)
app=FastAPI(title="Fleet Intelligence API", version=APP_VERSION)
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in __import__('os').getenv('CORS_ORIGINS','http://localhost:5173').split(',')], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
PENDING={}

@app.get('/api/health')
def health(): return {"status":"ok","version":APP_VERSION,"environment":APP_ENV}
@app.get('/api/health/db')
def health_db(db:Session=Depends(get_db)):
    try: db.execute(select(1)); return {"status":"ok","database":"reachable"}
    except Exception as e: raise HTTPException(503, detail="Database unavailable") from e
@app.post('/api/auth/login', response_model=LoginResponse)
def login(payload:LoginRequest):
    from .config import ADMIN_PASSWORD, ADMIN_TOKEN
    if payload.password != ADMIN_PASSWORD: raise HTTPException(401, detail="Invalid password")
    return {"token":ADMIN_TOKEN,"role":"admin"}

@app.get('/api/fleet/summary', dependencies=[Depends(require_admin)])
def fleet_summary(db:Session=Depends(get_db)):
    vehicles=db.scalar(select(func.count(Vehicle.id))) or 0
    total=db.scalar(select(func.count(DailyStatus.id))) or 0
    statuses=db.execute(select(DailyStatus.corrected_status, DailyStatus.imported_status)).all()
    counts={}
    for corrected, imported in statuses:
        s=corrected if corrected is not None else imported
        if s: counts[s]=counts.get(s,0)+1
    running=sum(v for k,v in counts.items() if 'running' in k.lower())
    return {"total_vehicles":vehicles,"status_records":total,"running_records":running,"status_distribution":counts,"utilization_pct":round(running/total*100,1) if total else 0}
@app.get('/api/vehicles', dependencies=[Depends(require_admin)])
def vehicles(q:str|None=None, db:Session=Depends(get_db)):
    stmt=select(Vehicle).order_by(Vehicle.vehicle_number)
    if q: stmt=stmt.where(Vehicle.vehicle_number.ilike(f"%{q}%"))
    return [{"vehicle_number":v.vehicle_number,"id":v.id} for v in db.scalars(stmt).all()]
@app.get('/api/status-matrix', dependencies=[Depends(require_admin)])
def status_matrix(start:date|None=None,end:date|None=None,db:Session=Depends(get_db)):
    stmt=select(DailyStatus,Vehicle.vehicle_number).join(Vehicle).order_by(Vehicle.vehicle_number,DailyStatus.status_date)
    if start: stmt=stmt.where(DailyStatus.status_date>=start)
    if end: stmt=stmt.where(DailyStatus.status_date<=end)
    out=[]
    for s,v in db.execute(stmt).all(): out.append({"vehicle_number":v,"date":s.status_date.isoformat(),"status":s.effective_status,"imported_status":s.imported_status,"corrected_status":s.corrected_status})
    return out
@app.get('/api/vehicles/{vehicle_number}', dependencies=[Depends(require_admin)])
def vehicle_profile(vehicle_number:str,db:Session=Depends(get_db)):
    v=db.scalar(select(Vehicle).where(Vehicle.vehicle_number==vehicle_number.upper()))
    if not v: raise HTTPException(404,"Vehicle not found")
    history=db.scalars(select(DailyStatus).where(DailyStatus.vehicle_id==v.id).order_by(DailyStatus.status_date)).all()
    return {"vehicle_number":v.vehicle_number,"history":[{"date":x.status_date.isoformat(),"status":x.effective_status,"imported_status":x.imported_status,"corrected_status":x.corrected_status} for x in history]}
@app.get('/api/exceptions', dependencies=[Depends(require_admin)])
def exceptions(min_idle_days:int=Query(3,ge=1),db:Session=Depends(get_db)):
    # Current latest status per vehicle; no data is not interpreted as idle.
    result=[]
    for v in db.scalars(select(Vehicle)).all():
        s=db.scalar(select(DailyStatus).where(DailyStatus.vehicle_id==v.id).order_by(DailyStatus.status_date.desc()).limit(1))
        if s and s.effective_status and any(w in s.effective_status.lower() for w in ['waiting','halting','maintenance','no driver','accident']):
            result.append({"vehicle_number":v.vehicle_number,"date":s.status_date.isoformat(),"status":s.effective_status,"severity":"review"})
    return result

@app.post('/api/imports/preview', dependencies=[Depends(require_admin)])
async def preview_import(file:UploadFile=File(...)):
    suffix=Path(file.filename or '').suffix.lower()
    if suffix not in ['.xlsx','.xls']: raise HTTPException(400,"Upload an .xlsx or .xls workbook")
    content=await file.read()
    if len(content)>MAX_UPLOAD_MB*1024*1024: raise HTTPException(413,"File exceeds upload limit")
    token=str(uuid.uuid4()); path=UPLOAD_DIR/f"{token}{suffix}"; path.write_bytes(content)
    try: parsed=inspect_workbook(path)
    except Exception as e:
        path.unlink(missing_ok=True); raise HTTPException(422,f"Workbook could not be parsed: {e}")
    PENDING[token]={"path":str(path),"filename":Path(file.filename or 'workbook').name,"parsed":parsed}
    return {"preview_id":token,"filename":Path(file.filename or 'workbook').name,"sheets":parsed['sheets'],"total_records":parsed['total_records'],"valid_records":parsed['valid_records'],"duplicate_records":parsed['duplicate_records'],"errors":parsed['errors'][:200],"can_import":bool(parsed['records'])}
@app.post('/api/imports/{preview_id}/confirm', dependencies=[Depends(require_admin)])
def confirm_import(preview_id:str,db:Session=Depends(get_db)):
    pending=PENDING.get(preview_id)
    if not pending: raise HTTPException(404,"Preview expired or not found; upload again")
    parsed=pending['parsed']; records=parsed['records']
    month=min((r['status_date'][:7] for r in records),default=None)
    batch=ImportBatch(filename=pending['filename'],reporting_month=month,status='processing',total_rows=parsed['total_records'],valid_rows=len(records),invalid_rows=len(parsed['errors']))
    db.add(batch); db.flush()
    inserted=updated=0
    try:
        for r in records:
            v=db.scalar(select(Vehicle).where(Vehicle.vehicle_number==r['vehicle_number']))
            if not v: v=Vehicle(vehicle_number=r['vehicle_number']); db.add(v); db.flush()
            d=date.fromisoformat(r['status_date'])
            s=db.scalar(select(DailyStatus).where(DailyStatus.vehicle_id==v.id,DailyStatus.status_date==d))
            if not s:
                s=DailyStatus(vehicle_id=v.id,status_date=d,imported_status=r['status'],import_batch_id=batch.id); db.add(s); inserted+=1
            else:
                s.imported_status=r['status']; s.import_batch_id=batch.id; updated+=1
        batch.status='completed'
        db.add(AuditLog(entity_type='import_batch',entity_id=str(batch.id),action='import_confirmed',reason=f"{inserted} inserted, {updated} source records updated",after_value=pending['filename']))
        db.commit()
    except Exception:
        db.rollback(); raise
    PENDING.pop(preview_id,None)
    Path(pending['path']).unlink(missing_ok=True)
    return {"batch_id":batch.id,"status":"completed","inserted":inserted,"updated":updated,"invalid":len(parsed['errors'])}
@app.get('/api/imports', dependencies=[Depends(require_admin)])
def import_history(db:Session=Depends(get_db)):
    return [{"id":b.id,"filename":b.filename,"reporting_month":b.reporting_month,"status":b.status,"total_rows":b.total_rows,"valid_rows":b.valid_rows,"invalid_rows":b.invalid_rows,"created_at":b.created_at.isoformat()} for b in db.scalars(select(ImportBatch).order_by(ImportBatch.created_at.desc())).all()]
@app.post('/api/corrections', dependencies=[Depends(require_admin)])
def correct_status(payload:CorrectionRequest,db:Session=Depends(get_db)):
    v=db.scalar(select(Vehicle).where(Vehicle.vehicle_number==payload.vehicle_number.upper()))
    if not v: raise HTTPException(404,"Vehicle not found")
    s=db.scalar(select(DailyStatus).where(DailyStatus.vehicle_id==v.id,DailyStatus.status_date==payload.status_date))
    if not s: s=DailyStatus(vehicle_id=v.id,status_date=payload.status_date,imported_status=None); db.add(s); db.flush()
    before=s.corrected_status if s.corrected_status is not None else s.imported_status
    s.corrected_status=payload.corrected_status.strip(); s.correction_reason=payload.reason; s.corrected_by='admin'; s.corrected_at=datetime.utcnow()
    db.add(AuditLog(entity_type='daily_status',entity_id=str(s.id),action='status_corrected',reason=payload.reason,before_value=before,after_value=s.corrected_status))
    db.commit(); return {"status":"saved","effective_status":s.effective_status}
@app.get('/api/audit', dependencies=[Depends(require_admin)])
def audit(db:Session=Depends(get_db)):
    return [{"id":a.id,"entity_type":a.entity_type,"entity_id":a.entity_id,"action":a.action,"actor":a.actor,"reason":a.reason,"before":a.before_value,"after":a.after_value,"created_at":a.created_at.isoformat()} for a in db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(500)).all()]

@app.get('/api/reports/export', dependencies=[Depends(require_admin)])
def export_report(format:str='xlsx',db:Session=Depends(get_db)):
    rows=db.execute(select(Vehicle.vehicle_number,DailyStatus.status_date,DailyStatus.imported_status,DailyStatus.corrected_status).join(DailyStatus)).all()
    data=[{"vehicle_number":v,"date":d.isoformat(),"imported_status":i,"corrected_status":c,"effective_status":c if c is not None else i} for v,d,i,c in rows]
    df=pd.DataFrame(data)
    if format=='csv':
        buf=io.StringIO(); df.to_csv(buf,index=False); return StreamingResponse(iter([buf.getvalue()]),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=fleet-report.csv'})
    if format=='xlsx':
        buf=io.BytesIO(); df.to_excel(buf,index=False); buf.seek(0); return StreamingResponse(buf,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':'attachment; filename=fleet-report.xlsx'})
    if format=='pdf':
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.platypus import SimpleDocTemplate,Table,TableStyle,Paragraph
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        buf=io.BytesIO(); doc=SimpleDocTemplate(buf,pagesize=landscape(A4)); table_data=[list(df.columns)]+df.fillna('').astype(str).values.tolist()
        t=Table(table_data,repeatRows=1); t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#24364b')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),.25,colors.grey),('FONTSIZE',(0,0),(-1,-1),7)])); doc.build([Paragraph('Fleet status report',getSampleStyleSheet()['Title']),t]); buf.seek(0)
        return StreamingResponse(buf,media_type='application/pdf',headers={'Content-Disposition':'attachment; filename=fleet-report.pdf'})
    raise HTTPException(400,"format must be csv, xlsx or pdf")

@app.post('/api/ai/chat', dependencies=[Depends(require_admin)])
async def chat(payload:ChatRequest,db:Session=Depends(get_db)):
    summary=f"Fleet vehicles: {db.scalar(select(func.count(Vehicle.id))) or 0}. Daily status records: {db.scalar(select(func.count(DailyStatus.id))) or 0}."
    # Ground simple queries in DB results; optional LLM receives only compact aggregate context.
    statuses=db.execute(select(DailyStatus.corrected_status,DailyStatus.imported_status)).all(); counts={}
    for c,i in statuses:
        s=c if c is not None else i
        if s: counts[s]=counts.get(s,0)+1
    context=summary+" Status counts: "+json.dumps(counts)
    answer="I can answer questions about the imported fleet data. "+context+" For vehicle-specific details, ask about a vehicle number."
    if LLM_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=35) as client:
                resp=await client.post(LLM_BASE_URL.rstrip('/')+'/chat/completions',headers={'Authorization':f'Bearer {LLM_API_KEY}'},json={'model':LLM_MODEL,'messages':[{'role':'system','content':'You are Fleet Copilot. Answer only from supplied fleet context. If the context does not contain the answer, say so. Do not invent operational facts. Context: '+context},*payload.history[-8:],{'role':'user','content':payload.message}]})
                resp.raise_for_status(); answer=resp.json()['choices'][0]['message']['content']
        except Exception as e: answer="The configured AI service could not be reached. Here is the available database summary instead: "+context
    return {"answer":answer,"mode":"llm" if LLM_API_KEY else "data-summary"}
