from pydantic import BaseModel
from datetime import datetime


class ComplaintCreate(BaseModel):
    title: str
    description: str
    category: str
    location: str
    priority: str = "Medium"


class ComplaintResponse(BaseModel):
    id: int
    title: str
    description: str
    category: str
    location: str
    priority: str
    status: str
    created_at: datetime
    student_id: int | None = None

    class Config:
        from_attributes = True

class StudentRegister(BaseModel):
    name: str
    usn: str
    department: str
    year: int
    password: str


class StudentLogin(BaseModel):
    usn: str
    password: str


class StudentResponse(BaseModel):
    id: int
    name: str
    usn: str
    department: str
    year: int

    class Config:
        from_attributes = True