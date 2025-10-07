# File: smartscripts/services/file_manager.py

import csv
import uuid
import zipfile
import logging
from typing import Optional, List, Dict
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename

from smartscripts.utils import csv_helpers
from smartscripts.services.ocr_helpers import (
    detect_student_front_pages,
    pdf_to_images,
    safe_extract_name_id,
    split_pdf_by_page_ranges,
)

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "txt", "csv"}


# -------------------------------
# Core Upload Helpers
# -------------------------------

def get_upload_root() -> Path:
    """
    Return the root upload directory inside Flask's static folder.
    Ensures the folder exists.
    """
    static_folder = current_app.static_folder
    if not static_folder:
        raise RuntimeError("Flask static folder is not configured")

    root = Path(static_folder) / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    return root


def allowed_file(filename: str) -> bool:
    """Check if a filename has an allowed extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_unique_filename(filename: str) -> str:
    """Generate a unique filename with a UUID prefix."""
    return f"{uuid.uuid4().hex}_{secure_filename(filename)}"


def save_uploaded_file(
    file_storage,
    file_type: str,
    test_id: int,
    student_id: Optional[str] = None,
) -> str:
    """
    Save an uploaded file to the correct folder.

    Returns:
        Relative path (to static folder).
    """
    if not file_storage or not getattr(file_storage, "filename", None):
        raise ValueError("No file provided")

    filename = secure_filename(file_storage.filename)
    if not filename:
        raise ValueError("File has no filename")
    if not allowed_file(filename):
        raise ValueError(f"File type not allowed: {filename}")

    unique_filename = generate_unique_filename(filename)

    folder_map = {
        "question_paper": "question_papers",
        "rubric": "rubrics",
        "marking_guide": "marking_guides",
        "answered_script": "answered_scripts",
        "class_list": "class_lists",
        "combined_scripts": "combined_scripts",
        "student_list": "student_lists",
        "student_scripts": "student_scripts",
    }
    if file_type not in folder_map:
        raise ValueError(f"Unknown file_type: {file_type}")

    dir_path = get_upload_root() / folder_map[file_type] / str(test_id)
    if student_id:
        dir_path /= str(student_id)
    dir_path.mkdir(parents=True, exist_ok=True)

    file_path = dir_path / unique_filename
    file_storage.save(str(file_path))

    static_folder = current_app.static_folder
    if not static_folder:
        raise RuntimeError("Flask static folder is not configured")

    try:
        rel_path = file_path.relative_to(Path(static_folder))
    except ValueError:
        rel_path = file_path

    logger.info("✔ File saved: %s (relative path: %s)", file_path, rel_path)
    return str(rel_path).replace("\\", "/")


def get_file_url(relative_path: str) -> str:
    """Convert a relative static path into an absolute file system path."""
    if not relative_path:
        raise ValueError("relative_path cannot be None or empty")

    static_folder = current_app.static_folder
    if not static_folder:
        raise RuntimeError("Flask static folder is not configured")

    return str(Path(static_folder) / relative_path)


# -------------------------------
# CSV & Class List Helpers
# -------------------------------

def save_and_parse_class_list(file_storage, test_id: int) -> List[Dict[str, str]]:
    """
    Save and parse a class list CSV.

    Returns:
        List of student dictionaries.
    """
    relative_path = save_uploaded_file(file_storage, "class_list", test_id)

    static_folder = current_app.static_folder
    if not static_folder:
        raise RuntimeError("Flask static folder is not configured")

    full_path = Path(static_folder) / relative_path

    if not full_path.exists():
        raise FileNotFoundError(f"Class list file not found: {full_path}")

    students = csv_helpers.read_class_list(full_path)
    logger.info("Parsed %d students from class list: %s", len(students), full_path)
    return students


def generate_presence_csv(
    matched: List[Dict[str, str]],
    unmatched: List[Dict[str, str]],
    test_id: int,
) -> str:
    """
    Generate a CSV marking students as Present/Absent.

    Returns:
        Relative path to presence.csv
    """
    output_dir = get_upload_root() / "exports" / str(test_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "presence.csv"
    with open(csv_path, mode="w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["student_id", "name", "email", "status"])
        for student in matched:
            writer.writerow([
                student.get("student_id", ""),
                student.get("name", ""),
                student.get("email", ""),
                "Present",
            ])
        for student in unmatched:
            writer.writerow([
                student.get("student_id", ""),
                student.get("name", ""),
                student.get("email", ""),
                "Absent",
            ])

    try:
        return str(csv_path.relative_to(get_upload_root())).replace("\\", "/")
    except ValueError:
        return str(csv_path)


# -------------------------------
# PDF Preprocessing / Student Detection
# -------------------------------

def split_pdf_by_student(
    combined_pdf_path: str,
    test_id: int,
    class_list: Optional[List[Dict[str, str]]] = None,
) -> List[Dict[str, str]]:
    """
    Split a combined PDF into per-student scripts using OCR + layout detection.

    Returns:
        List of dicts containing OCR results and extracted file paths.
    """
    if not combined_pdf_path:
        raise ValueError("combined_pdf_path cannot be None or empty")

    pdf_path = Path(combined_pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"{combined_pdf_path} not found")

    images = pdf_to_images(pdf_path)
    page_ranges = detect_student_front_pages(images)

    upload_dir = get_upload_root() / "student_scripts" / str(test_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    student_scripts: List[Dict[str, str]] = []

    for start, end in page_ranges:
        front_image = images[start]
        name, student_id, confidence = safe_extract_name_id(front_image)
        student_id = student_id or "unknown"
        name = name or "unknown"

        split_paths = split_pdf_by_page_ranges(
            pdf_path=str(pdf_path),
            ranges=[(start, end)],
            output_dir=str(upload_dir),
        )
        extracted_pdf_path: Optional[Path] = split_paths[0] if split_paths else None

        if extracted_pdf_path:
            new_filename = f"{student_id}-{name.replace(' ', '_')}.pdf"
            new_path = upload_dir / new_filename
            extracted_pdf_path.rename(new_path)
            extracted_pdf_path = new_path

        student_scripts.append({
            "ocr_student_id": student_id,
            "ocr_name": name,
            "ocr_confidence": str(confidence),
            "extracted_pdf_path": (
                str(extracted_pdf_path.relative_to(get_upload_root()))
                if extracted_pdf_path else ""
            ),
        })

    if class_list:
        for script in student_scripts:
            matched = [
                s for s in class_list
                if s.get("student_id") == script["ocr_student_id"]
                or s.get("name") == script["ocr_name"]
            ]
            if matched:
                script["matched"] = "True"
                script["matched_name"] = matched[0].get("name", "")
            else:
                script["matched"] = "False"
                script["matched_name"] = ""

    return student_scripts


# -------------------------------
# Zip / Backup Helpers
# -------------------------------

def zip_student_scripts(student_scripts: List[Dict[str, str]], output_zip: str) -> None:
    """
    Create a ZIP file containing all extracted student scripts.
    """
    if not output_zip:
        raise ValueError("output_zip cannot be None or empty")

    output_zip_path = Path(output_zip)
    with zipfile.ZipFile(output_zip_path, "w") as zf:
        for script in student_scripts:
            pdf_path_str = script.get("extracted_pdf_path")
            if not pdf_path_str:
                continue
            pdf_path = get_upload_root() / pdf_path_str
            if pdf_path.exists():
                zf.write(pdf_path, arcname=pdf_path.name)

    logger.info("Generated review ZIP: %s", output_zip_path)
