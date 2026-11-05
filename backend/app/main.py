
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import hash_password, verify_password
from app.database import get_db
from app import models, schemas
from app.admin import router as admin_router

app = FastAPI(
    title="CampusFix API",
    description="Smart Campus Maintenance Management System",
    version="1.0.0"
)

app.include_router(admin_router)


@app.get("/")
def home():
    return {"message": "Welcome to CampusFix API", "status": "Running"}


@app.get("/health")
def health_check():
    return {"status": "healthy", "application": "CampusFix"}


@app.post("/students/register", response_model=schemas.StudentResponse)
def register_student(student: schemas.StudentRegister, db: Session = Depends(get_db)):
    existing = db.query(models.Student).filter(
        models.Student.usn == student.usn
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="USN already registered")

    new_student = models.Student(
        name=student.name,
        usn=student.usn,
        department=student.department,
        year=student.year,
        password_hash=hash_password(student.password)
    )

    db.add(new_student)
    db.commit()
    db.refresh(new_student)
    return new_student


@app.post("/students/login")
def login_student(credentials: schemas.StudentLogin, db: Session = Depends(get_db)):
    student = db.query(models.Student).filter(
        models.Student.usn == credentials.usn
    ).first()

    if not student or not verify_password(
        credentials.password, student.password_hash
    ):
        raise HTTPException(status_code=401, detail="Invalid USN or password")

    return {
        "message": "Login successful",
        "student": {
            "id": student.id,
            "name": student.name,
            "usn": student.usn
        }
    }


@app.post("/complaints", response_model=schemas.ComplaintResponse)
def create_complaint(
    complaint: schemas.ComplaintCreate,
    student_id: int,
    db: Session = Depends(get_db)
):
    student = db.query(models.Student).filter(
        models.Student.id == student_id
    ).first()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    new_complaint = models.Complaint(
        **complaint.model_dump(),
        student_id=student_id
    )

    db.add(new_complaint)
    db.commit()
    db.refresh(new_complaint)
    return new_complaint


@app.get("/complaints")
def get_complaints(db: Session = Depends(get_db)):
    complaints = db.query(models.Complaint).all()
    return {"total": len(complaints), "complaints": complaints}


@app.get("/students/{student_id}/complaints")
def get_student_complaints(student_id: int, db: Session = Depends(get_db)):
    student = db.query(models.Student).filter(
        models.Student.id == student_id
    ).first()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    complaints = db.query(models.Complaint).filter(
        models.Complaint.student_id == student_id
    ).order_by(models.Complaint.created_at.desc()).all()

    return {"total": len(complaints), "complaints": complaints}


@app.get("/staff/{staff_id}/complaints")
def get_staff_tasks(staff_id: int, db: Session = Depends(get_db)):
    staff = db.query(models.Staff).filter(
        models.Staff.id == staff_id
    ).first()

    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")

    complaints = db.query(models.Complaint).filter(
        models.Complaint.staff_id == staff_id
    ).all()

    return {"total": len(complaints), "tasks": complaints}


@app.patch("/staff/{staff_id}/complaints/{complaint_id}/status")
def staff_update_status(
    staff_id: int,
    complaint_id: int,
    status: str,
    db: Session = Depends(get_db)
):
    if status not in ["In Progress", "Resolved"]:
        raise HTTPException(
            status_code=400,
            detail="Staff can only set status to In Progress or Resolved"
        )

    complaint = db.query(models.Complaint).filter(
        models.Complaint.id == complaint_id,
        models.Complaint.staff_id == staff_id
    ).first()

    if not complaint:
        raise HTTPException(
            status_code=404,
            detail="Assigned complaint not found for this staff member"
        )

    complaint.status = status
    db.commit()
    db.refresh(complaint)

    return {
        "message": "Task status updated",
        "complaint_id": complaint.id,
        "status": complaint.status
    }
