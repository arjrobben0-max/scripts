"""
smartscripts/tasks/matching_tasks.py
------------------------------------
Fuzzy Matching Tasks
 - Match OCR IDs/names against class_list.csv
 - Updates OCRSubmission objects
 - Generates presence table CSV
 - Supports pause/resume/cancel via TaskControl
"""

import logging
import time
from pathlib import Path
import pandas as pd
from rapidfuzz import process, fuzz
from flask import current_app, has_app_context

from smartscripts.extensions import celery, db

logger = logging.getLogger(__name__)

# ------------------------------------------------------
# Fuzzy Matching Task
# ------------------------------------------------------
@celery.task(bind=True, name="smartscripts.tasks.matching_tasks.fuzzy_match_class_list")
def fuzzy_match_class_list(self, ocr_output: dict, test_id: int, class_list_path: str):
    """
    Step 3: Match OCR IDs/names against class_list.csv using fuzzy string matching.
    Updates OCRSubmission + returns presence table.
    Supports pause/resume/cancel via TaskControl.
    """
    if not has_app_context():
        from smartscripts.app import create_app
        app = create_app("production")
        with app.app_context():
            return _run_matching_task(self, ocr_output, test_id, class_list_path)
    else:
        return _run_matching_task(self, ocr_output, test_id, class_list_path)


def _run_matching_task(self, ocr_output: dict, test_id: int, class_list_path: str):
    from smartscripts.models.ocr_submission import OCRSubmission
    from smartscripts.models.submission_manifest import SubmissionManifest
    from smartscripts.models.task_control import TaskControl

    task_id = self.request.id
    current_app.logger.info(f"[Matching] Task {task_id} started for test {test_id}")

    # Create or get TaskControl record
    db_state = TaskControl.query.filter_by(task_id=task_id).first()
    if not db_state:
        db_state = TaskControl(task_id=task_id, test_id=test_id, status="RUNNING")
        db.session.add(db_state)
        db.session.commit()

    results = []

    try:
        class_df = pd.read_csv(class_list_path)
        ocr_results = ocr_output.get("ocr_results", [])
        total = len(ocr_results)

        for i, res in enumerate(ocr_results, start=1):
            db.session.refresh(db_state)

            # -------------------
            # Cancel check
            # -------------------
            if db_state.status == "CANCELLED":
                self.update_state(state="REVOKED")
                current_app.logger.warning(f"[Matching] Task {task_id} cancelled at {i}/{total}")
                db_state.status = "CANCELLED"
                db.session.commit()
                return {
                    "status": "CANCELLED",
                    "task_id": task_id,
                    "test_id": test_id,
                    "current": i,
                    "total": total,
                    "percent": int(i / total * 100),
                    "message": "Task cancelled by user.",
                }

            # -------------------
            # Pause check
            # -------------------
            while db_state.status == "PAUSED":
                current_app.logger.info(f"[Matching] Task {task_id} paused at {i}/{total}")
                time.sleep(2)
                db.session.refresh(db_state)

            # -------------------
            # Fuzzy match ID and name
            # -------------------
            ocr_id = str(res.get("ocr_id", "")).strip()
            ocr_name = str(res.get("ocr_name", "")).strip()

            best_match_id = process.extractOne(
                ocr_id, class_df["student_id"], scorer=fuzz.ratio
            )
            best_match_name = process.extractOne(
                ocr_name, class_df["name"], scorer=fuzz.token_sort_ratio
            )

            matched = False
            matched_id = None
            matched_name = None
            confidence = 0

            if best_match_id and best_match_id[1] > 80:
                matched = True
                matched_id = best_match_id[0]
                confidence = best_match_id[1]
                matched_row = class_df[class_df["student_id"] == matched_id].iloc[0]
                matched_name = matched_row["name"]

            elif best_match_name and best_match_name[1] > 80:
                matched = True
                matched_name = best_match_name[0]
                confidence = best_match_name[1]
                matched_row = class_df[class_df["name"] == matched_name].iloc[0]
                matched_id = matched_row["student_id"]

            results.append({
                "ocr_id": ocr_id,
                "ocr_name": ocr_name,
                "matched_id": matched_id,
                "matched_name": matched_name,
                "confidence": confidence,
                "matched": matched,
            })

            # -------------------
            # Update OCRSubmission
            # -------------------
            sub = OCRSubmission.query.filter_by(id=res.get("submission_id")).first()
            if sub:
                sub.corrected_id = matched_id
                sub.corrected_name = matched_name
                sub.confidence = confidence
                sub.needs_human_review = not matched or confidence < 85
                db.session.add(sub)

            # -------------------
            # Progress update
            # -------------------
            percent = int(i / total * 100)
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": i,
                    "total": total,
                    "percent": percent,
                    "test_id": test_id,
                    "task_id": task_id,
                },
            )

        # -------------------
        # Commit DB & generate presence table CSV
        # -------------------
        db.session.commit()

        manifest = SubmissionManifest.query.filter_by(test_id=test_id).first()
        if manifest:
            Path("presence_tables").mkdir(exist_ok=True)
            manifest.presence_table_path = f"presence_tables/test_{test_id}_presence.csv"
            pd.DataFrame(results).to_csv(manifest.presence_table_path, index=False)
            db.session.commit()

        db_state.status = "COMPLETED"
        db.session.commit()

        current_app.logger.info(f"[Matching] ✅ Completed fuzzy match for test {test_id}")
        return {"status": "COMPLETED", "test_id": test_id, "presence_table": results}

    except Exception as e:
        db.session.rollback()
        db_state.status = "FAILED"
        db.session.commit()
        current_app.logger.exception(f"[Matching] ❌ Failed for test {test_id}: {e}")
        return {"status": "FAILED", "test_id": test_id, "error": str(e)}
