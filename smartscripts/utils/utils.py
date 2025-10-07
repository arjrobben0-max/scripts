# smartscripts/utils/utils.py

import os
import magic
from flask import abort, current_app
from flask_login import current_user
from werkzeug.utils import secure_filename
from typing import Optional

# Base upload directory
BASE_UPLOAD_FOLDER = "static/uploads"


# ================================
# Access Control Utilities
# ================================

def check_role_access(required_role: str):
    """
    Aborts with 403 if the current user is not authenticated or lacks the required role.
    """
    if not current_user.is_authenticated or getattr(current_user, "role", None) != required_role:
        abort(403)


def check_teacher_access():
    check_role_access("teacher")


def check_student_access():
    check_role_access("student")


# ================================
# File Type Utilities
# ================================

def is_pdf(file) -> bool:
    """
    Checks if the uploaded file is a PDF based on MIME type.
    """
    file.seek(0)
    mime = magic.from_buffer(file.read(2048), mime=True)
    file.seek(0)
    return mime == "application/pdf"


def allowed_file(filename: str) -> bool:
    """
    Checks if the uploaded file has an allowed extension.
    Uses app config if available, otherwise falls back to default set.
    """
    allowed_exts = current_app.config.get(
        "ALLOWED_EXTENSIONS", {"jpg", "jpeg", "png", "pdf"}
    )
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_exts


# ================================
# File Handling Utilities
# ================================

def safe_remove(filepath: str):
    """
    Safely removes a file if it exists. Logs a warning on failure.
    """
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
    except Exception as e:
        current_app.logger.warning(f"Failed to delete file {filepath}: {e}")


def unique_filename(base_dir: str, filename: str) -> str:
    """
    Generate a unique filename in base_dir to avoid overwrite.
    """
    name, ext = os.path.splitext(filename)
    counter = 1
    candidate = filename
    while os.path.exists(os.path.join(base_dir, candidate)):
        candidate = f"{name}_{counter}{ext}"
        counter += 1
    return candidate


def save_file(
    file,
    subfolder: str,
    test_id: Optional[int] = None,
    student_id: Optional[int] = None,
) -> str:
    """
    Saves an uploaded file under a structured path based on subfolder and optional IDs.
    Returns a path relative to BASE_UPLOAD_FOLDER.
    """
    folder_path = resolve_upload_folder(subfolder, test_id, student_id)
    os.makedirs(folder_path, exist_ok=True)

    # Secure and unique filename
    filename = secure_filename(file.filename)
    filename = unique_filename(folder_path, filename)

    full_path = os.path.join(folder_path, filename)
    file.save(full_path)

    # Return path relative to BASE_UPLOAD_FOLDER
    return os.path.relpath(full_path, BASE_UPLOAD_FOLDER)


def resolve_upload_folder(subfolder: str, test_id: Optional[int], student_id: Optional[int]) -> str:
    """
    Resolves the full path for a subfolder based on optional test/student IDs.
    """
    subfolder_routes = {
        "guides": os.path.join(BASE_UPLOAD_FOLDER, "guides"),
        "rubrics": os.path.join(BASE_UPLOAD_FOLDER, "rubrics"),
        "scripts": lambda: os.path.join(BASE_UPLOAD_FOLDER, "scripts", f"test_id_{test_id}"),
        "submissions": lambda: os.path.join(BASE_UPLOAD_FOLDER, "submissions", f"test_id_{test_id}", f"student_id_{student_id}"),
        "ocr_images": lambda: os.path.join(BASE_UPLOAD_FOLDER, "submissions", f"test_id_{test_id}", f"student_id_{student_id}"),
        "marked": lambda: os.path.join(BASE_UPLOAD_FOLDER, "marked", f"test_id_{test_id}", f"student_id_{student_id}"),
        "audit_logs": lambda: os.path.join(BASE_UPLOAD_FOLDER, "audit_logs", f"test_id_{test_id}", f"student_id_{student_id}"),
        "exports": lambda: os.path.join(BASE_UPLOAD_FOLDER, "final_exports", f"test_id_{test_id}"),
    }

    if subfolder in ("guides", "rubrics"):
        return subfolder_routes[subfolder]
    elif subfolder in subfolder_routes and callable(subfolder_routes[subfolder]):
        try:
            return subfolder_routes[subfolder]()
        except TypeError:
            raise ValueError(f"Missing test_id/student_id for subfolder={subfolder}")
    else:
        raise ValueError(f"Invalid upload path: subfolder={subfolder}")


# ================================
# Auto-create standard folders
# ================================

def create_test_folders(test_id: int, student_ids: Optional[list[int]] = None):
    """
    Auto-create all standard folders for a given test.
    If student_ids are provided, create per-student folders as well.
    """
    base_paths = [
        os.path.join(BASE_UPLOAD_FOLDER, "scripts", f"test_id_{test_id}"),
        os.path.join(BASE_UPLOAD_FOLDER, "guides"),
        os.path.join(BASE_UPLOAD_FOLDER, "rubrics"),
        os.path.join(BASE_UPLOAD_FOLDER, "final_exports", f"test_id_{test_id}"),
    ]

    # Per-student folders
    if student_ids:
        for sid in student_ids:
            base_paths.extend([
                os.path.join(BASE_UPLOAD_FOLDER, "submissions", f"test_id_{test_id}", f"student_id_{sid}"),
                os.path.join(BASE_UPLOAD_FOLDER, "marked", f"test_id_{test_id}", f"student_id_{sid}"),
                os.path.join(BASE_UPLOAD_FOLDER, "audit_logs", f"test_id_{test_id}", f"student_id_{sid}"),
            ])

    # Create all directories
    for path in base_paths:
        os.makedirs(path, exist_ok=True)
