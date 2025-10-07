import os
from pathlib import Path

from flask import Blueprint, jsonify, flash, redirect, url_for, abort, current_app
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError

from smartscripts.extensions import db
from smartscripts.models import (
    Test,
    MarkingGuide,
    StudentSubmission,
    ExtractedStudentScript,
)
from smartscripts.app.teacher.utils import (
    get_file_path,
    UPLOAD_FOLDERS,
    FILENAME_FIELDS,
)
from smartscripts.utils.utils import safe_remove

delete_bp = Blueprint("delete_bp", __name__, url_prefix="/delete")


def delete_submissions_for_guide(guide_id):
    """Helper to delete all submissions and their files for a marking guide."""
    submissions = StudentSubmission.query.filter_by(guide_id=guide_id).all()
    for submission in submissions:
        safe_remove(submission.file_path)
        db.session.delete(submission)


@delete_bp.route("/file/<int:test_id>/<file_type>", methods=["POST"])
@login_required
def delete_file(test_id, file_type):
    test = Test.query.get_or_404(test_id)

    if test.teacher_id != current_user.id and not current_user.is_admin:
        abort(403)

    if file_type not in FILENAME_FIELDS:
        flash("Invalid file type.", "danger")
        return redirect(url_for("upload_bp.upload_test_materials", test_id=test_id))

    filename = getattr(test, FILENAME_FIELDS[file_type])
    if not filename:
        flash("File not set.", "warning")
        return redirect(url_for("upload_bp.upload_test_materials", test_id=test_id))

    file_path = get_file_path(Path(UPLOAD_FOLDERS[file_type]) / str(test_id) / filename)
    if file_path.exists():
        try:
            file_path.unlink()
            setattr(test, FILENAME_FIELDS[file_type], None)
            db.session.commit()
            flash(
                f"ðŸ—‘ï¸ {file_type.replace('_', ' ').title()} deleted successfully.",
                "info",
            )
        except Exception as e:
            current_app.logger.error(f"Failed to delete file: {e}")
            flash(f"âŒ Deletion failed: {e}", "danger")
    else:
        flash("âš ï¸ File not found or already deleted.", "warning")

    return redirect(url_for("upload_bp.upload_test_materials", test_id=test_id))


@delete_bp.route("/delete_test/<int:test_id>", methods=["POST"])
@login_required
def delete_test(test_id):
    test = Test.query.get_or_404(test_id)

    if test.teacher_id != current_user.id and not current_user.is_admin:
        abort(403)

    try:
        # Delete related submissions for all marking guides of the test
        guide_ids = [
            mg.id for mg in MarkingGuide.query.filter_by(test_id=test.id).all()
        ]
        for guide_id in guide_ids:
            delete_submissions_for_guide(guide_id)

        # Delete marking guides and extracted scripts
        MarkingGuide.query.filter_by(test_id=test.id).delete(synchronize_session=False)
        ExtractedStudentScript.query.filter_by(test_id=test.id).delete(
            synchronize_session=False
        )

        # Delete the test itself
        db.session.delete(test)
        db.session.commit()

        flash("âœ… Test and all related data deleted successfully.", "success")
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"[DB ERROR] Failed to delete test {test_id}: {e}")
        flash("âŒ Database error while deleting test.", "danger")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"[ERROR] Unexpected error deleting test {test_id}: {e}"
        )
        flash("âŒ Unexpected error occurred.", "danger")

    return redirect(url_for("teacher_bp.dashboard_bp.dashboard"))


@delete_bp.route("/delete_all_submissions/<int:guide_id>", methods=["POST"])
@login_required
def delete_all_submissions(guide_id):
    guide = MarkingGuide.query.get_or_404(guide_id)

    if guide.teacher_id != current_user.id:
        abort(403)

    try:
        delete_submissions_for_guide(guide_id)
        db.session.commit()
        flash("âœ… All submissions deleted successfully.", "success")
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(
            f"[DB ERROR] While deleting submissions for guide {guide_id}: {e}"
        )
        flash("âŒ Database error occurred.", "danger")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"[ERROR] Failed to delete submissions for guide {guide_id}: {e}"
        )
        flash("âŒ Failed to delete submissions.", "danger")

    return redirect(url_for("teacher_bp.export_upload_guide_page"))


@delete_bp.route("/delete_guide/<int:guide_id>", methods=["POST"])
@login_required
def delete_marking_guide(guide_id):
    guide = MarkingGuide.query.get_or_404(guide_id)

    if guide.teacher_id != current_user.id:
        abort(403)

    try:
        delete_submissions_for_guide(guide_id)
        db.session.delete(guide)
        db.session.commit()
        flash("âœ… Marking guide and all associated submissions deleted.", "success")
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"[DB ERROR] While deleting guide {guide_id}: {e}")
        flash("âŒ Database error occurred.", "danger")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"[ERROR] Failed to delete guide {guide_id}: {e}")
        flash("âŒ Failed to delete guide.", "danger")

    return redirect(url_for("teacher_bp.export_upload_guide_page"))
