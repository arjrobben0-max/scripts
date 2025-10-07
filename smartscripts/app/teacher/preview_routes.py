import os
import logging
from flask import Blueprint, abort, send_file, render_template, current_app
from flask_login import login_required, current_user

from smartscripts.models import Test
from smartscripts.app.forms import (
    BulkOverrideUploadForm,
)  # still needed for bulk_review

preview_bp = Blueprint("preview_bp", __name__, url_prefix="/preview")
logger = logging.getLogger(__name__)


def _check_test_ownership(test):
    """Ensure only the test owner or an admin can access."""
    if test.teacher_id != current_user.id and not current_user.is_admin:
        abort(403)


@preview_bp.route("/file/<file_type>/<int:test_id>")
@login_required
def preview_file(file_type, test_id):
    test = Test.query.get_or_404(test_id)
    _check_test_ownership(test)

    # Map file_type to model attributes
    file_map = {
        "question_paper": test.question_paper_path,
        "rubric": test.rubric_path,
        "marking_guide": test.marking_guide_path,
        "answered_script": test.answered_script_path,
        "class_list": test.class_list_path,
        "combined_scripts": test.combined_scripts_path,
    }

    file_path = file_map.get(file_type)
    if not file_path or not os.path.isfile(file_path):
        logger.warning(
            f"Preview requested but file not found: {file_type} for test {test_id}"
        )
        abort(404)

    # Show file inline (browser preview for PDFs, images, etc.)
    return send_file(file_path, as_attachment=False)


@preview_bp.route("/bulk_review/<int:test_id>", methods=["GET"])
@login_required
def bulk_review(test_id):
    test = Test.query.get_or_404(test_id)
    _check_test_ownership(test)

    form = BulkOverrideUploadForm()
    return render_template("review_bulk.html", test=test, form=form)
