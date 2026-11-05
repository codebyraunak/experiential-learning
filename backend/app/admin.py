from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/complaints")
def view_all_complaints(db: Session = Depends(get_db)):
    complaints = db.query(models.Complaint).all()
    return {"total": len(complaints), "complaints": complaints}


@router.patch("/complaints/{complaint_id}/status")
def update_complaint_status(
    complaint_id: int,
    status: str,
    db: Session = Depends(get_db)
):
    allowed_statuses = [
        "Submitted", "Assigned", "In Progress", "Resolved", "Rejected"
    ]

    if status not in allowed_statuses:
        raise HTTPException(status_code=400, detail="Invalid complaint status")

    complaint = db.query(models.Complaint).filter(
        models.Complaint.id == complaint_id
    ).first()

    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    complaint.status = status
    db.commit()
    db.refresh(complaint)

    return {"message": "Status updated", "complaint_id": complaint.id,
            "status": complaint.status}


@router.post("/staff")
def create_staff(
    name: str,
    employee_id: str,
    department: str,
    phone: str = "",
    db: Session = Depends(get_db)
):
    existing = db.query(models.Staff).filter(
        models.Staff.employee_id == employee_id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Employee ID already exists")

    staff = models.Staff(
        name=name,
        employee_id=employee_id,
        department=department,
        phone=phone
    )

    db.add(staff)
    db.commit()
    db.refresh(staff)

    return {
        "message": "Staff created",
        "id": staff.id,
        "name": staff.name,
        "employee_id": staff.employee_id
    }


@router.get("/staff")
def list_staff(db: Session = Depends(get_db)):
    staff = db.query(models.Staff).all()
    return {"total": len(staff), "staff": staff}


@router.patch("/complaints/{complaint_id}/assign")
def assign_complaint(
    complaint_id: int,
    staff_id: int,
    db: Session = Depends(get_db)
):
    complaint = db.query(models.Complaint).filter(
        models.Complaint.id == complaint_id
    ).first()

    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    staff = db.query(models.Staff).filter(
        models.Staff.id == staff_id
    ).first()

    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")

    complaint.staff_id = staff_id
    complaint.status = "Assigned"

    db.commit()
    db.refresh(complaint)

    return {
        "message": "Complaint assigned successfully",
        "complaint_id": complaint.id,
        "staff_id": staff.id,
        "status": complaint.status
    }