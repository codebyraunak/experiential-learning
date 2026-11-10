from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Notification


def add_notification(
    db: Session,
    *,
    target_role: str,
    target_user_id: int | None,
    complaint_id: int | None,
    kind: str,
    message: str,
    created_at: datetime | None = None,
) -> Notification:
    notification = Notification(
        target_role=target_role,
        target_user_id=target_user_id,
        complaint_id=complaint_id,
        kind=kind,
        message=message,
        created_at=created_at or datetime.now(timezone.utc),
    )
    db.add(notification)
    return notification
