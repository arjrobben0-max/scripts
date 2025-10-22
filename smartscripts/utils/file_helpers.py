# smartscripts/utils/file_helpers.py
import os
import csv
import uuid
import shutil
import zipfile
import logging
from pathlib import Path
from typing import Optional, List, Dict, Union

from flask import current_app
from werkzeug.utils import secure_filename
from smartscripts.config import BaseConfig
from smartscripts.utils import csv_helpers

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "txt", "csv", "doc", "docx"}

# ─────────────────────────────────────────────────────────────────────────────
# Core Helpers
# ─────────────────────────────────────────────────────────────────────────────
def get_upload_root() -> Path:
    """Return absolute Path to static/uploads, ensuring it exists."""
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
    """Generate a unique, secure filename."""
    return f"{uuid.uuid4().hex}_{secure_filename(filename)}"

# ─────────────────────────────────────────────────────────────────────────────
# Save File
# ─────────────────────────────────────────────────────────────────────────────
def save_file(
    file_storage,
    file_type: str,
    test_id: Union[str, int],
    student_id: Optional[Union[str, int]] = None,
    teacher_id: Optional[Union[str, int]] = None,
) -> str:
    """
    Save an uploaded file into the appropriate subfolder under static/uploads/.
    Returns a relative path from uploads/ suitable for storing in the DB.
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

    folder_name = folder_map[file_type]
    upload_root = get_upload_root()
    dir_path = upload_root / str(test_id) / folder_name

    if student_id:
        dir_path = dir_path / str(student_id)
    if teacher_id and folder_name == "tmp":
        dir_path = dir_path / str(teacher_id) / "working_files"

    dir_path.mkdir(parents=True, exist_ok=True)

    file_path = dir_path / unique_filename
    file_storage.save(str(file_path))

    # Return relative path from uploads/ (fix double 'uploads/' issue)
    rel_path = file_path.relative_to(upload_root)
    logger.info(f"✅ Saved file: {file_path}")
    return str(rel_path).replace("\\", "/")  # store in DB as '13/question_papers/...'

def get_uploaded_file_path(relative_path: str) -> Path:
    """Convert relative path (from uploads/) to absolute filesystem path."""
    if not relative_path:
        raise ValueError("relative_path cannot be empty")
    return get_upload_root() / relative_path

# ─────────────────────────────────────────────────────────────────────────────
# CSV/Class List Utilities
# ─────────────────────────────────────────────────────────────────────────────
def save_and_parse_class_list(file_storage, test_id: Union[str, int]) -> List[Dict[str, str]]:
    """Save a class list (CSV/TXT) and return parsed student data."""
    rel_path = save_file(file_storage, "class_list", test_id)
    full_path = get_uploaded_file_path(rel_path)
    students = csv_helpers.read_class_list(full_path)
    logger.info(f"📋 Parsed {len(students)} students from class list: {full_path}")
    return students

# ─────────────────────────────────────────────────────────────────────────────
# Directory Structure Management
# ─────────────────────────────────────────────────────────────────────────────
def create_test_directory_structure(test_id: Union[str, int]) -> Dict[str, Path]:
    """Ensure standard folder structure exists for a given test."""
    base = get_upload_root() / str(test_id)
    folders = [
        "answered_scripts",
        "audit_logs",
        "class_lists",
        "combined_scripts",
        "feedback",
        "manifests",
        "marked",
        "marking_guides",
        "question_papers",
        "resources",
        "rubrics",
        "student_lists",
        "student_scripts",
        "submissions",
        "tmp",
        "exports",
    ]
    paths = {}
    for f in folders:
        p = base / f
        p.mkdir(parents=True, exist_ok=True)
        paths[f] = p
    return paths

# ─────────────────────────────────────────────────────────────────────────────
# Directory Getters
# ─────────────────────────────────────────────────────────────────────────────
def get_dir(test_id: Union[str, int], *subdirs: str) -> Path:
    """Utility to quickly fetch or create nested directories."""
    path = get_upload_root() / str(test_id)
    for sub in subdirs:
        path = path / sub
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_exports_dir(test_id: Union[str, int]) -> Path:
    return get_dir(test_id, "exports")

# ─────────────────────────────────────────────────────────────────────────────
# CSV Output Generator
# ─────────────────────────────────────────────────────────────────────────────
def generate_presence_csv(
    matched: List[Dict[str, str]],
    unmatched: List[Dict[str, str]],
    test_id: Union[str, int],
) -> str:
    """Generate a presence table CSV file."""
    output_dir = get_exports_dir(test_id)
    csv_path = output_dir / "presence_table.csv"

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["student_id", "name", "email", "status"])
        for s in matched:
            writer.writerow([s["student_id"], s["name"], s.get("email", ""), "Present"])
        for s in unmatched:
            writer.writerow([s["student_id"], s["name"], s.get("email", ""), "Absent"])

    rel_path = csv_path.relative_to(get_upload_root())
    logger.info(f"📄 Generated presence table: {csv_path}")
    return str(rel_path).replace("\\", "/")

# ─────────────────────────────────────────────────────────────────────────────
# Test Folder Management
# ─────────────────────────────────────────────────────────────────────────────
def delete_test_folder(test_id: Union[str, int]) -> None:
    """Completely delete a test’s upload directory."""
    test_path = get_upload_root() / str(test_id)
    if test_path.exists():
        shutil.rmtree(test_path)
        logger.info(f"🗑 Deleted test folder: {test_path}")

def zip_test_directory(test_id: Union[str, int]) -> Path:
    """Zip a test directory and return the zip file path."""
    test_dir = get_upload_root() / str(test_id)
    if not test_dir.exists():
        raise FileNotFoundError(f"Test folder not found: {test_dir}")

    zip_path = test_dir.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in test_dir.rglob("*"):
            zf.write(f, f.relative_to(test_dir))

    logger.info(f"🗜 Created test ZIP: {zip_path}")
    return zip_path

# ─────────────────────────────────────────────────────────────────────────────
# Review / Analysis Utilities
# ─────────────────────────────────────────────────────────────────────────────
def get_student_script_pdf_path(test_id: Union[str, int], student_id: Union[str, int]) -> Optional[str]:
    pdf_path = get_upload_root() / str(test_id) / "answered_scripts" / f"{student_id}.pdf"
    if pdf_path.exists():
        return str(pdf_path)
    logger.warning(f"❌ Student script not found: {pdf_path}")
    return None

def get_image_path_for_page(test_id: Union[str, int], student_id: Union[str, int], page_num: int) -> Optional[str]:
    path = get_upload_root() / str(test_id) / "extracted" / str(student_id) / f"page_{page_num}.png"
    if path.exists():
        return str(path)
    logger.warning(f"❌ Page image not found: {path}")
    return None

def get_extracted_dir(zip_path: str) -> str:
    base_dir = Path(zip_path).parent
    extracted_dir = base_dir / "extracted"
    extracted_dir.mkdir(exist_ok=True)
    return str(extracted_dir)

def get_submission_dir(test_id: str, student_id: str) -> Path:
    path = BaseConfig.submissions(test_id, student_id)
    path.mkdir(parents=True, exist_ok=True)
    return path
