from flask import (
    render_template,
    redirect,
    url_for,
    flash,
    request,
    current_app,
    send_file,
    Blueprint,
)
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError

from smartscripts.utils.analytics_helpers import generate_pdf_report
from smartscripts.models import Test, GradedScript, TeacherReview
from smartscripts.extensions import db

# Blueprint registration
auth_bp = Blueprint("auth_bp", __name__)


@auth_bp.route("/")
def index():
    """Landing page for authentication blueprint."""
    return render_template("main/index.html")


@auth_bp.route("/download_report/<int:test_id>")
@login_required
def download_report(test_id: int):
    """Generate and download a PDF report for a given test."""
    test = Test.query.get_or_404(test_id)
    try:
        pdf_path = generate_pdf_report(test_id)
        return send_file(pdf_path, as_attachment=True)
    except Exception as e:
        current_app.logger.exception(f"Failed to generate report: {e}")
        flash("Could not generate report. Please try again later.", "danger")
        return redirect(url_for("auth_bp.index"))  # Corrected endpoint


@auth_bp.route("/review", methods=["GET"])
@login_required
def teacher_review():
    """View list of scripts to review for the logged-in teacher."""
    scripts = GradedScript.query.filter_by(teacher_id=current_user.id).all()
    return render_template("main/teacher_review.html", scripts=scripts)


@auth_bp.route("/review/submit", methods=["POST"])
@login_required
def submit_teacher_review():
    """Submit a teacher review for a script."""
    try:
        script_id = request.form.get("script_id")
        question_id = request.form.get("question_id") or ""
        original_text = request.form.get("original_text") or ""
        corrected_text = request.form.get("corrected_text") or ""

        if not all([script_id, question_id.strip(), original_text.strip(), corrected_text.strip()]):
            flash("All fields are required for review submission.", "danger")
            return redirect(url_for("auth_bp.teacher_review"))

        review = TeacherReview(
            script_id=script_id,
            question_id=str(question_id),
            original_text=str(original_text),
            corrected_text=str(corrected_text),
            reviewer_id=current_user.id,
            timestamp=db.func.current_timestamp(),
        )
        db.session.add(review)
        db.session.commit()
        flash("Review submitted successfully.", "success")

    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Database error during review: {e}")
        flash("A database error occurred. Please try again.", "danger")

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"Unexpected error: {e}")
        flash("An unexpected error occurred. Please try again.", "danger")

    return redirect(url_for("auth_bp.teacher_review"))
