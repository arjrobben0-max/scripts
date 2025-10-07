import json
from datetime import datetime
from smartscripts.extensions import db
from smartscripts.models import (
    AttendanceRecord,
    OCROverrideLog,
    User,
    Test,
)  # adjust if needed


def process_bulk_attendance_overrides(test_id: int, entries: list, user_id: int):
    count = 0

    for entry in entries:
        student_id = str(entry.get("student_id")).strip()
        present_str = str(entry.get("present", "yes")).strip().lower()
        present = present_str in ["yes", "1", "true"]

        # Find or create AttendanceRecord
        record = AttendanceRecord.query.filter_by(
            test_id=test_id, student_id=student_id
        ).first()
        if not record:
            record = AttendanceRecord(test_id=test_id, student_id=student_id)
            db.session.add(record)

        previous_value = str(record.present) if record.present is not None else None
        record.present = present  # type: ignore

        # Create OCROverrideLog â€” adapted to your actual model
        log = OcrOverrideLog(
            test_id=test_id,
            user_id=user_id,
            pdf_path=entry.get("pdf_path", "N/A"),
            old_name=entry.get("old_name"),
            old_id=entry.get("old_id"),
            new_name=entry.get("new_name"),
            new_id=entry.get("new_id"),
            timestamp=datetime.utcnow(),
        )
        db.session.add(log)

        count += 1

    db.session.commit()
    return count
