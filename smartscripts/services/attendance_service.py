# File: smartscripts/services/attendance_service.py

import os
import csv
from pathlib import Path
from typing import List, Dict
from datetime import datetime
from flask import current_app

# -------------------------------
# Attendance / Presence Helpers
# -------------------------------

def generate_presence_csv(
    matched: List[Dict[str, str]],
    unmatched: List[Dict[str, str]],
    test_id: str
) -> str:
    """
    Generate a presence CSV report based on matched/unmatched students.

    Args:
        matched: List of students that were detected / present.
        unmatched: List of students that were absent.
        test_id: Test identifier (used to create output folder).

    Returns:
        Relative path to the generated CSV file.
    """
    # ✅ Ensure static folder exists and is usable
    static_folder = current_app.static_folder
    if static_folder is None:
        raise ValueError("Flask static_folder is not configured")

    output_dir = Path(static_folder) / "uploads" / "exports" / str(test_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = output_dir / f"presence_{timestamp}.csv"

    with csv_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["student_id", "name", "email", "status"])

        # Write matched students (Present)
        for student in matched:
            writer.writerow([
                student.get("student_id", ""),
                student.get("name", ""),
                student.get("email", ""),
                "Present"
            ])

        # Write unmatched students (Absent)
        for student in unmatched:
            writer.writerow([
                student.get("student_id", ""),
                student.get("name", ""),
                student.get("email", ""),
                "Absent"
            ])

    rel_path = csv_path.relative_to(Path(static_folder))
    print(f"🧾 Presence CSV saved to: {csv_path}")
    return str(rel_path).replace("\\", "/")


def update_attendance(
    class_list: List[Dict[str, str]],
    detected_ids: List[str]
) -> Dict[str, List[Dict[str, str]]]:
    """
    Compare OCR-detected student IDs with class list and return attendance mapping.

    Args:
        class_list: List of dicts with keys "student_id" and "name".
        detected_ids: List of OCR-detected student IDs.

    Returns:
        Dict with keys "present" and "absent", each containing a list of student dicts.
    """
    detected_set = {str(sid).strip() for sid in detected_ids if sid}

    present = []
    absent = []

    for student in class_list:
        student_id = str(student.get("student_id", "")).strip()
        if student_id in detected_set:
            present.append(student)
        else:
            absent.append(student)

    return {"present": present, "absent": absent}
