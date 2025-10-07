from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from flask import current_app
import logging

from smartscripts.models import StudentSubmission, ExtractedStudentScript
from smartscripts.extensions import db
from smartscripts.services.student_preprocessing import preprocess_student_submissions
from smartscripts.utils.file_helpers import get_submission_dir
from smartscripts.models.attendance import AttendanceRecord
from typing import List, Dict, Set

logger = logging.getLogger(__name__)


# -------------------------------
# Bulk PDF Upload & Preprocessing
# -------------------------------
def handle_bulk_upload(
    combined_pdf_path: Union[str, Path],
    test_id: int,
    guide_id: int,
    class_list: Optional[List[Dict[str, Any]]] = None,
    app=None
) -> Dict[str, Any]:
    """
    Handle bulk student submission upload:
    - Run preprocessing pipeline
    - Save StudentSubmission records
    - Trigger AI marking
    """
    if app is None:
        app = current_app

    combined_pdf_path = Path(combined_pdf_path)

    # Preprocessing pipeline
    result = preprocess_student_submissions(
        combined_pdf_path=combined_pdf_path,
        test_id=test_id,
        class_list=class_list
    )

    extracted_scripts: List[ExtractedStudentScript] = result.get("extracted_student_script", [])

    for script in extracted_scripts:
        student_id = script.matched_id or script.ocr_student_id
        if not student_id:
            logger.warning("Skipped script with no matched or OCR student ID: %s", script.extracted_pdf_path)
            continue

        # Ensure submission directory exists
        submission_dir = Path(get_submission_dir(test_id, student_id))
        submission_dir.mkdir(parents=True, exist_ok=True)

        if script.extracted_pdf_path:
            extracted_pdf_path = Path(script.extracted_pdf_path)
        else:
            logger.warning("Skipped script with no PDF path: %s", getattr(script, "id", None))
            continue

        # Create submission using correct fields
        submission = StudentSubmission(
            test_id=test_id,
            student_id=int(student_id) if str(student_id).isdigit() else None,
            guide_id=guide_id,
            original_filename=extracted_pdf_path.name,
            extracted_filename=str(extracted_pdf_path),
            match_status="unmatched",
            review_status="pending",
        )
        db.session.add(submission)

    try:
        db.session.commit()
        logger.info("Bulk upload processed for test %d (%d submissions)", test_id, len(extracted_scripts))
    except Exception as e:
        db.session.rollback()
        logger.error("DB error during bulk upload: %s", e)

    # Trigger AI marking (lazy import)
    try:
        from smartscripts.ai.marking_adapter import start_ai_marking
        start_ai_marking(test_id=test_id)
        logger.info("AI marking triggered for test %d", test_id)
    except Exception as e:
        logger.error("AI marking failed for test %d: %s", test_id, e)

    return result


# -------------------------------
# Save uploaded batch & mark
# -------------------------------
def save_and_mark_batch(
    files: List[Any],
    test_id: int,
    guide_id: int
) -> List[StudentSubmission]:
    """
    Save uploaded files, create StudentSubmission records, and trigger AI marking.
    """
    saved_submissions: List[StudentSubmission] = []

    upload_dir = Path(current_app.config.get("UPLOAD_FOLDER", "uploads")) / "submissions" / str(test_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    for file in files:
        filename = getattr(file, "filename", None)
        if not filename:
            continue

        safe_filename = filename.replace(" ", "_")
        file_path = upload_dir / safe_filename
        file.save(file_path)

        student_id = safe_filename.rsplit(".", 1)[0]

        submission = StudentSubmission(
            test_id=test_id,
            student_id=int(student_id) if student_id.isdigit() else None,
            guide_id=guide_id,
            original_filename=file_path.name,
            extracted_filename=str(file_path),
            match_status="unmatched",
            review_status="pending"
        )
        db.session.add(submission)
        saved_submissions.append(submission)

    try:
        db.session.commit()
        logger.info("Saved %d submissions for test %d", len(saved_submissions), test_id)
    except Exception as e:
        db.session.rollback()
        logger.error("DB error saving batch submissions: %s", e)
        raise

    # Trigger AI marking
    try:
        from smartscripts.ai.marking_adapter import start_ai_marking
        start_ai_marking(test_id=test_id)
        logger.info("AI marking triggered for batch submissions of test %d", test_id)
    except Exception as e:
        logger.error("AI marking failed for test %d: %s", test_id, e)

    return saved_submissions

def store_attendance_records(test_id: int, class_list: List[Dict], present_ids: Set[str]) -> None:
    """
    Store attendance records for a test in the DB.

    :param test_id: ID of the test
    :param class_list: List of students, each as {"student_id": str, "name": str}
    :param present_ids: Set of student_ids who are present
    """
    try:
        for student in class_list:
            student_id = student["student_id"]
            name = student.get("name")
            present = student_id in present_ids

            record = AttendanceRecord(
                test_id=test_id,
                student_id=student_id,
                name=name,
                present=present
            )
            db.session.add(record)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise e