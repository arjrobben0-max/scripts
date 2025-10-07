import os
from pathlib import Path
from flask import Blueprint, current_app, send_file, abort, flash, redirect, url_for
from flask_login import login_required, current_user
from smartscripts.models import Test

download_bp = Blueprint("download_bp", __name__, url_prefix="/download")


# -------------------------------
# Helper Functions
# -------------------------------

def _secure_send_file(file_path):
    """Send a file securely, abort 404 if not found."""
    if not file_path:
        abort(404)
    # Convert relative path to absolute if needed
    path_obj = Path(file_path)
    if not path_obj.is_file():
        # Try static folder
        path_obj = Path(current_app.static_folder) / file_path
        if not path_obj.is_file():
            abort(404)
    return send_file(str(path_obj), as_attachment=True)


def _check_test_ownership(test):
    """Ensure the current user owns the test."""
    if test.teacher_id != current_user.id:
        abort(403)


# -------------------------------
# File Download Routes
# -------------------------------

@download_bp.route("/question_paper/<int:test_id>")
@login_required
def download_question_paper(test_id):
    test = Test.query.get_or_404(test_id)
    _check_test_ownership(test)
    return _secure_send_file(test.question_paper_path)


@download_bp.route("/rubric/<int:test_id>")
@login_required
def download_rubric(test_id):
    test = Test.query.get_or_404(test_id)
    _check_test_ownership(test)
    return _secure_send_file(test.rubric_path)


@download_bp.route("/marking_guide/<int:test_id>")
@login_required
def download_marking_guide(test_id):
    test = Test.query.get_or_404(test_id)
    _check_test_ownership(test)
    return _secure_send_file(test.marking_guide_path)


@download_bp.route("/answered_script/<int:test_id>")
@login_required
def download_answered_script(test_id):
    test = Test.query.get_or_404(test_id)
    _check_test_ownership(test)
    return _secure_send_file(test.answered_script_path)


@download_bp.route("/class_list/<int:test_id>")
@login_required
def download_class_list(test_id):
    test = Test.query.get_or_404(test_id)
    _check_test_ownership(test)
    return _secure_send_file(test.class_list_path)


@download_bp.route("/combined_scripts/<int:test_id>")
@login_required
def download_combined_scripts(test_id):
    test = Test.query.get_or_404(test_id)
    _check_test_ownership(test)
    return _secure_send_file(test.combined_scripts_path)


@download_bp.route("/student_list/<int:test_id>")
@login_required
def download_student_list(test_id):
    """
    Download the OCR-generated student list CSV for this test.
    """
    base_dir = Path(current_app.static_folder) / "uploads" / str(test_id) / "extracted" / "student_list"
    csv_path = base_dir / f"student_list_test_{test_id}.csv"
    if not csv_path.exists():
        flash("Student list not found.", "warning")
        return redirect(url_for("dashboard_bp.dashboard"))
    return _secure_send_file(csv_path)


@download_bp.route("/review_zip/<int:test_id>")
@login_required
def download_review_zip(test_id):
    """
    Download the preprocessed review ZIP (PDFs + logs) after front-page detection & OCR.
    """
    base_dir = Path(current_app.static_folder) / "uploads" / str(test_id) / "extracted"
    zip_path = base_dir / "review_package.zip"
    if not zip_path.exists():
        flash("Review package not found. Make sure preprocessing has completed.", "warning")
        return redirect(url_for("dashboard_bp.dashboard"))
    return _secure_send_file(zip_path)


@download_bp.route("/download_all/<int:test_id>")
@login_required
def download_all_files(test_id):
    """
    Placeholder: ZIP of all files for the test.
    """
    flash("Download all files feature coming soon.", "info")
    return redirect(url_for("dashboard_bp.dashboard"))
