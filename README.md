# Fleet Intelligence & Vehicle Utilization Platform

A full-stack starting implementation for monthly fleet-workbook ingestion, daily vehicle status monitoring, corrections with audit history, fleet analytics, exports, and a unified text/voice operations assistant.

## Stack
- Frontend: React + TypeScript + Vite
- Backend: Python 3.12 + FastAPI
- Database: PostgreSQL + SQLAlchemy
- Excel: Pandas + OpenPyXL
- Charts: Recharts
- Deployment: Docker Compose

## Quick start (Windows PowerShell + Docker Desktop)
1. Copy `.env.example` to `.env` and change `ADMIN_PASSWORD` and `ADMIN_TOKEN`.
2. Start Docker Desktop.
3. From this folder run:
   ```powershell
   Copy-Item .env.example .env
   notepad .env
   docker compose up --build
   ```
4. Open http://localhost:5173. Sign in with the `ADMIN_PASSWORD` from `.env`.
5. API docs: http://localhost:8000/docs

## Local development without Docker
Backend (Python 3.12 recommended):
```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:DATABASE_URL = "sqlite:///./fleet_local.db"
uvicorn app.main:app --reload
```
Frontend, in another terminal:
```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```
Set `VITE_API_BASE` only if the backend is not available through Vite's `/api` proxy.

## Workbook format and import behavior
The importer attempts to recognize a vehicle-by-date matrix (vehicle registration column plus date columns containing status values) and a normalized table (vehicle, date, status columns). Since the real monthly workbook was not available in this build environment, validate the mapping against your actual workbook before operational use. The preview reports unrecognized sheets/rows instead of silently treating them as valid.

Upload flow: sign in → Data Import → select workbook → Preview → Confirm Import. Re-imports update imported source values while retaining manual corrections; each import batch and each correction is audited. A missing cell is stored as missing, not as an idle status.

## AI and voice
The Fleet Copilot works without an LLM key using a deterministic fallback for basic fleet questions. For generative answers, set `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL` in `.env` and restart the backend. The browser voice interface uses the Web Speech API (`SpeechRecognition` where supported and `speechSynthesis` for spoken replies); browser/device support and microphone permission are required. Voice and LLM provider usage may incur separate charges.

## Important production checklist
- Replace development secrets and configure HTTPS, backups, monitoring and restricted CORS.
- Add a proper identity provider, password reset, rate limiting and role-based permissions before multi-user production.
- Review workbook mappings and operational definitions (eligible days, utilization, status groups, revenue source) with the business owner.
- Configure a managed PostgreSQL database and durable private object storage for uploaded workbooks.
- Run tests and validate imports against representative real monthly workbooks before relying on reports.

## Current scope
This repository is an executable MVP foundation, not a certified production deployment. The project includes working core flows and explicit integration points; business-specific workbook mapping and live LLM credentials still need validation/configuration.
