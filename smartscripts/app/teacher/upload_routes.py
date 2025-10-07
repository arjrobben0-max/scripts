import uuid
from pathlib import Path
from typing import Optional
import os

from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, current_app
)
from flask_login import login_required, current_user

from smartscripts.extensions import db
from smartscripts.models import Test
from smartscripts.app.forms import UploadFileForm, CreateTestWithFilesForm
from smartscripts.utils.file_helpers import save_file, allowed_file, save_and_parse_class_list
from smartscripts.config import BaseConfig

from smartscripts.services.bulk_upload_service import (
    preprocess_student_submissions,
    store_attendance_records,
)

upload_bp = Blueprint("upload_bp", __name__)

UPLOAD_MAP = {
    "question_paper": ("question_paper_path", "QUESTION_PAPER_FOLDER"),
    "rubric": ("rubric_path", "RUBRIC_FOLDER"),
    "marking_guide": ("marking_guide_path", "MARKING_GUIDE_FOLDER"),
    "answered_script": ("answered_script_path", "ANSWERED_SCRIPTS_FOLDER"),
    "class_list": ("class_list_path", "CLASS_LISTS_FOLDER"),
    "combined_scripts": ("combined_scripts_path", "COMBINED_SCRIPTS_FOLDER"),
}


@upload_bp.route("/create_test", methods=["GET", "POST"])
@login_required
def create_test():
    form: CreateTestWithFilesForm = CreateTestWithFilesForm()
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Form validation failed", "danger")
            return redirect(url_for("upload_bp.create_test"))

        try:
            new_test = Test(
                title=getattr(form, "title", None).data,
                subject=getattr(form, "subject", None).data,
                grade_level=getattr(form, "grade_level", None).data,
                teacher_id=current_user.id,
            )
            db.session.add(new_test)
            db.session.commit()

            # Ensure upload directories exist
            BaseConfig.init_upload_dirs(test_id=str(new_test.id))  # type-safe

            flash("Test created successfully! Upload directories initialized.", "success")
            return redirect(url_for("dashboard_bp.dashboard"))

        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("Test creation failed")
            flash(f"Error creating test: {e}", "danger")
            return redirect(url_for("upload_bp.create_test"))

    return render_template("teacher/create_test.html", form=form)


@upload_bp.route("/upload/<int:test_id>", methods=["GET", "POST"])
@login_required
def upload_file(test_id: int):
    form: UploadFileForm = UploadFileForm()
    test: Test = Test.query.get_or_404(test_id)

    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Form validation failed", "danger")
            return redirect(url_for("upload_bp.upload_file", test_id=test_id))

        file = getattr(form, "file", None).data
        file_type: Optional[str] = getattr(form, "file_type", None).data

        if not file or not allowed_file(file.filename):
            flash("Invalid or unsupported file type", "danger")
            return redirect(url_for("upload_bp.upload_file", test_id=test_id))

        if file_type not in UPLOAD_MAP:
            flash("Unknown file type", "danger")
            return redirect(url_for("upload_bp.upload_file", test_id=test_id))

        try:
            model_field, folder_attr = UPLOAD_MAP[file_type]
            target_folder: str = getattr(current_app.config, folder_attr)

            rel_path: Optional[str] = save_file(file, target_folder, test.id)
            assert rel_path is not None  # type-safe

            setattr(test, model_field, rel_path)
            db.session.commit()

            flash(f"{file_type.replace('_', ' ').title()} uploaded successfully!", "success")

            # Trigger preprocessing for combined scripts
            if file_type == "combined_scripts":
                class_list_path: Optional[str] = getattr(test, "class_list_path", None)
                if not class_list_path:
                    flash("Class list CSV must be uploaded before preprocessing.", "warning")
                    return redirect(url_for("upload_bp.upload_file", test_id=test_id))

                # Type-safe paths
                class_list_full_path = Path(current_app.static_folder) / class_list_path
                class_list = save_and_parse_class_list(class_list_full_path, test.id)

                combined_pdf_full_path = Path(current_app.static_folder) / rel_path

                result = preprocess_student_submissions(
                    combined_pdf_path=combined_pdf_full_path,  # Path object
                    test_id=test.id,
                    class_list=class_list,
                )

                matched_ids = {s["student_id"] for s in result["attendance"]["present"]}
                store_attendance_records(test.id, class_list, matched_ids)

                flash(
                    "Student scripts preprocessing complete (front page detection, OCR, splitting, ZIP).",
                    "success"
                )

            return redirect(url_for("dashboard_bp.dashboard"))

        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("File upload or preprocessing failed")
            flash(f"Error uploading file or preprocessing: {e}", "danger")
            return redirect(url_for("upload_bp.upload_file", test_id=test_id))

    return render_template("teacher/upload_test_materials.html", form=form, test=test)
