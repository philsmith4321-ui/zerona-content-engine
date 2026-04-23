import csv
import io
import uuid
from datetime import datetime
from typing import Optional

from app.campaign_db import upsert_patient, insert_import_history, recompute_all_tiers
from app.database import log_event


# Standard column names we expect
EXPECTED_COLUMNS = {
    "email": ["email", "e-mail", "email_address", "emailaddress"],
    "first_name": ["first_name", "firstname", "first", "fname", "name"],
    "last_name": ["last_name", "lastname", "last", "lname", "surname"],
    "phone": ["phone", "phone_number", "phonenumber", "mobile", "cell"],
    "last_visit_date": ["last_visit_date", "lastvisit", "last_visit", "last_appt", "lastappointment"],
    "gender": ["gender", "sex"],
    "age": ["age"],
    "tags": ["tags", "categories", "groups"],
}


def auto_map_columns(header_row: list[str]) -> dict[str, str]:
    """Attempt to auto-map CSV columns to our expected fields."""
    mapping = {}
    header_lower = [h.strip().lower().replace(" ", "_") for h in header_row]
    for field, aliases in EXPECTED_COLUMNS.items():
        for i, col in enumerate(header_lower):
            if col in aliases:
                mapping[field] = header_row[i].strip()
                break
    return mapping


def preview_csv(file_content: str, limit: int = 5) -> dict:
    """Parse CSV and return headers + preview rows for column mapping UI."""
    reader = csv.reader(io.StringIO(file_content))
    headers = next(reader, [])
    headers = [h.strip() for h in headers]
    rows = []
    for i, row in enumerate(reader):
        if i >= limit:
            break
        rows.append(row)
    auto_mapping = auto_map_columns(headers)
    return {"headers": headers, "preview_rows": rows, "auto_mapping": auto_mapping}


def import_patients(file_content: str, column_mapping: dict[str, str], filename: str = "upload.csv") -> dict:
    """Import patients from CSV content using the provided column mapping.

    column_mapping: {our_field: csv_header_name} e.g. {"email": "Email Address", "first_name": "First"}
    """
    batch_id = f"import_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    reader = csv.DictReader(io.StringIO(file_content))

    total = 0
    imported = 0
    duplicates = 0
    errors = 0

    # Invert mapping: csv_header -> our_field
    reverse_map = {v: k for k, v in column_mapping.items() if v}

    for row in reader:
        total += 1
        try:
            data = {"import_batch_id": batch_id}
            for csv_col, our_field in reverse_map.items():
                val = row.get(csv_col, "").strip()
                if our_field == "age" and val:
                    try:
                        data["age"] = int(val)
                    except ValueError:
                        data["age"] = None
                elif our_field == "tags" and val:
                    data["tags"] = [t.strip() for t in val.split(",") if t.strip()]
                else:
                    data[our_field] = val

            if not data.get("email"):
                errors += 1
                continue

            _, was_inserted = upsert_patient(data)
            if was_inserted:
                imported += 1
            else:
                duplicates += 1
        except Exception:
            errors += 1

    result = {
        "filename": filename,
        "column_mapping": column_mapping,
        "total_rows": total,
        "imported": imported,
        "duplicates_skipped": duplicates,
        "errors": errors,
        "batch_id": batch_id,
    }
    insert_import_history(result)
    log_event("import", f"Imported {imported} patients from {filename}", result)
    return result
