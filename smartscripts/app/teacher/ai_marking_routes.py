import os
from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    jsonify,
    abort,
    render_template,
    flash,
    redirect,
    url_for,
)
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError

from smartscripts.models import StudentSubmission, Test, AttendanceRecord
from smartscripts.extensions import db
from smartscripts.ai.marking_pipeline import (
    mark_batch_submissions,
    mark_single_submission,
)
from smartscripts.tasks.grade_tasks import async_mark_submission
from smartscripts.app.teacher.utils import get_file_path

ai_marking_bp = Blueprint("ai_marking_bp", __name__, url_prefix="/ai_marking")


def save_marked_image(submission, result):
    """Save annotated image from AI result to disk and update DB path."""
    image_data = result.get("annotated_image_bytes")
    if not image_data:
        current_app.logger.warning(
            f"[AI Marking] No annotated image for submission {submission.id}"
        )
        return None

    marked_dir = os.path.join(current_app.config["MARKED_FOLDER"], str(submission.id))
    os.makedirs(marked_dir, exist_ok=True)
    image_path = os.path.join(marked_dir, "annotated.png")

    try:
        with open(image_path, "wb") as f:
            f.write(image_data)

        submission.graded_image = image_path
        try:
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(
                f"[DB] Error saving graded image path: {e}", exc_info=True
            )
            flash("A database error occurred while saving the graded image.", "danger")
        return image_path
    except Exception as e:
        current_app.logger.error(
            f"[AI Marking] Failed to save marked image for submission {submission.id}: {e}"
        )
        return None


# ---------------- Batch AI Marking ----------------
@ai_marking_bp.route("/start_ai_marking/<int:test_id>", methods=["GET"])
@login_required
def start_ai_marking_form(test_id):
    """Render the AI marking page."""
    test = Test.query.get_or_404(test_id)
    if test.teacher_id != current_user.id and not current_user.is_admin:
        abort(403)
    return render_template("teacher/start_ai_marking.html", test=test)


@ai_marking_bp.route("/start_ai_marking/<int:test_id>", methods=["POST"])
@login_required
def start_ai_marking_batch(test_id):
    """Run synchronous AI marking for all submissions in a test."""
    test = Test.query.get_or_404(test_id)
    if test.teacher_id != current_user.id and not current_user.is_admin:
        return jsonify({"error": "Unauthorized access"}), 403

    try:
        submissions = StudentSubmission.query.filter_by(
            test_id=test.id, teacher_id=current_user.id
        ).all()

        if not submissions:
            return (
                jsonify({"error": "No student submissions found for this test."}),
                404,
            )

        results = mark_batch_submissions(submissions, test_id)
        for submission, result in zip(submissions, results):
            save_marked_image(submission, result)

        return jsonify(
            {"message": f"✅ AI marking completed for {len(submissions)} submissions."}
        )
    except Exception as e:
        current_app.logger.error(
            f"[AI Marking] Error during batch marking for test {test_id}: {e}",
            exc_info=True,
        )
        return jsonify({"error": str(e)}), 500


# ---------------- Single AI Marking ----------------
@ai_marking_bp.route(
    "/start_ai_marking/submission/<int:submission_id>", methods=["POST"]
)
@login_required
def start_ai_marking_single(submission_id):
    """Run AI marking for a single submission."""
    submission = StudentSubmission.query.get_or_404(submission_id)
    if submission.teacher_id != current_user.id:
        abort(403, "Unauthorized access")

    try:
        result = mark_single_submission(submission)
        save_marked_image(submission, result)
        return jsonify(
            {"message": f"✅ AI marking completed for submission ID {submission_id}."}
        )
    except Exception as e:
        current_app.logger.error(
            f"[AI Marking] Failed marking submission {submission_id}: {e}",
            exc_info=True,
        )
        return jsonify({"error": str(e)}), 500


# ---------------- Async AI Grading ----------------
@ai_marking_bp.route("/start_ai_grading/<int:test_id>", methods=["POST"])
@login_required
def start_ai_grading_async(test_id):
    """Asynchronously enqueue AI grading jobs using Celery."""
    test = Test.query.get_or_404(test_id)
    if test.teacher_id != current_user.id and not current_user.is_admin:
        return jsonify({"error": "Unauthorized access"}), 403

    if test.is_locked:
        return jsonify({"error": "This test is already locked for grading."}), 400

    submissions = StudentSubmission.query.filter_by(
        test_id=test.id, teacher_id=current_user.id
    ).all()

    if not submissions:
        return jsonify({"error": "No submissions found for this test"}), 404

    try:
        test.is_locked = True
        try:
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"[DB] Error locking test: {e}", exc_info=True)
            flash("Database error occurred while locking the test.", "danger")
            return jsonify({"error": "Database error while locking test."}), 500

        for submission in submissions:
            async_mark_submission.delay(
                submission.file_path,
                test.id,
                submission.student_id,
                test.id,
            )

        return jsonify(
            {"message": f"🚀 Async AI grading launched for {len(submissions)} submissions."}
        )
    except Exception as e:
        current_app.logger.error(
            f"[AI Marking] Async grading error for test {test_id}: {e}", exc_info=True
        )
        return jsonify({"error": str(e)}), 500


# ---------------- OCR Reprocess ----------------
@ai_marking_bp.route("/reprocess_ocr/<int:test_id>/<int:record_id>")
@login_required
def reprocess_ocr(test_id, record_id):
    """Re-run OCR on a single attendance record."""
    # ✅ Local import to break circular dependency
    from smartscripts.tasks.ocr_tasks import run_student_script_ocr_pipeline

    record = AttendanceRecord.query.get_or_404(record_id)

    if not record.pdf_path:
        flash("PDF path not found.", "danger")
        return redirect(url_for("review.review_test", test_id=test_id))

    abs_path = get_file_path(record.pdf_path, file_type="pdf")
    if not abs_path.exists():
        flash("PDF file missing on disk.", "danger")
        return redirect(url_for("review.review_test", test_id=test_id))

    try:
        result = run_student_script_ocr_pipeline.delay(test_id)
        record.ocr_task_id = result.id
        db.session.commit()
        flash("OCR reprocessing task launched successfully.", "success")
    except Exception as e:
        current_app.logger.error(f"OCR reprocessing failed: {e}", exc_info=True)
        flash(f"OCR reprocessing failed: {e}", "danger")

    return redirect(url_for("review.review_test", test_id=test_id))
