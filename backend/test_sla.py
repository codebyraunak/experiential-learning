from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models
from app.database import Base
from app.sla import deadline_for, escalation_levels_due, run_sla_cycle


def test_sla_deadlines_and_escalation_thresholds():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert deadline_for("Network", now) == now + timedelta(hours=4)
    assert deadline_for("Other", now) == now + timedelta(hours=48)
    assert escalation_levels_due(now, now - timedelta(seconds=1)) == []
    assert escalation_levels_due(now, now) == [1]
    assert escalation_levels_due(now, now + timedelta(hours=24)) == [1, 2]
    assert escalation_levels_due(now, now + timedelta(hours=72)) == [1, 2, 3]


def test_sla_cycle_escalates_and_auto_closes():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    now = datetime(2026, 1, 5, tzinfo=timezone.utc)
    with Session(engine) as db:
        student = models.Student(name="Test", usn="SLA001", department="CSE")
        db.add(student)
        db.flush()
        overdue = models.Complaint(
            title="Overdue",
            description="Test",
            category="Network",
            location="Block A",
            priority="medium",
            status="Reported",
            student_id=student.id,
            due_at=now - timedelta(hours=80),
        )
        resolved = models.Complaint(
            title="Awaiting confirmation",
            description="Test",
            category="Other",
            location="Block A",
            priority="medium",
            status="Resolved",
            student_id=student.id,
            due_at=now + timedelta(hours=48),
            verification_deadline=now - timedelta(seconds=1),
        )
        db.add_all([overdue, resolved])
        db.commit()
        run_sla_cycle(db, now)
        assert overdue.escalation_level == 3
        assert resolved.status == "Closed"
        assert db.query(models.EscalationHistory).filter_by(complaint_id=overdue.id).count() == 3
        assert db.query(models.Notification).filter_by(kind="escalation").count() == 3
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
