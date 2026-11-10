from import_admission_data import parse_pdf_pages


def _row(usn: str, department: str, name: str) -> str:
    return f"{usn:<14}{department:<9}{name:<26}{'FATHER':<27}{'MOTHER':<24}{'1234567890'}"


def test_parse_pdf_rows_and_wrapped_names():
    page = "\n".join([
        "USN Branch Name Father Name Mother Name Admission",
        _row("1ab26cs001", "cs", "ALEXANDER"),
        " " * 23 + "SMITH",
        _row("1AB26EC002", "ec", "JORDAN"),
    ])

    result = parse_pdf_pages([page])

    assert result.extracted_count == 2
    assert result.invalid_count == 0
    assert result.duplicate_count == 0
    assert [(record.usn, record.name, record.department) for record in result.records] == [
        ("1AB26CS001", "ALEXANDER SMITH", "CS"),
        ("1AB26EC002", "JORDAN", "EC"),
    ]


def test_duplicate_usns_are_not_returned_twice():
    page = "\n".join([
        "USN Branch Name Father Name Mother Name Admission",
        _row("1AB26CS001", "CS", "ALEX"),
        _row("1AB26CS001", "CS", "ALEX"),
    ])

    result = parse_pdf_pages([page])

    assert result.extracted_count == 2
    assert result.duplicate_count == 1
    assert len(result.records) == 1
