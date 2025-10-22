import os
from pathlib import Path

from flask import Blueprint, render_template, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from flask_wtf.csrf import CSRFError
from sqlalchemy.orm import joinedload

from smartscripts.extensions import db
from smartscripts.models import Test, AttendanceRecord
from smartscripts.app.forms import TestForm
from smartscripts.utils.file_helpers import get_uploaded_file_path

dashboard_bp = Blueprint("dashboard_bp", __name__, url_prefix="/dashboard")

# Mapping file types to upload folders
FILE_TYPE_TO_FOLDER = {
    "marking_guide": "marking_guides",
    "class_list": "class_lists",
    "rubric": "rubrics",
    "combined_scripts": "combined_scripts",
    "answered_script": "answered_scripts",
    "question_paper": "question_papers",
}

# Corresponding model path attributes
FILE_TYPE_TO_MODEL_PATH_ATTR = {
    "marking_guide": "marking_guide_path",
    "class_list": "class_list_path",
    "rubric": "rubric_path",
    "combined_scripts": "combined_scripts_path",
    "answered_script": "answered_script_path",
    "question_paper": "question_paper_path",
}


def get_valid_tests_for_user(user) -> list[Test]:
    """Return valid tests for the current user/admin, with attendance and file checks."""
    query = Test.query.options(joinedload(Test.marking_guide))
    tests = query.all() if user.is_admin else query.filter_by(teacher_id=user.id).all()

    valid_tests = [
        test
        for test in tests
        if test.title and test.subject and test.grade_level and test.id is not None
    ]

    for test in valid_tests:
        # Load attendance records
        test.attendance_records = AttendanceRecord.query.filter_by(test_id=test.id).all()

        # Check required teacher-uploaded files
        test.all_required_files_uploaded = all(
            getattr(test, FILE_TYPE_TO_MODEL_PATH_ATTR.get(ft, ""), None)
            for ft in ["class_list", "combined_scripts", "marking_guide", "question_paper"]
        )

    return valid_tests


@dashboard_bp.route("/", methods=["GET", "POST"])
@login_required
def dashboard():
    """Render dashboard showing upload form and list of uploaded tests."""
    try:
        form = TestForm()
        uploaded_tests = Test.query.filter_by(teacher_id=current_user.id).all()

        return render_template(
            "teacher/dashboard.html",
            form=form,
            uploaded_tests=uploaded_tests,
            teacher_name=current_user.username,
        )

    except Exception as e:
        current_app.logger.error(f"Error loading dashboard: {e}", exc_info=True)
        flash("An error occurred while loading the dashboard.", "danger")
        return render_template(
            "teacher/dashboard.html",
            uploaded_tests=[],
            form=TestForm(),
            teacher_name=current_user.username,
        )


@dashboard_bp.route("/delete_file/<int:test_id>/<file_type>", methods=["POST"])
@login_required
def delete_file(test_id: int, file_type: str):
    """Delete a specific uploaded file for a test."""
    try:
        test = Test.query.get_or_404(test_id)

        if test.teacher_id != current_user.id and not current_user.is_admin:
            flash("Unauthorized", "danger")
            return redirect(url_for("dashboard_bp.dashboard"))

        if file_type not in FILE_TYPE_TO_MODEL_PATH_ATTR:
            flash("Invalid file type.", "danger")
            return redirect(url_for("dashboard_bp.dashboard"))

        path_attr = FILE_TYPE_TO_MODEL_PATH_ATTR[file_type]
        file_path_str = getattr(test, path_attr, None)
        if not file_path_str:
            flash("File path not set.", "warning")
            return redirect(url_for("dashboard_bp.dashboard"))

        # Build absolute path
        abs_path: Path = get_uploaded_file_path(file_path_str)

        if abs_path.exists():
            abs_path.unlink()
            setattr(test, path_attr, None)
            db.session.commit()
            flash(f"{file_type.replace('_', ' ').capitalize()} deleted successfully.", "info")
        else:
            flash("File not found.", "warning")

    except Exception as e:
        current_app.logger.error(
            f"Error deleting {file_type} file for test {test_id}: {e}", exc_info=True
        )
        flash("Deletion failed.", "danger")

    return redirect(url_for("dashboard_bp.dashboard"))


# ------------------ Error Handlers ------------------


@dashboard_bp.app_errorhandler(CSRFError)
def handle_csrf_error(e):
    current_app.logger.error(f"CSRF error: {e.description}", exc_info=True)
    return render_template("errors/400.html", reason=e.description), 400


@dashboard_bp.app_errorhandler(400)
def handle_bad_request(e):
    current_app.logger.error(f"400 Bad Request: {e}", exc_info=True)
    return render_template("errors/400.html", reason=str(e)), 400
