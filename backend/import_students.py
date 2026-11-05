"""Import the CSE Section F attendance workbook into CampusFix PostgreSQL."""
import csv
import secrets
from pathlib import Path

from openpyxl import load_workbook
from sqlalchemy import text

from app.database import Base, engine, SessionLocal
from app import models
from app.auth import hash_password

WORKBOOK = Path(__file__).with_name("Attendance.xlsx")
CREDENTIALS_FILE = Path(__file__).with_name("student_credentials.csv")


def read_students(path: Path):
    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook.active
    header_row = None
    usn_col = name_col = None

    for row_number, row in enumerate(sheet.iter_rows(values_only=True), start=1):
        normalized = [str(value).strip().lower() if value is not None else "" for value in row]
        if "usn" in normalized and "name" in normalized:
            header_row = row_number
            usn_col = normalized.index("usn")
            name_col = normalized.index("name")
            break

    if header_row is None:
        raise ValueError("Could not find the USN and Name header row in the workbook.")

    result = []
    for row in sheet.iter_rows(min_row=header_row + 1, values_only=True):
        usn = str(row[usn_col]).strip().upper() if len(row) > usn_col and row[usn_col] else ""
        name = str(row[name_col]).strip() if len(row) > name_col and row[name_col] else ""
        if usn and name and usn.lower() != "nan":
            result.append((usn, name))
    workbook.close()

    usns = [usn for usn, _ in result]
    if len(usns) != len(set(usns)):
        raise ValueError("Duplicate USNs found in Excel. Import stopped without inserting records.")
    return result


def main():
    if not WORKBOOK.exists():
        raise FileNotFoundError("Place Attendance.xlsx in the backend folder beside this script.")

    students = read_students(WORKBOOK)
    Base.metadata.create_all(bind=engine)

    # Add the new profile fields to an already-existing PostgreSQL students table.
    with engine.begin() as connection:
        connection.execute(text(
            "ALTER TABLE students ADD COLUMN IF NOT EXISTS semester INTEGER"
        ))
        connection.execute(text(
            "ALTER TABLE students ADD COLUMN IF NOT EXISTS section VARCHAR(10)"
        ))

    created = []
    skipped = []
    db = SessionLocal()
    try:
        for usn, name in students:
            existing = db.query(models.Student).filter(models.Student.usn == usn).first()
            if existing:
                skipped.append(usn)
                continue

            temporary_password = secrets.token_urlsafe(9)
            student = models.Student(
                name=name,
                usn=usn,
                department="CSE",
                year=2,
                semester=3,
                section="F",
                password_hash=hash_password(temporary_password),
            )
            db.add(student)
            db.flush()
            created.append((usn, name, temporary_password))

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    # This file contains temporary credentials. Keep it private and do not commit it.
    if created:
        with CREDENTIALS_FILE.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["USN", "Name", "Temporary Password"])
            writer.writerows(created)

    print(f"Excel records found: {len(students)}")
    print(f"New student accounts created: {len(created)}")
    print(f"Already-existing accounts skipped: {len(skipped)}")
    if created:
        print(f"Private temporary credentials saved to: {CREDENTIALS_FILE}")
    else:
        print("No new credentials file created because all USNs already exist.")


if __name__ == "__main__":
    main()
