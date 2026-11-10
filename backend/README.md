# CampusFix Backend

Smart Campus Maintenance and Infrastructure Management System.

## Tech Stack
- Python
- FastAPI
- Uvicorn

## Run Locally
1. Start PostgreSQL from the repository root: `docker compose up -d db`.
2. Copy `.env.example` to `.env` in the `backend/` directory and set
   `DATABASE_URL`, `JWT_SECRET_KEY`, `ADMIN_USERNAME`, and
   `ADMIN_PASSWORD`. Keep the `.env` file private.
3. Create and activate a virtual environment, then install dependencies:
   `python -m pip install -r requirements.txt`.
4. Apply additive database migrations from the `backend/` directory:
   `python -m app.migrate`.
5. From the `backend/` directory, start the server:
   `python -m uvicorn app.main:app --reload`.

API Documentation: http://127.0.0.1:8000/docs

## Import Admission Records
From the `backend/` directory, validate the PDF without writing to the database:

```powershell
python import_admission_data.py "C:\path\to\Admission Portal 2026 (1).pdf" --dry-run
```

Import the validated admission records into the existing PostgreSQL database:

```powershell
python import_admission_data.py "C:\path\to\Admission Portal 2026 (1).pdf"
```

The importer is safe to rerun: existing USNs are left unchanged. Only USN,
student name, and department are populated; year, semester, and section remain
unset because they are not established by the admission PDF.

## Maintenance features
- Student complaints can be categorized with Gemini (`GEMINI_API_KEY`); if the
  key is absent or Gemini is unavailable, the API uses the `Other`/`medium`
  fallback. Complaint text and an optional image are sent to Gemini when
  categorization is requested.
- Photo uploads are stored under `UPLOAD_DIR` (default: `backend/uploads/`).
  Keep this directory on persistent storage and out of version control.
- SLA targets are defined in `app/sla.py`. Background processing checks every
  15 minutes, escalates at the SLA deadline, then at 24 and 72 hours overdue,
  and auto-closes resolved complaints after 48 hours without student feedback.
  HOD/principal escalations are recorded and shown in the admin inbox.
- Admin credentials are configured only through `ADMIN_USERNAME` and
  `ADMIN_PASSWORD`. Admins create staff login accounts via the protected
  `/admin/staff/accounts` endpoint.
- JWTs are signed with `JWT_SECRET_KEY`; do not commit real credentials.

### Added API endpoints
- `POST /auth/login` — admin and maintenance-staff login.
- `POST /complaints/analyze` — Gemini suggestion (or fallback).
- `POST /complaints/with-photo` — submit with a before photo.
- `POST /students/{student_id}/complaints/{complaint_id}/verification` — confirm
  or reopen a proof-of-fix request.
- `GET /notifications` and `PATCH /notifications/{id}/read` — in-app notices.
- `GET /media/{filename}` — role/ownership-checked complaint photo.
- `GET /locations`, `GET/POST /admin/locations` — QR location records.
- `POST /admin/staff/accounts` — create a password-enabled staff account.
- `GET /sla-config` — current category SLA hours.
- `GET /admin/departments/counts` — department student counts.
- `GET /admin/complaints/{complaint_id}/escalations` — escalation history.

Admin complaint and staff management endpoints now require an admin bearer
token; staff task endpoints require the assigned staff member's token, and
student complaint endpoints require the complaint owner's token.
