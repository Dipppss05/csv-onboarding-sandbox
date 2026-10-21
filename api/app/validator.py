"""Row-level validation for employee CSV uploads."""
import csv
import io
import re
from datetime import date
from decimal import Decimal, InvalidOperation

REQUIRED_COLUMNS = ["employee_id", "full_name", "email", "department_code", "hire_date", "hourly_rate"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def parse_csv(raw: bytes) -> tuple[list[str], list[dict]]:
    text = raw.decode("utf-8-sig")  # strips the BOM Excel adds to CSV exports
    reader = csv.DictReader(io.StringIO(text))
    headers = [h.strip().lower() for h in (reader.fieldnames or [])]
    reader.fieldnames = headers
    rows = [{k: (v or "").strip() for k, v in r.items() if k is not None} for r in reader]
    return headers, rows


def check_headers(headers: list[str]) -> list[str]:
    missing = [c for c in REQUIRED_COLUMNS if c not in headers]
    return [f"missing column: {c}" for c in missing]


def validate_rows(rows: list[dict], valid_departments: set[str]) -> tuple[list[dict], list[dict]]:
    """Return (accepted, rejected). Rejected rows carry the CSV line number and reasons."""
    accepted, rejected = [], []
    seen_ids, seen_emails = set(), set()

    for i, row in enumerate(rows, start=2):  # line 1 is the header
        errors = []
        clean = {}

        try:
            clean["employee_id"] = int(row["employee_id"])
            if clean["employee_id"] <= 0:
                errors.append("employee_id must be positive")
            elif clean["employee_id"] in seen_ids:
                errors.append("duplicate employee_id in file")
        except ValueError:
            errors.append(f"employee_id '{row['employee_id']}' is not an integer")

        if not row["full_name"]:
            errors.append("full_name is required")
        clean["full_name"] = row["full_name"]

        email = row["email"].lower()
        if not EMAIL_RE.match(email):
            errors.append(f"email '{row['email']}' is not valid")
        elif email in seen_emails:
            errors.append("duplicate email in file")
        clean["email"] = email

        dept = row["department_code"].upper()
        if dept not in valid_departments:
            errors.append(f"department_code '{row['department_code']}' does not exist")
        clean["department_code"] = dept

        try:
            hd = date.fromisoformat(row["hire_date"])
            if hd > date.today():
                errors.append("hire_date is in the future")
            clean["hire_date"] = hd
        except ValueError:
            errors.append(f"hire_date '{row['hire_date']}' must be YYYY-MM-DD")

        try:
            rate = Decimal(row["hourly_rate"])
            if rate <= 0:
                errors.append("hourly_rate must be greater than 0")
            clean["hourly_rate"] = rate
        except InvalidOperation:
            errors.append(f"hourly_rate '{row['hourly_rate']}' is not a number")

        if errors:
            rejected.append({"line": i, "employee_id": row["employee_id"], "errors": errors})
        else:
            seen_ids.add(clean["employee_id"])
            seen_emails.add(email)
            accepted.append(clean)

    return accepted, rejected
