def normalize_usn(value: str) -> str:
    return value.strip().upper()


def normalize_department_code(value: str) -> str:
    return " ".join(value.split()).upper()
