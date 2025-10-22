"""
Review Tasks
-------------
- Generate review ZIP (PDFs + logs + presence table) using canonical generate_review_zip
- Updates SubmissionManifest
- Supports pause/resume/cancel via TaskControl
"""

import logging
import csv
import time
from pathlib import Path
from flask import current_app

from smartscripts.extensions import db, celery
from smartscripts.models.submission_manifest import SubmissionManifest
from smartscripts.models.task_control import TaskControl
from smartscripts.services.analytics_service import generate_review_zip as canonical_generate_review_zip

logger = logging.getLogger(__name__)


@celery.task(bind=True, name="smartscripts.tasks.review_tasks.generate_review_zip")
def generate_review_zip_task(self, match_output: dict, test_id: int):
    """
    Generate review ZIP for a test using canonical generate_review_zip.
    - Includes PDFs + presence table CSV + JSON logs
    - Updates SubmissionManifest.review_zip_path and review_ready
    - Supports pause/resume/cancel
    """
    task_id = self.request.id
    logger.info(f"[Review] Task {task_id} started for test {test_id}")

    # --- Create or get TaskControl ---
    db_state = TaskControl.query.filter_by(task_id=task_id).first()
    if not db_state:
        db_state = TaskControl(task_id=task_id, test_id=test_id, status="RUNNING")
        db.session.add(db_state)
        db.session.commit()

    try:
        Path("review_exports").mkdir(exist_ok=True)
        zip_path = Path(f"review_exports/test_{test_id}_review.zip")

        per_student_files = match_output.get("extracted_student_scripts", [])
        presence_csv_path = match_output.get("presence_csv_path")
        extra_files = match_output.get("extra_files", [])

        # --- Load presence table if available ---
        presence_rows = []
        if presence_csv_path and Path(presence_csv_path).exists():
            with open(presence_csv_path, newline='', encoding='utf-8') as f:
                presence_rows = list(csv.DictReader(f))

        # --- Simulate progress with pause/resume/cancel support ---
        total_steps = 3
        for step in range(1, total_steps + 1):
            db.session.refresh(db_state)

            # Handle cancel
            if db_state.status == "CANCELLED":
                logger.warning(f"[Review] Task {task_id} cancelled at step {step}")
                db_state.status = "CANCELLED"
                db.session.commit()
                self.update_state(state="REVOKED")
                return {"status": "CANCELLED", "task_id": task_id, "test_id": test_id}

            # Handle pause
            while db_state.status == "PAUSED":
                logger.info(f"[Review] Task {task_id} paused at step {step}")
                time.sleep(2)
                db.session.refresh(db_state)

            # Update progress
            percent = int(step / total_steps * 100)
            self.update_state(state="PROGRESS", meta={"percent": percent})
            time.sleep(1)

        # --- Generate the ZIP ---
        canonical_generate_review_zip(
            per_student_files=per_student_files,
            presence_rows=presence_rows,
            zip_path=str(zip_path),
            extra_files=extra_files
        )

        # --- Update SubmissionManifest ---
        manifest = SubmissionManifest.query.filter_by(test_id=test_id).first()
        if manifest:
            manifest.review_zip_path = str(zip_path)
            manifest.review_ready = True
            db.session.commit()

        # --- Mark as completed ---
        db_state.status = "COMPLETED"
        db.session.commit()

        logger.info(f"[Review] Task {task_id} COMPLETED for test {test_id}")
        return {
            "status": "COMPLETED",
            "task_id": task_id,
            "test_id": test_id,
            "review_zip": str(zip_path),
            "percent": 100,
            "message": "Review ZIP generated successfully.",
        }

    except Exception as e:
        db.session.rollback()
        db_state.status = "FAILED"
        db.session.commit()
        logger.exception(f"[Review] Task {task_id} FAILED for test {test_id}: {e}")
        return {
            "status": "FAILED",
            "test_id": test_id,
            "task_id": task_id,
            "error": str(e),
        }
