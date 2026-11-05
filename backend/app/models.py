from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    usn = Column(String(20), unique=True, index=True, nullable=False)
    department = Column(String(50))
    year = Column(Integer)
    password_hash = Column(String(255), nullable=True)

    complaints = relationship("Complaint", back_populates="student")


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(50), nullable=False)
    location = Column(String(200), nullable=False)
    priority = Column(String(20), default="Medium")
    status = Column(String(30), default="Submitted")
    created_at = Column(DateTime, default=datetime.utcnow)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    student = relationship("Student", back_populates="complaints")

class Staff(Base):
    __tablename__ = "staff"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    employee_id = Column(String(30), unique=True, nullable=False)
    department = Column(String(50), nullable=False)
    phone = Column(String(15))