import io
import logging
from pathlib import Path

from celery.result import AsyncResult
from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, abort, request, jsonify, current_app
)
from flask_login import login_required, current_user

from smartscripts.extensions import db
from smartscripts.models import Test
from smartscripts.models.task_control import TaskControl
from smartscripts.app.forms import UploadFileForm, DeleteFileForm, PreprocessingForm
from smartscripts.utils.file_helpers import save_file, get_uploaded_file_path
from smartscripts.config import BaseConfig

manage_bp = Blueprint("manage_bp", __name__, url_prefix="/manage")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ALLOWED_FILE_TYPES = [
    "question_paper",
    "marking_guide",
    "class_list",
    "rubric",
    "answered_script",
    "combined_scripts",
]

# ---------------- Manage Test Files ----------------
@manage_bp.route("/test/<int:test_id>/files", methods=["GET"])
@login_required
def manage_test_files(test_id: int):
    test = Test.query.get_or_404(test_id)
    if test.teacher_id != current_user.id and not current_user.is_admin:
        abort(403)

    file_types = [
        ("question_paper", "Question Paper"),
        ("marking_guide", "Marking Guide"),
        ("class_list", "Class List"),
        ("rubric", "Rubric"),
        ("answered_script", "Answered Script"),
        ("combined_scripts", "Student Scripts (Combined PDF)"),
    ]

    upload_forms = {ft[0]: UploadFileForm(prefix=ft[0]) for ft in file_types}
    delete_forms = {ft[0]: DeleteFileForm(prefix=f"del_{ft[0]}") for ft in file_types}
    preprocessing_form = PreprocessingForm()

    file_urls = {}
    for key, _ in file_types:
        rel_path = getattr(test, f"{key}_path", None)
        if rel_path:
            abs_path: Path = get_uploaded_file_path(rel_path)
            file_urls[key] = (
                url_for("static", filename=rel_path.replace("\\", "/"))
                if abs_path.exists() else None
            )
        else:
            file_urls[key] = None

    active_task = TaskControl.query.filter_by(status="RUNNING").first()
    task_id = active_task.task_id if active_task else None

    return render_template(
        "teacher/manage_test_files.html",
        test=test,
        file_types=file_types,
        upload_forms=upload_forms,
        delete_forms=delete_forms,
        preprocessing_form=preprocessing_form,
        file_urls=file_urls,
        task_id=task_id,
    )


# ---------------- Upload / Delete ----------------
@manage_bp.route("/test/<int:test_id>/upload/<file_type>", methods=["POST"])
@login_required
def upload_file(test_id: int, file_type: str):
    form = UploadFileForm(prefix=file_type)
    if not form.validate_on_submit():
        flash(f"Validation failed: {form.errors}", "danger")
        return redirect(url_for("manage_bp.manage_test_files", test_id=test_id))

    test = Test.query.get_or_404(test_id)
    if test.teacher_id != current_user.id and not current_user.is_admin:
        abort(403)

    if file_type not in ALLOWED_FILE_TYPES:
        flash("Invalid file type.", "danger")
        return redirect(url_for("manage_bp.manage_test_files", test_id=test_id))

    try:
        old_file_path = getattr(test, f"{file_type}_path", None)
        if old_file_path:
            try:
                abs_old_path: Path = get_uploaded_file_path(old_file_path)
                abs_old_path.unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Could not delete old {file_type}: {e}")

        rel_path = save_file(form.file.data, file_type, test.id)
        setattr(test, f"{file_type}_path", rel_path)
        db.session.commit()

        BaseConfig.init_upload_dirs(test_id=test.id)
        flash(f"{file_type.replace('_', ' ').title()} uploaded successfully.", "success")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error uploading {file_type}: {e}")
        flash("Error while uploading file. Please try again.", "danger")

    return redirect(url_for("manage_bp.manage_test_files", test_id=test.id))


@manage_bp.route("/test/<int:test_id>/delete/<file_type>", methods=["POST"])
@login_required
def delete_file(test_id: int, file_type: str):
    form = DeleteFileForm(prefix=f"del_{file_type}")
    if not form.validate_on_submit():
        flash(f"Validation failed: {form.errors}", "danger")
        return redirect(url_for("manage_bp.manage_test_files", test_id=test_id))

    test = Test.query.get_or_404(test_id)
    if test.teacher_id != current_user.id and not current_user.is_admin:
        abort(403)

    if file_type not in ALLOWED_FILE_TYPES:
        flash("Invalid file type.", "danger")
        return redirect(url_for("manage_bp.manage_test_files", test_id=test_id))

    file_path = getattr(test, f"{file_type}_path", None)
    if file_path:
        try:
            abs_path: Path = get_uploaded_file_path(file_path)
            abs_path.unlink(missing_ok=True)
            flash(f"{file_type.replace('_', ' ').title()} deleted successfully.", "success")
        except Exception as e:
            logger.error(f"Error deleting {file_type}: {e}")
            flash(f"Error deleting {file_type}.", "danger")
    else:
        flash("File does not exist or already deleted.", "warning")

    setattr(test, f"{file_type}_path", None)
    db.session.commit()
    return redirect(url_for("manage_bp.manage_test_files", test_id=test.id))

# ---------------- Preprocessing ----------------
@manage_bp.route("/start_preprocessing/<int:test_id>", methods=["POST"])
@login_required
def start_preprocessing(test_id: int):
    # Lazy import with Pylance ignore to prevent circular import & type errors
    from smartscripts.tasks.ocr_tasks import run_student_script_ocr_pipeline  # type: ignore

    form = PreprocessingForm()
    if not form.validate_on_submit():
        flash(f"Validation failed: {form.errors}", "danger")
        return redirect(url_for("manage_bp.manage_test_files", test_id=test_id))

    test = Test.query.get_or_404(test_id)
    if test.teacher_id != current_user.id and not current_user.is_admin:
        abort(403)

    required_files = [
        "marking_guide_path",
        "question_paper_path",
        "combined_scripts_path",
        "class_list_path"
    ]
    missing = [f for f in required_files if not getattr(test, f)]
    if missing:
        flash(f"Required files missing: {', '.join(missing)}", "danger")
        return redirect(url_for("manage_bp.manage_test_files", test_id=test.id))

    try:
        task = run_student_script_ocr_pipeline.delay(
            test.id,
            str(get_uploaded_file_path(test.combined_scripts_path)),
            str(get_uploaded_file_path(test.class_list_path))
        )
        logger.info(f"Preprocessing started for test_id={test.id}, task_id={task.id}")

        control = TaskControl(task_id=str(task.id), status="RUNNING", test_id=test.id)
        db.session.add(control)
        db.session.commit()

        flash("Preprocessing started. You will be notified upon completion.", "success")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error starting preprocessing for test_id={test.id}: {e}")
        flash("Error starting preprocessing. Please try again.", "danger")

    return redirect(url_for("manage_bp.manage_test_files", test_id=test.id))



# ---------------- Task Status ----------------
@manage_bp.route("/task_status/<task_id>")
@login_required
def task_status(task_id):
    result = AsyncResult(task_id)
    response = {"state": result.state, "progress": getattr(result.info, "get", lambda k, d: 0)("percent", 0)}
    if result.state == "SUCCESS":
        response["progress"] = 100
        response["state"] = "COMPLETED"
    elif result.state in ("FAILURE", "REVOKED"):
        response["progress"] = 0
    return jsonify(response)
