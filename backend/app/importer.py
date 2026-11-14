from datetime import date, datetime
from pathlib import Path
import re
import pandas as pd

VEHICLE_HINTS = ("vehicle", "registration", "reg no", "vehicle no", "truck no", "car no")
DATE_HINTS = ("date", "day")
STATUS_HINTS = ("status", "vehicle status")

def _norm(v):
    return re.sub(r"\s+", " ", str(v)).strip() if v is not None else ""

def _parse_date(value):
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.date() if hasattr(value, "date") else value
    try:
        return pd.to_datetime(value, dayfirst=True, errors="raise").date()
    except Exception:
        return None

def inspect_workbook(path: str | Path):
    xls = pd.ExcelFile(path)
    rows, errors, sheets = [], [], []
    for sheet in xls.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet, header=0)
        sheets.append({"name": sheet, "rows": int(len(df)), "columns": [str(c) for c in df.columns]})
        if df.empty: continue
        cols = list(df.columns)
        vehicle_col = next((c for c in cols if any(h in _norm(c).lower() for h in VEHICLE_HINTS)), None)
        date_col = next((c for c in cols if _norm(c).lower() in ("date", "status date", "report date")), None)
        status_col = next((c for c in cols if any(h in _norm(c).lower() for h in STATUS_HINTS)), None)
        if vehicle_col is None:
            errors.append({"sheet": sheet, "row": None, "message": "Could not identify a vehicle-number column; this sheet was not imported."})
            continue
        # Normalized table: Vehicle + Date + Status columns.
        if date_col is not None and status_col is not None:
            for idx, rec in df.iterrows():
                vehicle = _norm(rec.get(vehicle_col))
                d = _parse_date(rec.get(date_col))
                status = _norm(rec.get(status_col)) or None
                if not vehicle or vehicle.lower() == "nan":
                    errors.append({"sheet": sheet, "row": int(idx)+2, "message": "Missing vehicle number"}); continue
                if d is None:
                    errors.append({"sheet": sheet, "row": int(idx)+2, "message": "Invalid or missing date"}); continue
                rows.append({"vehicle_number": vehicle.upper(), "status_date": d.isoformat(), "status": status, "sheet": sheet, "row": int(idx)+2})
        else:
            # Matrix: each date-like column is a daily status column.
            date_cols = [(c, _parse_date(c)) for c in cols]
            date_cols = [(c, d) for c, d in date_cols if d is not None]
            if not date_cols:
                errors.append({"sheet": sheet, "row": None, "message": "No date columns found; expected a normalized Date/Status table or vehicle-by-date matrix."})
                continue
            for idx, rec in df.iterrows():
                vehicle = _norm(rec.get(vehicle_col))
                if not vehicle or vehicle.lower() == "nan": continue
                for c, d in date_cols:
                    raw = rec.get(c)
                    status = _norm(raw)
                    if not status or status.lower() == "nan": status = None
                    rows.append({"vehicle_number": vehicle.upper(), "status_date": d.isoformat(), "status": status, "sheet": sheet, "row": int(idx)+2})
    seen, deduped, duplicates = set(), [], 0
    for r in rows:
        key=(r["vehicle_number"], r["status_date"])
        if key in seen:
            duplicates += 1
            errors.append({"sheet": r["sheet"], "row": r["row"], "message": "Duplicate vehicle/date record; first occurrence retained"})
            continue
        seen.add(key); deduped.append(r)
    return {"sheets": sheets, "records": deduped, "errors": errors, "total_records": len(rows), "valid_records": len(deduped), "duplicate_records": duplicates}
