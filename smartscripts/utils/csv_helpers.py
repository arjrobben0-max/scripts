# smartscripts/utils/csv_helpers.py

import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
from fuzzywuzzy import fuzz
from flask import current_app


def read_class_list(file_path: Path) -> List[Dict[str, Any]]:
    """
    Reads a class list CSV or TXT and returns a list of students.
    Each student is a dict with keys: 'name' and 'student_id'.
    Supports CSV files with headers: 'name', 'student_id' (case-insensitive),
    or TXT files with 'name,student_id' per line.

    Args:
        file_path (Path): Path to the uploaded class list file.

    Returns:
        List[Dict[str, Any]]: List of student dictionaries.
    """
    students: List[Dict[str, Any]] = []

    if not file_path.exists():
        current_app.logger.warning(f"Class list file does not exist: {file_path}")
        return students

    file_ext = file_path.suffix.lower()

    try:
        if file_ext == ".csv":
            with file_path.open(newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    name = (
                        row.get("name")
                        or row.get("Name")
                        or row.get("student_name")
                        or ""
                    )
                    student_id = (
                        row.get("student_id")
                        or row.get("Student ID")
                        or row.get("id")
                        or ""
                    )
                    if name.strip() or student_id.strip():
                        students.append(
                            {"name": name.strip(), "student_id": student_id.strip()}
                        )

        elif file_ext == ".txt":
            with file_path.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if "," in line:
                        name, student_id = line.split(",", 1)
                        students.append(
                            {"name": name.strip(), "student_id": student_id.strip()}
                        )
                    else:
                        students.append({"name": line.strip(), "student_id": ""})
        else:
            current_app.logger.warning(f"Unsupported class list format: {file_ext}")
            return students

    except Exception as e:
        current_app.logger.error(f"Failed to read class list {file_path}: {e}")

    return students


def fuzzy_match_student(
    ocr_id: str, class_list: List[Dict[str, Any]], threshold: int = 80
) -> Optional[Dict[str, Any]]:
    """
    Fuzzy match OCR ID against class list.

    Args:
        ocr_id (str): Student ID extracted from OCR.
        class_list (List[Dict[str, Any]]): List of student dicts with 'student_id' keys.
        threshold (int, optional): Minimum fuzzy match score to consider. Defaults to 80.

    Returns:
        Optional[Dict[str, Any]]: Best matching student dict or None if no match.
    """
    best_match: Optional[Dict[str, Any]] = None
    highest_score = 0

    for student in class_list:
        score = fuzz.ratio(ocr_id, student.get("student_id", ""))
        if score > highest_score and score >= threshold:
            highest_score = score
            best_match = student

    return best_match
