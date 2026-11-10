"""Apply additive, idempotent PostgreSQL migrations for CampusFix."""

from sqlalchemy import text

from app.database import Base, engine
from app import models  # noqa: F401

COMPLAINT_COLUMNS = {
    "suggested_team": "VARCHAR(100)",
    "summary": "TEXT",
    "before_photo_path": "VARCHAR(255)",
    "after_photo_path": "VARCHAR(255)",
    "resolution_note": "TEXT",
    "due_at": "TIMESTAMPTZ",
    "escalation_level": "INTEGER NOT NULL DEFAULT 0",
    "resolved_at": "TIMESTAMPTZ",
    "verification_deadline": "TIMESTAMPTZ",
    "closed_at": "TIMESTAMPTZ",
}


def migrate() -> None:
    with engine.begin() as connection:
        for column, definition in COMPLAINT_COLUMNS.items():
            connection.execute(
                text(f"ALTER TABLE complaints ADD COLUMN IF NOT EXISTS {column} {definition}")
            )
        connection.execute(
            text("ALTER TABLE staff ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)")
        )
        connection.execute(
            text("ALTER TABLE complaints ALTER COLUMN priority SET DEFAULT 'medium'")
        )
        connection.execute(
            text("ALTER TABLE complaints ALTER COLUMN status SET DEFAULT 'Reported'")
        )

    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_complaints_due_at ON complaints (due_at)")
        )


if __name__ == "__main__":
    migrate()
    print("CampusFix PostgreSQL migrations applied.")
