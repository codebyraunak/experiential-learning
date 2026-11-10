from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app import models
from app.notifications import add_notification

SLA_HOURS = {
    "Network": 4,
    "Electrical": 24,
    "Plumbing": 24,
    "Furniture": 72,
    "AV Equipment": 24,
    "Washroom": 12,
    "Other": 48,
}

ESCALATION_THRESHOLDS = {
    1: timedelta(0),
    2: timedelta(hours=24),
    3: timedelta(hours=72),
}
ESCALATION_TARGETS = {1: "admin", 2: "HOD", 3: "principal"}
UNRESOLVED_STATUSES = ("Reported", "Submitted", "Assigned", "In Progress")


def deadline_for(category: str, created_at: datetime) -> datetime:
    hours = SLA_HOURS.get(category, SLA_HOURS["Other"])
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return created_at + timedelta(hours=hours)


def escalation_levels_due(due_at: datetime, now: datetime) -> list[int]:
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    overdue_by = now - due_at
    return [
        level
        for level, threshold in ESCALATION_THRESHOLDS.items()
        if overdue_by >= threshold
    ]


def run_sla_cycle(db: Session, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    overdue = (
        db.query(models.Complaint)
        .filter(
            models.Complaint.due_at.is_not(None),
            models.Complaint.due_at <= now,
            models.Complaint.status.in_(UNRESOLVED_STATUSES),
        )
        .with_for_update()
        .all()
    )

    for complaint in overdue:
        existing_levels = {
            level
            for (level,) in db.query(models.EscalationHistory.level)
            .filter(models.EscalationHistory.complaint_id == complaint.id)
            .all()
        }
        due_levels = escalation_levels_due(complaint.due_at, now)
        for level in due_levels:
            if level in existing_levels:
                continue
            target = ESCALATION_TARGETS[level]
            db.add(
                models.EscalationHistory(
                    complaint_id=complaint.id,
                    level=level,
                    target=target,
                    created_at=now,
                )
            )
            add_notification(
                db,
                target_role="admin",
                target_user_id=None,
                complaint_id=complaint.id,
                kind="escalation",
                message=f"Level {level} escalation: complaint #{complaint.id} is overdue. Follow up with {target}.",
                created_at=now,
            )
        if due_levels:
            complaint.escalation_level = max(complaint.escalation_level, max(due_levels))

    auto_close = (
        db.query(models.Complaint)
        .filter(
            models.Complaint.status == "Resolved",
            models.Complaint.verification_deadline.is_not(None),
            models.Complaint.verification_deadline <= now,
        )
        .with_for_update()
        .all()
    )
    for complaint in auto_close:
        complaint.status = "Closed"
        complaint.closed_at = now

    db.commit()
