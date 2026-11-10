from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import hash_password
from app.database import get_db
from app.notifications import add_notification
from app.security import Principal, require_roles

router = APIRouter(prefix="/admin", tags=["Admin"])
admin_only = require_roles("admin")


@router.get("/complaints")
def view_all_complaints(
    db: Session = Depends(get_db),
    _: Principal = Depends(admin_only),
):
    complaints = (
        db.query(models.Complaint)
        .order_by(models.Complaint.created_at.desc())
        .all()
    )
    return {"total": len(complaints), "complaints": complaints}


@router.patch("/complaints/{complaint_id}/status")
def update_complaint_status(
    complaint_id: int,
    status: str,
    db: Session = Depends(get_db),
    _: Principal = Depends(admin_only),
):
    allowed_statuses = ["Reported", "Submitted", "Assigned", "In Progress"]
    if status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail="Admin cannot mark a task resolved without staff proof of fix",
        )
    complaint = db.query(models.Complaint).filter(
        models.Complaint.id == complaint_id
    ).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    if complaint.status in ("Resolved", "Closed"):
        raise HTTPException(
            status_code=409,
            detail="Resolved complaints must follow student verification",
        )
    if status == "Assigned" and complaint.staff_id is None:
        raise HTTPException(
            status_code=409,
            detail="Assign the complaint to a staff member before setting Assigned",
        )
    complaint.status = status
    db.commit()
    db.refresh(complaint)
    return {
        "message": "Status updated",
        "complaint_id": complaint.id,
        "status": complaint.status,
    }


@router.post("/staff")
def create_staff(
    name: str,
    employee_id: str,
    department: str,
    phone: str = "",
    db: Session = Depends(get_db),
    _: Principal = Depends(admin_only),
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
        phone=phone,
    )
    db.add(staff)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=400, detail="Employee ID already exists") from error
    db.refresh(staff)
    return {
        "message": "Staff created; set up login credentials using /admin/staff/accounts",
        "id": staff.id,
        "name": staff.name,
        "employee_id": staff.employee_id,
    }


@router.post("/staff/accounts")
def create_staff_account(
    request: schemas.StaffCreate,
    db: Session = Depends(get_db),
    _: Principal = Depends(admin_only),
):
    staff = db.query(models.Staff).filter(
        models.Staff.employee_id == request.employee_id
    ).first()
    if staff is not None:
        if staff.password_hash:
            raise HTTPException(status_code=409, detail="Staff account already has login credentials")
        staff.password_hash = hash_password(request.password)
    else:
        staff = models.Staff(
            name=request.name,
            employee_id=request.employee_id,
            department=request.department,
            phone=request.phone,
            password_hash=hash_password(request.password),
        )
        db.add(staff)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=400, detail="Employee ID already exists") from error
    db.refresh(staff)
    return {
        "id": staff.id,
        "name": staff.name,
        "employee_id": staff.employee_id,
        "department": staff.department,
    }


@router.get("/complaints/{complaint_id}/escalations")
def complaint_escalations(
    complaint_id: int,
    db: Session = Depends(get_db),
    _: Principal = Depends(admin_only),
):
    complaint = db.get(models.Complaint, complaint_id)
    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found")
    history = (
        db.query(models.EscalationHistory)
        .filter(models.EscalationHistory.complaint_id == complaint_id)
        .order_by(models.EscalationHistory.level)
        .all()
    )
    return {
        "complaint_id": complaint_id,
        "history": [
            {"level": event.level, "target": event.target, "created_at": event.created_at}
            for event in history
        ],
    }


@router.get("/staff")
def list_staff(
    db: Session = Depends(get_db),
    _: Principal = Depends(admin_only),
):
    staff = db.query(models.Staff).order_by(models.Staff.name).all()
    return {
        "total": len(staff),
        "staff": [
            {
                "id": person.id,
                "name": person.name,
                "employee_id": person.employee_id,
                "department": person.department,
                "phone": person.phone,
            }
            for person in staff
        ],
    }


@router.patch("/complaints/{complaint_id}/assign")
def assign_complaint(
    complaint_id: int,
    staff_id: int,
    db: Session = Depends(get_db),
    _: Principal = Depends(admin_only),
):
    complaint = db.query(models.Complaint).filter(
        models.Complaint.id == complaint_id
    ).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    if complaint.status not in ("Reported", "Submitted", "Assigned"):
        raise HTTPException(status_code=409, detail="Only reported complaints can be assigned")
    staff = db.query(models.Staff).filter(models.Staff.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")

    complaint.staff_id = staff.id
    complaint.status = "Assigned"
    add_notification(
        db,
        target_role="staff",
        target_user_id=staff.id,
        complaint_id=complaint.id,
        kind="assignment",
        message=f"Complaint #{complaint.id} has been assigned to you.",
    )
    db.commit()
    db.refresh(complaint)
    return {
        "message": "Complaint assigned successfully",
        "complaint_id": complaint.id,
        "staff_id": staff.id,
        "status": complaint.status,
    }


@router.post("/locations")
def create_location(
    request: schemas.LocationCreate,
    db: Session = Depends(get_db),
    _: Principal = Depends(admin_only),
):
    location = models.Location(name=request.name.strip(), details=request.details)
    db.add(location)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Location already exists") from error
    db.refresh(location)
    return {"id": location.id, "name": location.name, "details": location.details}


@router.get("/locations")
def list_locations(
    db: Session = Depends(get_db),
    _: Principal = Depends(admin_only),
):
    locations = db.query(models.Location).order_by(models.Location.name).all()
    return {
        "locations": [
            {"id": item.id, "name": item.name, "details": item.details}
            for item in locations
        ]
    }


@router.get("/departments/counts")
def department_counts(
    db: Session = Depends(get_db),
    _: Principal = Depends(admin_only),
):
    from sqlalchemy import func

    counts = (
        db.query(models.Student.department, func.count(models.Student.id))
        .filter(models.Student.department.is_not(None))
        .group_by(models.Student.department)
        .order_by(models.Student.department)
        .all()
    )
    return {"departments": [{"department": department, "count": count} for department, count in counts]}
