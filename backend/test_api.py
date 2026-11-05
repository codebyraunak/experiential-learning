import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )

    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_student_registration_and_login(client):
    student_data = {
        "name": "Test Student",
        "usn": "TEST001",
        "department": "CSE",
        "year": 3,
        "password": "Test@12345"
    }

    register_response = client.post(
        "/students/register",
        json=student_data
    )
    assert register_response.status_code == 200

    login_response = client.post(
        "/students/login",
        json={
            "usn": "TEST001",
            "password": "Test@12345"
        }
    )
    assert login_response.status_code == 200
    assert login_response.json()["message"] == "Login successful"


def test_complaint_and_staff_workflow(client):
    # Register student
    student_response = client.post(
        "/students/register",
        json={
            "name": "Test Student",
            "usn": "TEST002",
            "department": "CSE",
            "year": 3,
            "password": "Test@12345"
        }
    )
    assert student_response.status_code == 200
    student_id = student_response.json()["id"]

    # Create complaint
    complaint_response = client.post(
        f"/complaints?student_id={student_id}",
        json={
            "title": "Classroom light not working",
            "description": "Two lights are not working.",
            "category": "Electrical",
            "location": "Block A, Room 204",
            "priority": "Medium"
        }
    )
    assert complaint_response.status_code == 200
    complaint_id = complaint_response.json()["id"]

    # Create staff member
    staff_response = client.post(
        "/admin/staff",
        params={
            "name": "Rohan",
            "employee_id": "EMP001",
            "department": "Electrical",
            "phone": "123456789"
        }
    )
    assert staff_response.status_code == 200
    staff_id = staff_response.json()["id"]

    # Assign complaint to staff
    assign_response = client.patch(
        f"/admin/complaints/{complaint_id}/assign",
        params={"staff_id": staff_id}
    )
    assert assign_response.status_code == 200
    assert assign_response.json()["status"] == "Assigned"

    # Staff views assigned task
    tasks_response = client.get(f"/staff/{staff_id}/complaints")
    assert tasks_response.status_code == 200
    assert tasks_response.json()["total"] == 1

    # Staff updates status
    update_response = client.patch(
        f"/staff/{staff_id}/complaints/{complaint_id}/status",
        params={"status": "In Progress"}
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "In Progress"

    # Student views complaint history
    history_response = client.get(
        f"/students/{student_id}/complaints"
    )
    assert history_response.status_code == 200
    assert history_response.json()["total"] == 1
    assert history_response.json()["complaints"][0]["status"] == "In Progress"