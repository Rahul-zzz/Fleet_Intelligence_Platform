# Project progress

## Included in this delivery
- FastAPI application, SQLAlchemy persistence, PostgreSQL Docker service, SQLite local fallback.
- Admin password login using a configured bearer token.
- Workbook upload, preview, confirmation, import batch history and validation feedback.
- Daily status records with imported/corrected/effective values and correction audit trail.
- Fleet summary, vehicle listing/history, exception listing and Excel/CSV/PDF exports.
- Unified text/voice Copilot interface; optional OpenAI-compatible LLM configuration and browser speech APIs.
- React dashboard, status matrix, imports, corrections, reports, dark/light theme.

## Not yet business-validated
- Exact source workbook sheet/column mapping: actual reference workbook was not mounted during generation.
- Status taxonomy grouping and utilization denominator.
- Revenue and ERP/GPS metric source definitions.
- Production authentication, cloud deployment and voice-provider reliability.

## Verification
Run backend tests with `cd backend; py -3.12 -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements-dev.txt; pytest -v`.
Run frontend checks with `cd frontend; npm.cmd install; npm.cmd test; npm.cmd run typecheck; npm.cmd run build`.
Run Docker checks with `docker compose up --build`.
Do not mark any of these checks passed until they have actually been run in the target environment.
