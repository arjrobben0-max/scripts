# smartscripts/utils/history_logger.py

import os
import logging
from datetime import datetime
from flask import current_app
from flask_login import current_user
from smartscripts.utils.file_helpers import get_submission_dir

# -------------------------------
# Logger Setup
# -------------------------------

logger = logging.getLogger("history_logger")
logger.setLevel(logging.INFO)

if not logger.hasHandlers():
    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)


# -------------------------------
# OCR Logging
# -------------------------------

def log_ocr_result(
    test_id: int, student_id: str, page_num: int, ocr_name: str, confidence: float
) -> None:
    """
    Save OCR results for review per student.
    Logs stored in: <submissions>/<student_id>/logs/<student_id>_ocr.log
    """
    log_dir = get_submission_dir(test_id, student_id) / "logs"
    ensure_folder_exists(log_dir)
    log_file = log_dir / f"{student_id}_ocr.log"

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"Page {page_num}: {ocr_name} (confidence={confidence})\n")

    logger.info(f"Logged OCR result: {student_id} page {page_num} using {ocr_name}")


# -------------------------------
# Manual Override Logging
# -------------------------------

def log_manual_override(action: str, student_id: str, override_details: dict) -> None:
    """
    Log a manual override action by a teacher with timestamp and user info.

    :param action: Description of the action performed (e.g., 'score adjusted').
    :param student_id: ID of the student whose marks were overridden.
    :param override_details: Details of the override (old score, new score, reason, etc.)
    """
    user_id = getattr(current_user, "id", "anonymous")
    username = getattr(current_user, "username", "anonymous")

    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "username": username,
        "action": action,
        "student_id": student_id,
        "details": override_details,
    }

    logger.info(f"Manual Override: {log_entry}")


def log_override_change(
    user_id: str,
    student_id: str,
    field: str,
    old_value: str,
    new_value: str,
    timestamp: datetime = None,
) -> None:
    """
    Logs who changed what in the override history.
    """
    timestamp = timestamp or datetime.utcnow()
    log_entry = (
        f"[OVERRIDE] {timestamp.isoformat()} - User {user_id} changed {field} "
        f"for student {student_id} from '{old_value}' to '{new_value}'"
    )
    logger.info(log_entry)
