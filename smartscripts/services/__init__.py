"""
smartscripts.services
---------------------
Initialization for core service utilities.
Avoid importing API or AI layers here to prevent circular imports.
"""

# Overlay & Review
from smartscripts.services.overlay_service import add_overlay
from smartscripts.services.review_service import (
    get_review_history,
    get_latest_override,
    process_teacher_review,
    override_diff
)

# Analytics
from smartscripts.services.analytics_service import (
    compute_success_rates,
    aggregate_feedback,
    compute_average_score,
)
from smartscripts.services.ocr_utils import generate_review_zip

# Feedback / Reports / PDF
try:
    from smartscripts.services.feedback_service import save_feedback
except ModuleNotFoundError:
    save_feedback = None

try:
    from smartscripts.services.pdf_service import generate_pdf
except ModuleNotFoundError:
    generate_pdf = None

try:
    from smartscripts.services.report_service import generate_report
except ModuleNotFoundError:
    generate_report = None

# Marksheet / Results export
from smartscripts.services.marksheet_export_service import export_student_results

# File management
from smartscripts.services.file_manager import save_uploaded_file, get_file_url

# Attendance / Presence
from smartscripts.services.attendance_service import update_attendance, generate_presence_csv

# Bulk upload / PDF splitting
from smartscripts.services.bulk_upload_service import handle_bulk_upload

# Export / Overrides
from smartscripts.services.export_service import (
    export_submissions_to_csv,
    export_submissions_to_pdf,
    export_student_zip,
    export_override_csv,
    export_grading_results,
)

__all__ = [
    # Overlay & Review
    "add_overlay",
    "get_review_history",
    "get_latest_override",
    "process_teacher_review",
    "override_diff",
    "generate_review_zip",

    # Analytics
    "compute_success_rates",
    "aggregate_feedback",
    "compute_average_score",

    # Feedback / Reports / PDF
    "save_feedback",
    "generate_pdf",
    "generate_report",

    # Marksheet / Results export
    "export_student_results",

    # File management
    "save_uploaded_file",
    "get_file_url",

    # Attendance / Presence
    "update_attendance",
    "generate_presence_csv",

    # Bulk upload
    "handle_bulk_upload",

    # Export / Overrides
    "export_submissions_to_csv",
    "export_submissions_to_pdf",
    "export_student_zip",
    "export_override_csv",
    "export_grading_results",
]
