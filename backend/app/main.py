import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.admin import router as admin_router
from app.ai import categorize_complaint
from app.auth import hash_password, verify_password
from app.database import SessionLocal, get_db
from app.notifications import add_notification
from app.security import (
    Principal,
    issue_access_token,
    require_roles,
    verify_admin_credentials,
)
from app.sla import SLA_HOURS, deadline_for, run_sla_cycle
from app.uploads import UPLOAD_DIR, delete_image, read_image, save_image

logger = logging.getLogger(__name__)
SLA_SCAN_INTERVAL_SECONDS = 15 * 60
VERIFICATION_WINDOW = timedelta(hours=48)
PRIORITY_ORDER = ("low", "medium", "high", "critical")


def _run_sla_cycle() -> None:
    with SessionLocal() as db:
        run_sla_cycle(db)


async def _sla_worker() -> None:
    while True:
        await asyncio.sleep(SLA_SCAN_INTERVAL_SECONDS)
        try:
            await asyncio.to_thread(_run_sla_cycle)
        except Exception:
            logger.exception("CampusFix SLA cycle failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(_sla_worker())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="CampusFix API",
    description="Smart Campus Maintenance Management System",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_methods=["GET", "POST", "PATCH", "PUT", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(admin_router)


@app.get("/")
def home():
    return {"message": "Welcome to CampusFix API", "status": "Running"}


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "healthy", "application": "CampusFix"}


@app.post("/students/register", response_model=schemas.StudentResponse)
def register_student(student: schemas.StudentRegister, db: Session = Depends(get_db)):
    admission = (
        db.query(models.Student)
        .filter(models.Student.usn == student.usn)
        .with_for_update()
        .first()
    )
    if not admission:
        raise HTTPException(
            status_code=400,
            detail="USN was not found in the admission records.",
        )
    if admission.password_hash:
        raise HTTPException(
            status_code=400,
            detail="An account already exists for this USN.",
        )

    admission.password_hash = hash_password(student.password)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="An account already exists for this USN.",
        ) from error
    db.refresh(admission)
    return admission


@app.post("/students/login")
def login_student(credentials: schemas.StudentLogin, db: Session = Depends(get_db)):
    student = (
        db.query(models.Student)
        .filter(models.Student.usn == credentials.usn)
        .first()
    )
    if (
        not student
        or not student.password_hash
        or not verify_password(credentials.password, student.password_hash)
    ):
        raise HTTPException(status_code=401, detail="Invalid USN or password")

    return {
        "message": "Login successful",
        "access_token": issue_access_token("student", student.id, student.usn),
        "token_type": "bearer",
        "student": {"id": student.id, "name": student.name, "usn": student.usn},
    }


@app.post("/auth/login")
def login_staff_or_admin(credentials: schemas.LoginRequest, db: Session = Depends(get_db)):
    if credentials.role == "admin":
        if not os.getenv("ADMIN_USERNAME") or not os.getenv("ADMIN_PASSWORD"):
            raise HTTPException(status_code=503, detail="Admin login is not configured")
        if not verify_admin_credentials(credentials.username, credentials.password):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        return {
            "access_token": issue_access_token("admin", None, credentials.username),
            "token_type": "bearer",
            "user": {"role": "admin", "name": credentials.username},
        }

    staff = (
        db.query(models.Staff)
        .filter(models.Staff.employee_id == credentials.username)
        .first()
    )
    if (
        not staff
        or not staff.password_hash
        or not verify_password(credentials.password, staff.password_hash)
    ):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return {
        "access_token": issue_access_token("staff", staff.id, staff.employee_id),
        "token_type": "bearer",
        "user": {"id": staff.id, "role": "staff", "name": staff.name},
    }


@app.post("/complaints/analyze")
async def analyze_complaint(
    title: str = Form(min_length=1, max_length=200),
    description: str = Form(min_length=1, max_length=10000),
    photo: UploadFile | None = File(default=None),
    _: Principal = Depends(require_roles("student")),
):
    image, mime_type = await read_image(photo)
    return await asyncio.to_thread(
        categorize_complaint,
        title,
        description,
        image,
        mime_type,
    )


def _create_complaint(
    complaint: schemas.ComplaintCreate,
    student: Principal,
    db: Session,
    photo: tuple[bytes, str] | None = None,
) -> models.Complaint:
    now = datetime.now(timezone.utc)
    if not complaint.suggested_team or not complaint.summary:
        image, mime_type = photo if photo else (None, None)
        suggestion = categorize_complaint(
            complaint.title,
            complaint.description,
            image,
            mime_type,
        )
        complaint = complaint.model_copy(update={
            "category": complaint.category or suggestion["category"],
            "priority": complaint.priority or suggestion["priority"],
            "suggested_team": complaint.suggested_team or suggestion["suggested_team"],
            "summary": complaint.summary or suggestion["summary"],
        })
    category = complaint.category or "Other"
    priority = complaint.priority or "medium"
    photo_path = save_image(*photo) if photo else None
    complaint_data = complaint.model_dump()
    complaint_data.update(category=category, priority=priority)
    row = models.Complaint(
        **complaint_data,
        student_id=student.user_id,
        status="Reported",
        created_at=now,
        due_at=deadline_for(category, now),
        before_photo_path=photo_path,
    )
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    except Exception:
        db.rollback()
        delete_image(photo_path)
        raise


@app.post("/complaints", response_model=schemas.ComplaintResponse)
def create_complaint(
    complaint: schemas.ComplaintCreate,
    student_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles("student")),
):
    if student_id is not None and student_id != principal.user_id:
        raise HTTPException(status_code=403, detail="Cannot submit for another student")
    return _create_complaint(complaint, principal, db)


@app.post("/complaints/with-photo", response_model=schemas.ComplaintResponse)
async def create_complaint_with_photo(
    title: str = Form(min_length=1, max_length=200),
    description: str = Form(min_length=1, max_length=10000),
    location: str = Form(min_length=1, max_length=200),
    category: str | None = Form(default=None),
    priority: str | None = Form(default=None),
    suggested_team: str | None = Form(default=None),
    summary: str | None = Form(default=None),
    photo: UploadFile | None = File(default=None),
    student_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles("student")),
):
    if student_id is not None and student_id != principal.user_id:
        raise HTTPException(status_code=403, detail="Cannot submit for another student")
    complaint = schemas.ComplaintCreate(
        title=title,
        description=description,
        location=location,
        category=category,
        priority=priority,
        suggested_team=suggested_team,
        summary=summary,
    )
    image, mime_type = await read_image(photo)
    photo_data = (image, mime_type) if image is not None and mime_type else None
    if not complaint.suggested_team or not complaint.summary:
        suggestion = await asyncio.to_thread(
            categorize_complaint,
            complaint.title,
            complaint.description,
            image,
            mime_type,
        )
        complaint = complaint.model_copy(update={
            "category": complaint.category or suggestion["category"],
            "priority": complaint.priority or suggestion["priority"],
            "suggested_team": complaint.suggested_team or suggestion["suggested_team"],
            "summary": complaint.summary or suggestion["summary"],
        })
    return _create_complaint(complaint, principal, db, photo_data)


@app.get("/complaints")
def get_complaints(
    db: Session = Depends(get_db),
    _: Principal = Depends(require_roles("admin")),
):
    complaints = db.query(models.Complaint).order_by(models.Complaint.created_at.desc()).all()
    return {"total": len(complaints), "complaints": complaints}


@app.get("/students/{student_id}/complaints")
def get_student_complaints(
    student_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles("student", "admin")),
):
    if principal.role == "student" and student_id != principal.user_id:
        raise HTTPException(status_code=403, detail="Cannot view another student's complaints")
    complaints = (
        db.query(models.Complaint)
        .filter(models.Complaint.student_id == student_id)
        .order_by(models.Complaint.created_at.desc())
        .all()
    )
    return {"total": len(complaints), "complaints": complaints}


@app.get("/staff/{staff_id}/complaints")
def get_staff_tasks(
    staff_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles("staff", "admin")),
):
    if principal.role == "staff" and staff_id != principal.user_id:
        raise HTTPException(status_code=403, detail="Cannot view another staff member's tasks")
    complaints = (
        db.query(models.Complaint)
        .filter(models.Complaint.staff_id == staff_id)
        .order_by(models.Complaint.due_at.asc())
        .all()
    )
    return {"total": len(complaints), "tasks": complaints}


@app.patch("/staff/{staff_id}/complaints/{complaint_id}/status")
async def staff_update_status(
    staff_id: int,
    complaint_id: int,
    status: str = Query(),
    after_photo: UploadFile | None = File(default=None),
    note: str | None = Form(default=None, max_length=2000),
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles("staff")),
):
    if staff_id != principal.user_id:
        raise HTTPException(status_code=403, detail="Cannot update another staff member's task")
    if status not in ("In Progress", "Resolved"):
        raise HTTPException(status_code=400, detail="Staff can set status to In Progress or Resolved")
    complaint = (
        db.query(models.Complaint)
        .filter(
            models.Complaint.id == complaint_id,
            models.Complaint.staff_id == staff_id,
        )
        .with_for_update()
        .first()
    )
    if complaint is None:
        raise HTTPException(status_code=404, detail="Assigned complaint not found")
    if status == "In Progress" and complaint.status not in ("Assigned", "In Progress"):
        raise HTTPException(
            status_code=409,
            detail="Only assigned tasks can be started or continued",
        )
    if status == "Resolved" and complaint.status not in ("Assigned", "In Progress"):
        raise HTTPException(
            status_code=409,
            detail="Only assigned tasks in progress can be resolved",
        )

    photo_data = await read_image(after_photo)
    if status == "Resolved" and (photo_data[0] is None or not note or not note.strip()):
        raise HTTPException(
            status_code=400,
            detail="An after photo and resolution note are required to resolve a task",
        )

    new_photo_path = save_image(*photo_data) if photo_data[0] and photo_data[1] else None
    now = datetime.now(timezone.utc)
    complaint.status = status
    if status == "Resolved":
        complaint.after_photo_path = new_photo_path
        complaint.resolution_note = note.strip()
        complaint.resolved_at = now
        complaint.verification_deadline = now + VERIFICATION_WINDOW
        add_notification(
            db,
            target_role="student",
            target_user_id=complaint.student_id,
            complaint_id=complaint.id,
            kind="verification",
            message=f"Is complaint #{complaint.id} fixed? Confirm or reopen it within 48 hours.",
        )
    else:
        complaint.resolved_at = None
        complaint.verification_deadline = None
    try:
        db.commit()
    except Exception:
        db.rollback()
        delete_image(new_photo_path)
        raise
    db.refresh(complaint)
    return {"message": "Task status updated", "complaint_id": complaint.id, "status": complaint.status}


@app.post("/students/{student_id}/complaints/{complaint_id}/verification")
def verify_resolution(
    student_id: int,
    complaint_id: int,
    request: schemas.VerificationRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles("student")),
):
    if principal.user_id != student_id:
        raise HTTPException(status_code=403, detail="Cannot verify another student's complaint")
    complaint = (
        db.query(models.Complaint)
        .filter(
            models.Complaint.id == complaint_id,
            models.Complaint.student_id == student_id,
            models.Complaint.status == "Resolved",
        )
        .with_for_update()
        .first()
    )
    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint awaiting verification not found")
    now = datetime.now(timezone.utc)
    verification_deadline = complaint.verification_deadline
    if verification_deadline and verification_deadline.tzinfo is None:
        verification_deadline = verification_deadline.replace(tzinfo=timezone.utc)
    if verification_deadline and verification_deadline <= now:
        complaint.status = "Closed"
        complaint.closed_at = now
    elif request.action == "confirm":
        complaint.status = "Closed"
        complaint.closed_at = now
    else:
        complaint.status = "In Progress"
        complaint.resolved_at = None
        complaint.verification_deadline = None
        complaint.closed_at = None
        current_priority = complaint.priority.lower()
        if current_priority not in PRIORITY_ORDER:
            raise HTTPException(
                status_code=409,
                detail="Complaint priority cannot be escalated automatically",
            )
        complaint.priority = PRIORITY_ORDER[
            min(PRIORITY_ORDER.index(current_priority) + 1, len(PRIORITY_ORDER) - 1)
        ]
    db.commit()
    db.refresh(complaint)
    return {"complaint_id": complaint.id, "status": complaint.status, "priority": complaint.priority}


@app.get("/notifications", response_model=list[schemas.NotificationResponse])
def get_notifications(
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles("student", "staff", "admin")),
):
    query = db.query(models.Notification)
    if principal.role == "admin":
        query = query.filter(models.Notification.target_role == "admin")
    else:
        query = query.filter(
            (models.Notification.target_role == principal.role)
            & (models.Notification.target_user_id == principal.user_id)
        )
    return query.order_by(models.Notification.created_at.desc()).limit(100).all()


@app.patch("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles("student", "staff", "admin")),
):
    query = db.query(models.Notification).filter(models.Notification.id == notification_id)
    if principal.role == "admin":
        query = query.filter(models.Notification.target_role == "admin")
    else:
        query = query.filter(
            models.Notification.target_role == principal.role,
            models.Notification.target_user_id == principal.user_id,
        )
    notification = query.first()
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.read = True
    db.commit()
    return {"id": notification.id, "read": True}


@app.get("/media/{filename}")
def get_complaint_photo(
    filename: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles("student", "staff", "admin")),
):
    path = (UPLOAD_DIR / filename).resolve()
    if path.parent != UPLOAD_DIR or not path.is_file():
        raise HTTPException(status_code=404, detail="Photo not found")
    query = db.query(models.Complaint).filter(
        (models.Complaint.before_photo_path == filename)
        | (models.Complaint.after_photo_path == filename)
    )
    if principal.role == "student":
        query = query.filter(models.Complaint.student_id == principal.user_id)
    elif principal.role == "staff":
        query = query.filter(models.Complaint.staff_id == principal.user_id)
    if query.first() is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    return FileResponse(path)


@app.get("/locations")
def list_locations(
    db: Session = Depends(get_db),
    _: Principal = Depends(require_roles("student", "admin")),
):
    return db.query(models.Location).order_by(models.Location.name).all()


@app.get("/sla-config")
def get_sla_config(_: Principal = Depends(require_roles("student", "staff", "admin"))):
    return {"hours_by_category": SLA_HOURS}
