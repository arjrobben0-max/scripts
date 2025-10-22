# smartscripts/app/teacher/manage_routes.py
import logging
from pathlib import Path
from flask import (
    Blueprint, render_template, redirect, url_for, flash,
    abort, request, jsonify, send_from_directory
)
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from celery.result import AsyncResult

from smartscripts.extensions import db, celery
from smartscripts.models import Test
from smartscripts.models.task_control import TaskControl
from smartscripts.app.forms import (
    UploadFileForm, DeleteFileForm, PreprocessingForm, TestForm
)
from smartscripts.utils.file_helpers import save_file, get_uploaded_file_path
from smartscripts.tasks.ocr_tasks import run_student_script_ocr_pipeline

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

# ---------------- List / Create Tests ----------------
@manage_bp.route("/tests", methods=["GET", "POST"])
@login_required
def list_tests():
    form = TestForm()
    uploaded_tests = Test.query.filter_by(teacher_id=current_user.id).all()

    if form.validate_on_submit():
        try:
            new_test = Test(
                title=form.test_title.data,
                subject=form.subject.data,
                grade_level=form.grade_level.data,
                exam_date=form.exam_date.data,
                description=form.description.data,
                teacher_id=current_user.id,
            )
            db.session.add(new_test)
            db.session.flush()  # get ID before saving files

            # Save uploaded files
            files = {
                "question_paper": form.question_paper.data,
                "rubric": form.rubric.data,
                "marking_guide": form.marking_guide.data,
                "answered_script": form.answered_script.data,
                "class_list": form.class_list.data,
                "combined_scripts": form.combined_scripts.data,
            }

            for key, file in files.items():
                if file:
                    saved_path = save_file(file, key, new_test.id)
                    setattr(new_test, f"{key}_path", str(saved_path))
                    logger.info(f"Set {key}_path = {saved_path}")

            db.session.commit()
            flash("✅ Test created and files uploaded successfully.", "success")
            return redirect(url_for("manage_bp.list_tests"))

        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error while creating test: {e}")
            flash("Database error occurred. Please try again.", "danger")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Unexpected error: {e}")
            flash(f"Error during upload: {str(e)}", "danger")

    return render_template("teacher/dashboard.html", form=form, uploaded_tests=uploaded_tests)


# ---------------- Serve uploaded files ----------------
@manage_bp.route("/uploads/<path:relative_path>")
@login_required
def uploaded_file(relative_path):
    abs_path = get_uploaded_file_path(relative_path)
    if not abs_path.exists():
        abort(404)
    return send_from_directory(abs_path.parent, abs_path.name)


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

    # Generate file URLs if files exist
    file_urls = {}
    for key, _ in file_types:
        file_path = getattr(test, f"{key}_path", None)
        file_urls[key] = url_for(
            "manage_bp.uploaded_file", relative_path=file_path
        ) if file_path and get_uploaded_file_path(file_path).exists() else None

    return render_template(
        "teacher/manage_test_files.html",
        test=test,
        file_types=file_types,
        upload_forms=upload_forms,
        delete_forms=delete_forms,
        preprocessing_form=preprocessing_form,
        file_urls=file_urls
    )


# ---------------- Upload File ----------------
@manage_bp.route("/test/<int:test_id>/upload/<file_type>", methods=["POST"])
@login_required
def upload_file_route(test_id: int, file_type: str):
    form = UploadFileForm(prefix=file_type)
    if not form.validate_on_submit():
        flash(f"Validation failed: {form.errors}", "danger")
        return redirect(url_for("manage_bp.manage_test_files", test_id=test_id))

    if file_type not in ALLOWED_FILE_TYPES:
        flash("Invalid file type.", "danger")
        return redirect(url_for("manage_bp.manage_test_files", test_id=test_id))

    test = Test.query.get_or_404(test_id)
    if test.teacher_id != current_user.id and not current_user.is_admin:
        abort(403)

    try:
        old_path = getattr(test, f"{file_type}_path", None)
        if old_path:
            abs_old_path = get_uploaded_file_path(old_path)
            if abs_old_path.exists():
                abs_old_path.unlink()
                logger.info(f"Deleted old file: {abs_old_path}")

        saved_path = save_file(form.file.data, file_type, test.id)
        setattr(test, f"{file_type}_path", str(saved_path))
        db.session.commit()

        flash(f"{file_type.replace('_', ' ').title()} uploaded successfully.", "success")
        logger.info(f"Uploaded {file_type} for test_id={test.id}, path={saved_path}")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error uploading {file_type} for test_id={test.id}: {e}", exc_info=True)
        flash(f"Error uploading file: {e}", "danger")

    return redirect(url_for("manage_bp.manage_test_files", test_id=test.id))


# ---------------- Delete File ----------------
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
            get_uploaded_file_path(file_path).unlink(missing_ok=True)
            flash(f"{file_type.replace('_', ' ').title()} deleted successfully.", "success")
        except Exception as e:
            logger.error(f"Error deleting {file_type}: {e}")
            flash(f"Error deleting {file_type}.", "danger")
    else:
        flash("File does not exist or was already deleted.", "warning")

    setattr(test, f"{file_type}_path", None)
    db.session.commit()
    return redirect(url_for("manage_bp.manage_test_files", test_id=test.id))


# ---------------- Preprocessing ----------------
@manage_bp.route("/start_preprocessing/<int:test_id>", methods=["POST"])
@login_required
def start_preprocessing(test_id: int):
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
        task = run_student_script_ocr_pipeline.apply_async(
            args=[
                test.id,
                str(get_uploaded_file_path(test.combined_scripts_path)),
                str(get_uploaded_file_path(test.class_list_path))
            ]
        )

        test.ocr_task_id = task.id
        db.session.commit()

        control = TaskControl(task_id=str(task.id), status="RUNNING", test_id=test.id)
        db.session.add(control)
        db.session.commit()

        logger.info(f"Preprocessing started for test_id={test.id}, task_id={task.id}")
        flash("OCR preprocessing started.", "success")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error starting preprocessing for test_id={test.id}: {e}")
        flash("Error starting preprocessing. Please try again.", "danger")

    return redirect(url_for("manage_bp.manage_test_files", test_id=test.id))


# ---------------- Task Status ----------------
@manage_bp.route("/task_status/<task_id>")
@login_required
def task_status(task_id):
    """
    ✅ Use global Celery instance with result backend to avoid DisabledBackend errors
    """
    result = AsyncResult(task_id, app=celery)
    response = {
        "task_id": task_id,
        "state": result.state,
        "info": None
    }

    if result.state == "PENDING":
        response["info"] = "Task is pending."
    elif result.state == "STARTED":
        response["info"] = result.info or "Task started."
    elif result.state == "SUCCESS":
        response["info"] = result.result
        response["state"] = "COMPLETED"
    elif result.state in ("FAILURE", "REVOKED"):
        response["info"] = str(result.result)
    else:
        response["info"] = result.info

    return jsonify(response)


# ---------------- Pause / Resume / Cancel ----------------
@manage_bp.route("/pause_task/<task_id>", methods=["POST"])
@login_required
def pause_task(task_id):
    flash("Pause not implemented yet.", "warning")
    return redirect(request.referrer or url_for("manage_bp.list_tests"))


@manage_bp.route("/resume_task/<task_id>", methods=["POST"])
@login_required
def resume_task(task_id):
    flash("Resume not implemented yet.", "info")
    return redirect(request.referrer or url_for("manage_bp.list_tests"))


@manage_bp.route("/cancel_task/<task_id>", methods=["POST"])
@login_required
def cancel_task(task_id):
    celery.control.revoke(task_id, terminate=True)
    flash("Task canceled.", "danger")
    return redirect(request.referrer or url_for("manage_bp.list_tests"))
