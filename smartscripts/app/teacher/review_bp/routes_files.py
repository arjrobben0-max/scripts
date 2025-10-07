from pathlib import Path
from flask import Blueprint, flash, redirect, url_for, send_file
from flask_login import login_required, current_user

from smartscripts.models import Test
from smartscripts.app.teacher.utils import get_file_path, UPLOAD_FOLDERS, FILENAME_FIELDS

# -----------------------------
# Blueprint
# -----------------------------
review_files_bp = Blueprint("review_files_bp", __name__, url_prefix="/review/file")

# -----------------------------
# Routes
# -----------------------------
@review_files_bp.route("/<file_type>/<int:test_id>", methods=["GET"], endpoint="review_file")
@login_required
def review_file(file_type: str, test_id: int):
    """
    Serve uploaded test files to authorized teachers or admins.

    Args:
        file_type (str): Type of file (must be in FILENAME_FIELDS).
        test_id (int): ID of the test.

    Returns:
        Flask response: file download or redirect with flash message.
    """
    test = Test.query.get_or_404(test_id)

    # Check if current user is the teacher or admin
    if test.teacher_id != current_user.id and not current_user.is_admin:
        flash("Unauthorized access.", "danger")
        return redirect(url_for("teacher_bp.dashboard_bp.dashboard"))

    # Validate file_type
    if file_type not in FILENAME_FIELDS:
        flash("Invalid file type.", "danger")
        return redirect(url_for("upload_bp.upload_test_materials", test_id=test_id))

    # Get the filename
    filename = getattr(test, FILENAME_FIELDS[file_type])
    if not filename:
        flash(f"{file_type.replace('_', ' ').title()} not uploaded.", "warning")
        return redirect(url_for("upload_bp.upload_test_materials", test_id=test_id))

    # Build full file path
    file_path = get_file_path(Path(UPLOAD_FOLDERS[file_type]) / str(test_id) / filename)
    if not file_path.exists():
        flash("File not found.", "warning")
        return redirect(url_for("upload_bp.upload_test_materials", test_id=test_id))

    # Serve the file
    return send_file(file_path, as_attachment=True)
