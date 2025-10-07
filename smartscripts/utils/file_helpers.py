# smartscripts/utils/file_helpers.py

import os
import csv
import uuid
import shutil
import zipfile
import datetime
import logging
from pathlib import Path
from typing import Optional, List, Dict, Union

from flask import current_app
from werkzeug.utils import secure_filename
from pdf2image import convert_from_path
from smartscripts.utils import csv_helpers

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "txt", "csv"}

# -------------------------------
# Core Upload Helpers
# -------------------------------

def get_upload_root() -> Path:
    """Return absolute Path to static/uploads."""
    static_folder = current_app.static_folder
    if not static_folder:
        raise RuntimeError("current_app.static_folder is not set")
    root = Path(static_folder) / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    return root

def allowed_file(filename: str) -> bool:
    """Check if filename has an allowed extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_unique_filename(filename: str) -> str:
    """Generate a unique filename with UUID prefix."""
    filename = secure_filename(filename)
    return f"{uuid.uuid4().hex}_{filename}"

def save_file(
    file_storage,
    file_type: str,
    test_id: Union[str, int],
    student_id: Optional[Union[str, int]] = None,
    teacher_id: Optional[Union[str, int]] = None,
) -> str:
    """
    Save an uploaded file into the correct folder based on file_type.
    Returns relative path (str) usable with url_for('static', filename=...).
    """
    if not file_storage or not getattr(file_storage, "filename", None):
        raise ValueError("No file provided")

    filename = secure_filename(file_storage.filename)
    if not allowed_file(filename):
        raise ValueError(f"File type not allowed: {filename}")

    unique_filename = generate_unique_filename(filename)

    folder_map = {
        "question_paper": "question_papers",
        "rubric": "rubrics",
        "marking_guide": "marking_guides",
        "answered_script": "answered_scripts",
        "class_list": "class_lists",
        "student_list": "student_lists",
        "combined_scripts": "combined_scripts",
        "submission": "submissions",
        "feedback": "feedback",
        "marked": "marked",
        "manifest": "manifests",
        "audit_log": "audit_logs",
        "resource": "resources",
        "student_script": "student_scripts",
        "tmp": "tmp",
        "export": "exports",
    }

    if file_type not in folder_map:
        raise ValueError(f"Unknown file_type: {file_type}")

    folder = folder_map[file_type]
    dir_path: Path = get_upload_root() / str(test_id) / folder

    if student_id is not None:
        dir_path = dir_path / str(student_id)
    if teacher_id is not None and folder == "tmp":
        dir_path = dir_path / str(teacher_id) / "working_files"

    dir_path.mkdir(parents=True, exist_ok=True)

    file_path: Path = dir_path / unique_filename
    file_storage.save(str(file_path))

    # Return relative path for URL / DB storage
    static_folder = current_app.static_folder
    if not static_folder:
        raise RuntimeError("current_app.static_folder is not set")
    rel_path = file_path.relative_to(Path(static_folder))
    logger.info(f"✅ File saved: {file_path} (relative path: {rel_path})")
    return str(rel_path).replace("\\", "/")

def get_uploaded_file_path(relative_path: Optional[str]) -> Path:
    """Return absolute Path from a relative static path."""
    if not relative_path:
        raise ValueError("relative_path cannot be None")
    static_folder = current_app.static_folder
    if not static_folder:
        raise RuntimeError("current_app.static_folder is not set")
    return Path(static_folder) / relative_path

# -------------------------------
# Class/Student List Parsing
# -------------------------------

def save_and_parse_class_list(file_storage, test_id: Union[str, int]) -> List[Dict[str, str]]:
    """Save uploaded class list CSV/TXT and return parsed student list."""
    relative_path = save_file(file_storage, "class_list", test_id)
    full_path = get_uploaded_file_path(relative_path)
    students = csv_helpers.read_class_list(full_path)
    logger.info(f"Parsed {len(students)} students from class list: {full_path}")
    return students

# -------------------------------
# Test Directory Utilities
# -------------------------------

def create_test_directory_structure(test_id: Union[str, int]) -> Dict[str, Path]:
    """Create all required subfolders for a test and return absolute paths."""
    base = get_upload_root() / str(test_id)
    folders = [
        "answered_scripts",
        "audit_logs",
        "class_lists",
        "combined_scripts",
        "extracted",
        "feedback",
        "manifests",
        "marked",
        "marking_guides",
        "question_papers",
        "resources/images",
        "resources/code",
        "resources/datasets",
        "rubrics",
        "student_lists",
        "student_scripts",
        "submissions",
        "tmp",
        "exports",
    ]
    paths: Dict[str, Path] = {}
    for folder in folders:
        path = base / folder
        path.mkdir(parents=True, exist_ok=True)
        paths[folder] = path
    return paths

# -------------------------------
# Convenience Getters
# -------------------------------

def get_submission_dir(test_id: Union[str, int], student_id: Optional[Union[str, int]] = None) -> Path:
    base = get_upload_root() / str(test_id) / "submissions"
    if student_id is not None:
        return base / str(student_id)
    return base

def get_student_output_dir(test_id: Union[str, int]) -> Path:
    path = get_submission_dir(test_id) / "processed"
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_answered_scripts_dir(test_id: Union[str, int]) -> Path:
    return get_upload_root() / str(test_id) / "answered_scripts"

def get_marking_guide_dir(test_id: Union[str, int]) -> Path:
    return get_upload_root() / str(test_id) / "marking_guides"

def get_rubric_dir(test_id: Union[str, int]) -> Path:
    return get_upload_root() / str(test_id) / "rubrics"

def get_combined_scripts_dir(test_id: Union[str, int]) -> Path:
    return get_upload_root() / str(test_id) / "combined_scripts"

def get_student_lists_dir(test_id: Union[str, int]) -> Path:
    return get_upload_root() / str(test_id) / "student_lists"

def get_extracted_dir(test_id: Union[str, int], student_id: Optional[Union[str, int]] = None) -> Path:
    base = get_upload_root() / str(test_id) / "extracted"
    if student_id is not None:
        return base / str(student_id)
    return base

def get_feedback_dir(test_id: Union[str, int]) -> Path:
    return get_upload_root() / str(test_id) / "feedback"

def get_marked_dir(test_id: Union[str, int]) -> Path:
    return get_upload_root() / str(test_id) / "marked"

def get_manifest_dir(test_id: Union[str, int]) -> Path:
    return get_upload_root() / str(test_id) / "manifests"

def get_audit_log_dir(test_id: Union[str, int]) -> Path:
    return get_upload_root() / str(test_id) / "audit_logs"

def get_resources_dir(test_id: Union[str, int]) -> Path:
    return get_upload_root() / str(test_id) / "resources"

def get_tmp_dir(test_id: Union[str, int], teacher_id: Union[str, int]) -> Path:
    return get_upload_root() / str(test_id) / "tmp" / str(teacher_id) / "working_files"

def get_exports_dir(test_id: Union[str, int]) -> Path:
    return get_upload_root() / str(test_id) / "exports"

# -------------------------------
# CSV Helpers
# -------------------------------

def generate_presence_csv(
    matched: List[Dict[str, str]], unmatched: List[Dict[str, str]], test_id: Union[str, int]
) -> str:
    """Generate a presence CSV and return relative path."""
    output_dir = get_exports_dir(test_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "presence_table.csv"

    with csv_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["student_id", "name", "email", "status"])
        for student in matched:
            writer.writerow([student["student_id"], student["name"], student.get("email", ""), "Present"])
        for student in unmatched:
            writer.writerow([student["student_id"], student["name"], student.get("email", ""), "Absent"])

    return str(csv_path.relative_to(get_upload_root()))

# -------------------------------
# Test Folder Management
# -------------------------------

def delete_test_folder(test_id: Union[str, int]) -> None:
    test_path = get_upload_root() / str(test_id)
    if test_path.exists() and test_path.is_dir():
        shutil.rmtree(test_path)
        logger.info(f"🗑 Deleted test folder: {test_path}")

def zip_test_directory(test_id: Union[str, int]) -> Path:
    test_dir = get_upload_root() / str(test_id)
    if not test_dir.exists():
        raise FileNotFoundError(f"Test folder does not exist: {test_dir}")

    zip_path = test_dir.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file_path in test_dir.rglob("*"):
            zipf.write(file_path, file_path.relative_to(test_dir))
    return zip_path

# -------------------------------
# Review Utilities (NEW)
# -------------------------------

def get_student_script_pdf_path(test_id: Union[str, int], student_id: Union[str, int]) -> Optional[str]:
    """
    Return the absolute path to the student's answered script PDF.
    Looks under: uploads/<test_id>/answered_scripts/<student_id>.pdf
    """
    base_dir = get_answered_scripts_dir(test_id)
    pdf_path = base_dir / f"{student_id}.pdf"
    if pdf_path.exists():
        return str(pdf_path)
    logger.warning(f"❌ Student script not found: {pdf_path}")
    return None

def get_image_path_for_page(test_id: Union[str, int], student_id: Union[str, int], page_num: int) -> Optional[str]:
    """
    Return absolute path to a student's per-page extracted image.
    Assumes images are saved under: uploads/<test_id>/extracted/<student_id>/page_<page_num>.png
    """
    extracted_dir = get_extracted_dir(test_id, student_id)
    image_path = extracted_dir / f"page_{page_num}.png"
    if image_path.exists():
        return str(image_path)
    logger.warning(f"❌ Page image not found: {image_path}")
    return None
