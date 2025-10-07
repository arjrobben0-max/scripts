import os
from pathlib import Path
from flask import Blueprint, flash, url_for, abort, current_app, send_file, redirect
from flask_login import login_required, current_user

from smartscripts.models import MarkingGuide
from smartscripts.services.export_service import (
    export_submissions_to_csv,
    export_submissions_to_pdf,
)

# Define Blueprint
export_bp = Blueprint("export_bp", __name__, url_prefix="/export")


@export_bp.route("/<int:guide_id>/<string:format>")
@login_required
def export_submissions(guide_id, format):
    """
    Export all student submissions for a marking guide as CSV or PDF.
    Files are stored under:
        smartscripts/app/static/uploads/<test_id>/exports/
    """
    guide = MarkingGuide.query.get_or_404(guide_id)

    # Only the owner teacher or admins can export
    if guide.teacher_id != current_user.id and not current_user.is_admin:
        abort(403)

    try:
        # Generate export file
        if format == "csv":
            file_path = export_submissions_to_csv(guide)
        elif format == "pdf":
            file_path = export_submissions_to_pdf(guide)
        else:
            flash("❌ Unsupported export format.", "warning")
            return redirect(url_for("teacher_bp.teacher_dashboard"))

        # Ensure file exists
        if not os.path.exists(file_path):
            current_app.logger.error(f"[Export Missing] File not found: {file_path}")
            flash("Export failed: File not found.", "danger")
            return redirect(url_for("teacher_bp.teacher_dashboard"))

        # Send file for download
        return send_file(file_path, as_attachment=True)

    except Exception as e:
        current_app.logger.exception(
            f"[Export Error] Failed export ({format.upper()}) for guide {guide_id}: {str(e)}"
        )
        flash(f"❌ Failed to export as {format.upper()}. Please try again.", "danger")
        return redirect(url_for("teacher_bp.teacher_dashboard"))
