from pydantic import BaseModel, ConfigDict
from datetime import datetime


class ComplaintCreate(BaseModel):
    title: str
    description: str
    category: str
    location: str
    priority: str = "Medium"


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


class StudentRegister(BaseModel):
    name: str
    usn: str
    department: str
    year: int
    password: str
    semester: int | None = None
    section: str | None = None


class StudentLogin(BaseModel):
    usn: str
    password: str


class StudentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    usn: str
    department: str
    year: int
    semester: int | None = None
    section: str | None = None
