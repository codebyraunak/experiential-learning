from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime
from typing import Literal

from app.normalization import normalize_usn


class ComplaintCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10000)
    category: Literal[
        "Electrical", "Plumbing", "Furniture", "Network",
        "AV Equipment", "Washroom", "Other",
    ] | None = None
    location: str = Field(min_length=1, max_length=200)
    priority: Literal["low", "medium", "high", "critical"] | None = None
    suggested_team: str | None = Field(default=None, max_length=100)
    summary: str | None = Field(default=None, max_length=1000)


class ComplaintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    category: str
    location: str
    priority: str
    status: str
    created_at: datetime
    student_id: int | None = None
    suggested_team: str | None = None
    summary: str | None = None
    due_at: datetime | None = None
    escalation_level: int = 0
    before_photo_path: str | None = None
    after_photo_path: str | None = None
    resolution_note: str | None = None
    verification_deadline: datetime | None = None
    closed_at: datetime | None = None


class LoginRequest(BaseModel):
    role: Literal["admin", "staff"]
    username: str
    password: str


class StaffCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    employee_id: str = Field(min_length=1, max_length=30)
    department: str = Field(min_length=1, max_length=50)
    phone: str | None = Field(default=None, max_length=15)
    password: str = Field(min_length=12, max_length=256)


class VerificationRequest(BaseModel):
    action: Literal["confirm", "reopen"]


class LocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    details: str | None = Field(default=None, max_length=1000)


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    complaint_id: int | None
    kind: str
    message: str
    created_at: datetime
    read: bool


class StudentRegister(BaseModel):
    usn: str
    password: str

    @field_validator("usn")
    @classmethod
    def normalize_student_usn(cls, value: str) -> str:
        return normalize_usn(value)


class StudentLogin(BaseModel):
    usn: str
    password: str

    @field_validator("usn")
    @classmethod
    def normalize_student_usn(cls, value: str) -> str:
        return normalize_usn(value)


class StudentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    usn: str
    department: str | None = None
    year: int | None = None
    semester: int | None = None
    section: str | None = None
