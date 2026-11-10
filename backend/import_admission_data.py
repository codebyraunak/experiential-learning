"""Import admission USNs, student names, and branch codes into CampusFix."""

import argparse
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app import models
from app.database import SessionLocal
from app.normalization import normalize_department_code, normalize_usn

logger = logging.getLogger("campusfix.admission_import")

USN_ROW_RE = re.compile(
    r"^\s*(?P<usn>\d[A-Z]{2}\d{2}[A-Z]{2}\d{3})\s+",
    re.IGNORECASE,
)
USN_CANDIDATE_RE = re.compile(r"^\s*(?P<token>\d[A-Z0-9]{7,11})\s+", re.IGNORECASE)
NAME_COLUMN_WIDTH = 26


@dataclass(frozen=True)
class AdmissionRecord:
    usn: str
    name: str
    department: str
    page: int
    line: int


@dataclass(frozen=True)
class ExtractionIssue:
    page: int
    line: int
    reason: str


@dataclass
class ExtractionResult:
    page_count: int
    extracted_count: int = 0
    invalid_count: int = 0
    duplicate_count: int = 0
    records: list[AdmissionRecord] = field(default_factory=list)
    issues: list[ExtractionIssue] = field(default_factory=list)
    pages_without_records: list[int] = field(default_factory=list)


def _column_starts(lines: list[str]) -> tuple[int, int] | None:
    for line in lines:
        if not USN_ROW_RE.match(line):
            continue
        token_starts = [match.start() for match in re.finditer(r"\S+", line)]
        if len(token_starts) >= 3:
            return token_starts[1], token_starts[2]
    return None


def parse_pdf_pages(page_texts: list[str]) -> ExtractionResult:
    result = ExtractionResult(page_count=len(page_texts))
    parsed_records: list[AdmissionRecord] = []

    for page_number, text in enumerate(page_texts, start=1):
        lines = text.splitlines()
        if not any(
            all(label in line for label in ("USN", "Branch", "Name", "Father", "Mother", "Admission"))
            for line in lines
        ):
            result.issues.append(
                ExtractionIssue(page_number, 0, "admission table header not found")
            )
            result.pages_without_records.append(page_number)
            continue

        starts = _column_starts(lines)
        if starts is None:
            result.issues.append(
                ExtractionIssue(page_number, 0, "no readable student rows found")
            )
            result.pages_without_records.append(page_number)
            continue

        branch_start, name_start = starts
        current_usn: str | None = None
        current_department = ""
        current_name_parts: list[str] = []
        current_page = 0
        current_line = 0
        page_row_count = 0

        def finish_record() -> None:
            nonlocal current_usn, current_department, current_name_parts
            if current_usn is None:
                return

            name = re.sub(r"\s+", " ", " ".join(current_name_parts)).strip()
            if not name or len(name) > 100:
                result.invalid_count += 1
                result.issues.append(
                    ExtractionIssue(current_page, current_line, "student name is empty or too long")
                )
            elif not current_department or len(current_department) > 50:
                result.invalid_count += 1
                result.issues.append(
                    ExtractionIssue(current_page, current_line, "branch code is empty or too long")
                )
            else:
                parsed_records.append(
                    AdmissionRecord(
                        usn=current_usn,
                        name=name,
                        department=current_department,
                        page=current_page,
                        line=current_line,
                    )
                )
            current_usn = None
            current_name_parts = []

        for line_number, line in enumerate(lines, start=1):
            candidate_match = USN_CANDIDATE_RE.match(line)
            if not candidate_match:
                if current_usn is not None:
                    continuation = line[name_start:name_start + NAME_COLUMN_WIDTH].strip()
                    if continuation:
                        current_name_parts.append(continuation)
                continue

            finish_record()
            result.extracted_count += 1
            page_row_count += 1
            row_match = USN_ROW_RE.match(line)
            if not row_match:
                result.invalid_count += 1
                result.issues.append(
                    ExtractionIssue(page_number, line_number, "USN does not match the admission format")
                )
                continue

            token_starts = [match.start() for match in re.finditer(r"\S+", line)]
            if (
                len(token_starts) < 3
                or token_starts[1] != branch_start
                or token_starts[2] != name_start
            ):
                result.invalid_count += 1
                result.issues.append(
                    ExtractionIssue(page_number, line_number, "student row has inconsistent columns")
                )
                continue

            department = normalize_department_code(line[branch_start:name_start])
            if not re.fullmatch(r"[A-Z0-9]{1,10}", department):
                result.invalid_count += 1
                result.issues.append(
                    ExtractionIssue(page_number, line_number, "branch code is invalid")
                )
                continue

            current_usn = normalize_usn(row_match.group("usn"))
            current_department = department
            current_name_parts = [line[name_start:name_start + NAME_COLUMN_WIDTH].strip()]
            current_page = page_number
            current_line = line_number

        finish_record()
        if page_row_count == 0:
            result.issues.append(
                ExtractionIssue(page_number, 0, "no student rows recognized on page")
            )
            result.pages_without_records.append(page_number)

    records_by_usn: dict[str, AdmissionRecord] = {}
    conflicting_usns: set[str] = set()
    for record in parsed_records:
        previous = records_by_usn.get(record.usn)
        if previous is None:
            records_by_usn[record.usn] = record
            continue

        result.duplicate_count += 1
        result.issues.append(
            ExtractionIssue(record.page, record.line, "duplicate USN in admission PDF")
        )
        if (previous.name, previous.department) != (record.name, record.department):
            conflicting_usns.add(record.usn)
            result.issues.append(
                ExtractionIssue(record.page, record.line, "duplicate USN has conflicting student details")
            )

    result.records = [
        record
        for usn, record in records_by_usn.items()
        if usn not in conflicting_usns
    ]
    return result


def extract_admission_pdf(pdf_path: Path) -> ExtractionResult:
    reader = PdfReader(str(pdf_path))
    page_texts = [
        page.extract_text(extraction_mode="layout") or ""
        for page in reader.pages
    ]
    return parse_pdf_pages(page_texts)


def import_records(records: list[AdmissionRecord]) -> set[str]:
    if not records:
        return set()

    statement = (
        pg_insert(models.Student.__table__)
        .values([
            {
                "usn": record.usn,
                "name": record.name,
                "department": record.department,
            }
            for record in records
        ])
        .on_conflict_do_nothing(index_elements=[models.Student.usn])
        .returning(models.Student.usn)
    )

    with SessionLocal.begin() as db:
        inserted_usns = set(db.execute(statement).scalars())

    return inserted_usns


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_path", type=Path, help="Path to the admission PDF")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and summarize without writing to PostgreSQL",
    )
    args = parser.parse_args()

    if not args.pdf_path.is_file():
        parser.error(f"PDF file does not exist: {args.pdf_path}")

    result = extract_admission_pdf(args.pdf_path)
    for issue in result.issues:
        logger.error(
            "PDF review required at page %d, text line %d: %s",
            issue.page,
            issue.line,
            issue.reason,
        )

    if result.pages_without_records:
        logger.error(
            "Import stopped: student rows were not verified on pages %s",
            ", ".join(map(str, result.pages_without_records)),
        )
        return 1

    if args.dry_run:
        inserted_usns: set[str] = set()
        print(f"Pages processed: {result.page_count}")
        print(f"Student records extracted: {result.extracted_count}")
        print(f"Valid unique records ready: {len(result.records)}")
        print(f"Duplicate records in PDF: {result.duplicate_count}")
        print(f"Invalid records: {result.invalid_count}")
        print("Database writes: none (dry run)")
        return 0

    inserted_usns = import_records(result.records)
    database_duplicates = len(result.records) - len(inserted_usns)
    duplicate_count = result.duplicate_count + database_duplicates
    skipped_count = result.extracted_count - len(inserted_usns)
    print(f"Pages processed: {result.page_count}")
    print(f"Student records extracted: {result.extracted_count}")
    print(f"Successfully imported: {len(inserted_usns)}")
    print(f"Skipped: {skipped_count}")
    print(f"Duplicate USNs (PDF and database): {duplicate_count}")
    print(f"Invalid records: {result.invalid_count}")
    print(f"Database duplicates: {database_duplicates}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR, format="%(levelname)s: %(message)s")
    raise SystemExit(main())
