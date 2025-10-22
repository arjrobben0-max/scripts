import uuid
import os
from pathlib import Path
from typing import Optional

from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, current_app
)
from flask_login import login_required, current_user

from smartscripts.extensions import db
from smartscripts.models import Test
from smartscripts.app.forms import TestForm
from smartscripts.utils.file_helpers import save_file, allowed_file, save_and_parse_class_list
from smartscripts.config import BaseConfig
from smartscripts.services.bulk_upload_service import (
    preprocess_student_submissions,
    store_attendance_records,
)

# -----------------------
# Blueprint Setup
# -----------------------

upload_bp = Blueprint("upload_bp", __name__)

# ✅ Updated: folder_attr set to None since save_file handles folders automatically
UPLOAD_MAP = {
    "question_paper": ("question_paper_path", None),
    "rubric": ("rubric_path", None),
    "marking_guide": ("marking_guide_path", None),
    "answered_script": ("answered_script_path", None),
    "class_list": ("class_list_path", None),
    "combined_scripts": ("combined_scripts_path", None),
}

# -----------------------
# Create Test + Upload in One Step
# -----------------------
@upload_bp.route("/create_test", methods=["GET", "POST"])
@login_required
def create_test():
    """Teacher creates a new test and uploads all associated files in one go."""
    form = TestForm()

    if form.validate_on_submit():
        try:
            # 1️⃣ Create test record
            new_test = Test(
                title=form.test_title.data,
                subject=form.subject.data,
                grade_level=form.grade_level.data,
                exam_date=form.exam_date.data,
                description=form.description.data,
                teacher_id=current_user.id,
            )
            db.session.add(new_test)
            db.session.commit()

            # 🚫 REMOVE THIS (conflicts with save_file):
            # BaseConfig.init_upload_dirs(test_id=str(new_test.id))

            # 2️⃣ Save uploaded files
            saved_paths = {}
            for field, (model_field, _) in UPLOAD_MAP.items():
                file = getattr(form, field).data
                if not file:
                    continue

                rel_path = save_file(file, field, new_test.id)
                if rel_path:
                    setattr(new_test, model_field, rel_path)
                    saved_paths[field] = rel_path

            db.session.commit()

            # 3️⃣ Optional: handle combined scripts preprocessing
            if "combined_scripts" in saved_paths:
                combined_path = Path(current_app.static_folder) / saved_paths["combined_scripts"]

                if not getattr(new_test, "class_list_path", None):
                    flash("Please upload a class list before preprocessing combined scripts.", "warning")
                else:
                    class_list_path = Path(current_app.static_folder) / new_test.class_list_path
                    class_list = save_and_parse_class_list(class_list_path, new_test.id)

                    result = preprocess_student_submissions(
                        combined_pdf_path=combined_path,
                        test_id=new_test.id,
                        class_list=class_list,
                    )

                    matched_ids = {s["student_id"] for s in result["attendance"]["present"]}
                    store_attendance_records(new_test.id, class_list, matched_ids)

                    flash("AI preprocessing complete: scripts split & attendance recorded.", "success")

            flash("✅ Test created and files uploaded successfully!", "success")
            return redirect(url_for("dashboard_bp.dashboard"))

        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("❌ Test creation or upload failed")
            flash(f"Error creating test or uploading files: {e}", "danger")
            return redirect(url_for("upload_bp.create_test"))

    return render_template("teacher/create_test.html", form=form)

# -----------------------
# Fallback: Upload Extra Files for Existing Test
# -----------------------

@upload_bp.route("/upload/<int:test_id>", methods=["GET", "POST"])
@login_required
def upload_file(test_id: int):
    """Used only when teacher wants to add or replace files for an existing test."""
    test = Test.query.get_or_404(test_id)
    form = TestForm()  # Reuse TestForm for consistent validation

    if request.method == "POST" and form.validate_on_submit():
        try:
            for field, (model_field, _) in UPLOAD_MAP.items():  # folder_attr ignored
                file = getattr(form, field).data
                if not file or not allowed_file(file.filename):
                    continue

                # Save the file using the correct file_type
                rel_path = save_file(file, field, test.id)
                setattr(test, model_field, rel_path)

            db.session.commit()
            flash("Files updated successfully!", "success")
            return redirect(url_for("dashboard_bp.dashboard"))

        except Exception as e:
            db.session.rollback()
            current_app.logger.exception("❌ File upload failed")
            flash(f"Error uploading files: {e}", "danger")
            return redirect(url_for("upload_bp.upload_file", test_id=test_id))

    return render_template("teacher/upload_test_materials.html", form=form, test=test)
