# Database design

- `vehicles`: normalized unique vehicle registration and optional attributes.
- `import_batches`: uploaded source file, reporting month, counts and lifecycle status.
- `daily_statuses`: one vehicle/date record; stores imported status and optional corrected status separately. `effective_status` is derived by service logic (corrected if present, otherwise imported).
- `audit_logs`: immutable event trail for imports and corrections, including actor, reason and before/after values.

The schema deliberately keeps workbook-specific optional values nullable. Missing daily status is `NULL`, never implicitly idle. Re-imports update imported source values but do not remove an existing correction. The current single-admin authentication is a bootstrap mechanism; user/role tables and full RBAC should be added before multi-user production.
