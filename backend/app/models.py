from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.database import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    usn = Column(String(20), unique=True, index=True, nullable=False)
    department = Column(String(50))
    year = Column(Integer)
    semester = Column(Integer, nullable=True)
    section = Column(String(10), nullable=True)
    password_hash = Column(String(255), nullable=True)

    complaints = relationship("Complaint", back_populates="student")


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(50), nullable=False)
    location = Column(String(200), nullable=False)
    priority = Column(String(20), default="medium", nullable=False)
    status = Column(String(30), default="Reported", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    suggested_team = Column(String(100), nullable=True)
    summary = Column(Text, nullable=True)
    before_photo_path = Column(String(255), nullable=True)
    after_photo_path = Column(String(255), nullable=True)
    resolution_note = Column(Text, nullable=True)
    due_at = Column(DateTime(timezone=True), nullable=True, index=True)
    escalation_level = Column(Integer, default=0, nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    verification_deadline = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    student = relationship("Student", back_populates="complaints")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    target_role = Column(String(20), nullable=False)
    target_user_id = Column(Integer, nullable=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=True)
    kind = Column(String(40), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    read = Column(Boolean, default=False, nullable=False)


class EscalationHistory(Base):
    __tablename__ = "escalation_history"
    __table_args__ = (
        UniqueConstraint("complaint_id", "level", name="uq_escalation_complaint_level"),
    )

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False)
    level = Column(Integer, nullable=False)
    target = Column(String(30), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, unique=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Staff(Base):
    __tablename__ = "staff"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    employee_id = Column(String(30), unique=True, nullable=False)
    department = Column(String(50), nullable=False)
    phone = Column(String(15))
    password_hash = Column(String(255), nullable=True)
