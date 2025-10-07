import os
from pathlib import Path
from flask import (
    render_template, request, redirect, url_for, flash,
    abort, current_app, send_file
)
from flask_login import login_required

from smartscripts.extensions import db
from smartscripts.models import Test, MarkingGuide
from smartscripts.models.extracted_student_script import ExtractedStudentScript

from . import review_bp
from .utils import file_url, is_teacher_or_admin, get_urls_for_guide

# ✅ Corrected imports: use the ocr_pipeline functions
from smartscripts.services.ocr_pipeline import generate_presence_csv, generate_review_zip



# -------------------------------
# Review test dashboard
# -------------------------------
@review_bp.route('/review_test/<int:test_id>')
@login_required
def review_test(test_id: int):
    test = Test.query.get_or_404(test_id)
    if not is_teacher_or_admin(test):
        abort(403)

    guide = MarkingGuide.query.filter_by(test_id=test.id).first()
    student_scripts = ExtractedStudentScript.query.filter_by(test_id=test.id).all()
    urls = get_urls_for_guide(guide)

    # attach file URLs to each script
    for s in student_scripts:
        s.file_url = file_url(s.extracted_pdf_path)

    sections = [
        {'title': '📄 Marking Guide', 'uploaded': bool(urls.get("guide")), 'review_url': urls.get("guide")},
        {'title': '📊 Rubric', 'uploaded': bool(urls.get("rubric")), 'review_url': urls.get("rubric")},
        {'title': '✏️ Answered Script', 'uploaded': bool(urls.get("answered")), 'review_url': urls.get("answered")},
        {'title': '👩‍🎓 Student Scripts', 'uploaded': bool(student_scripts),
         'review_url': url_for('teacher_bp.review_bp.review_extracted_student_list', test_id=test.id)},
    ]

    return render_template('teacher/review_test.html',
                           test=test,
                           guide=guide,
                           file_guide_url=urls.get('guide'),
                           file_rubric_url=urls.get('rubric'),
                           answered_script_url=urls.get('answered'),
                           student_scripts=student_scripts,
                           student_scripts_exist=bool(student_scripts),
                           sections=sections)


# -------------------------------
# Review extracted student list
# -------------------------------
@review_bp.route('/review_extracted_student_list/<int:test_id>', methods=['GET', 'POST'])
@login_required
def review_extracted_student_list(test_id: int):
    test = Test.query.get_or_404(test_id)
    if not is_teacher_or_admin(test):
        abort(403)

    scripts = ExtractedStudentScript.query.filter_by(test_id=test_id).all()

    if request.method == 'POST':
        for s in scripts:
            prefix = f"script_{s.id}_"
            name_val = request.form.get(prefix + "student_name")
            id_val = request.form.get(prefix + "matched_id")
            confirmed_val = request.form.get(prefix + "confirmed") == "on"

            if name_val:
                s.student_name = name_val.strip()
            if id_val:
                s.matched_id = id_val.strip()
            s.is_confirmed = confirmed_val

        try:
            db.session.commit()
            flash("✅ Extracted student list updated successfully.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Failed to update list: {e}", "danger")
        return redirect(url_for('teacher_bp.review_bp.review_extracted_student_list', test_id=test_id))

    return render_template('teacher/review_extracted_student_list.html',
                           test=test,
                           extracted_student_scripts=scripts)


# -------------------------------
# Serve individual student PDF
# -------------------------------
@review_bp.route('/review/student_pdf/<int:script_id>')
@login_required
def review_student_pdf(script_id: int):
    script = ExtractedStudentScript.query.get_or_404(script_id)
    test = script.test
    if not test or not is_teacher_or_admin(test):
        abort(403)

    full_path = Path(current_app.root_path) / 'static' / 'uploads' / script.extracted_pdf_path
    if not full_path.exists():
        flash(f"File not found: {script.extracted_pdf_path}", "warning")
        return redirect(url_for('teacher_bp.review_bp.review_test', test_id=test.id))

    return send_file(full_path)


# -------------------------------
# Generate review ZIP
# -------------------------------
@review_bp.route('/generate_review_zip/<int:test_id>')
@login_required
def generate_review_package(test_id: int):
    test = Test.query.get_or_404(test_id)
    if not is_teacher_or_admin(test):
        abort(403)

    scripts = ExtractedStudentScript.query.filter_by(test_id=test_id).all()
    present = [s for s in scripts if s.is_confirmed]
    absent = [s for s in scripts if not s.is_confirmed]

    upload_dir = Path(current_app.root_path) / "static" / "uploads" / str(test_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    presence_csv = generate_presence_csv(
        [{"name": s.student_name, "id": s.matched_id, "confidence": s.confidence} for s in present],
        [{"name": s.student_name, "id": s.matched_id, "confidence": s.confidence} for s in absent],
        test_id,
        upload_dir
    )

    zip_path = generate_review_zip(scripts, presence_csv, upload_dir)

    return send_file(zip_path, as_attachment=True)


# -------------------------------
# File viewer/download
# -------------------------------
def get_abs_path(relative_path: str) -> str:
    return os.path.join(current_app.config['UPLOAD_FOLDER'], relative_path)


@review_bp.route('/review/<file_type>/<int:test_id>')
@login_required
def review_file(file_type, test_id):
    test = Test.query.get_or_404(test_id)
    if not is_teacher_or_admin(test):
        abort(403)

    file_map = {
        "question_paper": test.question_paper_path,
        "rubric": test.rubric_path,
        "marking_guide": test.marking_guide_path,
        "answered_script": test.answered_script_path,
        "combined_scripts": test.combined_scripts_path,
        "class_list": test.class_list_path,
    }

    if file_type not in file_map or not file_map[file_type]:
        flash(f"{file_type.replace('_', ' ').title()} not available.", "warning")
        return redirect(url_for("upload_bp.upload_test_materials", test_id=test_id))

    full_path = get_abs_path(file_map[file_type])
    if not os.path.exists(full_path):
        flash(f"File not found: {full_path}", "warning")
        return redirect(url_for("upload_bp.upload_test_materials", test_id=test_id))

    return send_file(full_path)
