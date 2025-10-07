# smartscripts/tasks/grading_tasks.py
"""
Asynchronous Grading Tasks
--------------------------
 - Single-student grading wrapper
 - Batch grading with Celery
 - Pause / Resume / Cancel support via TaskControl
"""

import time
import traceback
import logging
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from smartscripts.ai.marking_pipeline import mark_submission
from smartscripts.celery_app import celery
from smartscripts.extensions import db
from smartscripts.models.task_control import TaskControl

logger = logging.getLogger(__name__)


# ------------------------------------------------------
# Single Submission Grading (sync wrapper)
# ------------------------------------------------------
def async_mark_submission(
    file_path: str,
    guide_id: int,
    student_id: int,
    test_id: int,
    threshold: float = 0.75,
):
    """
    Run grading synchronously (can be queued by Celery).
    Wraps `mark_submission` with logging and error handling.
    """
    try:
        result = mark_submission(file_path, guide_id, student_id, test_id, threshold)
        logger.info(f"✅ Successfully graded student={student_id}, test={test_id}")
        return {
            "status": "COMPLETED",
            "student_id": student_id,
            "test_id": test_id,
            "result": result,
        }
    except Exception as e:
        logger.error(
            f"❌ Grading failed for student={student_id}, test={test_id}: {e}\n{traceback.format_exc()}"
        )
        raise


# ------------------------------------------------------
# Batch Grading Task (with pause/cancel)
# ------------------------------------------------------
@celery.task(bind=True, max_retries=3, default_retry_delay=10, name="async_grade_all_students")
def async_grade_all_students(self, test_id: int):
    """
    Celery task to grade all student scripts for a given test.
    Supports pause / resume / cancel via TaskControl table.
    Retries failed student scripts automatically.
    """
    from smartscripts.services.grading_service import grade_student_script
    from smartscripts.models import Test

    task_id = self.request.id
    start_time = time.time()

    # Create TaskControl record
    db_state = TaskControl(task_id=task_id, test_id=test_id, status="RUNNING")
    db.session.add(db_state)
    db.session.commit()

    try:
        test = Test.query.get(test_id)
        if not test:
            logger.error(f"❌ Test with ID {test_id} not found.")
            db_state.status = "FAILED"
            db.session.commit()
            return {"status": "FAILED", "message": f"Test {test_id} not found."}

        total_scripts = len(test.student_scripts)
        graded_count = 0
        failed_scripts = []

        for i, script in enumerate(test.student_scripts, start=1):
            db.session.refresh(db_state)

            # -------------------
            # Cancel check
            # -------------------
            if db_state.status == "CANCELLED":
                self.update_state(state="REVOKED")
                logger.warning(f"🚨 Task {task_id} cancelled at {i}/{total_scripts}")
                db_state.status = "CANCELLED"
                db.session.commit()
                return {
                    "status": "CANCELLED",
                    "task_id": task_id,
                    "test_id": test_id,
                    "current": i,
                    "total": total_scripts,
                    "percent": int(i / total_scripts * 100),
                    "duration": time.time() - start_time,
                    "message": "Task cancelled by user.",
                }

            # -------------------
            # Pause check
            # -------------------
            while db_state.status == "PAUSED":
                logger.info(f"⏸️ Task {task_id} paused at {i}/{total_scripts}")
                time.sleep(2)
                db.session.refresh(db_state)

            # -------------------
            # Grade student script
            # -------------------
            try:
                grade_student_script(script)
                graded_count += 1
            except Exception as e:
                logger.error(
                    f"⚠️ Error grading script {script.id} (student={script.student_id}) "
                    f"for test {test_id}: {e}"
                )
                failed_scripts.append(script.id)
                try:
                    raise self.retry(exc=e, countdown=15)
                except self.MaxRetriesExceededError:
                    logger.critical(
                        f"🚨 Max retries reached for script {script.id} in test {test_id}"
                    )

            # -------------------
            # Progress update
            # -------------------
            percent = int(i / total_scripts * 100)
            elapsed = time.time() - start_time
            avg_time = elapsed / i if i > 0 else 1
            remaining = (total_scripts - i) * avg_time

            self.update_state(
                state="PROGRESS",
                meta={
                    "status": "PROGRESS",
                    "task_id": task_id,
                    "test_id": test_id,
                    "current": i,
                    "total": total_scripts,
                    "percent": percent,
                    "eta_seconds": int(remaining),
                    "graded": graded_count,
                    "failed": failed_scripts,
                },
            )

        # -------------------
        # Completion
        # -------------------
        db.session.commit()
        db_state.status = "COMPLETED"
        db.session.commit()
        duration = time.time() - start_time
        logger.info(
            f"✅ Grading completed for test={test_id}. Success: {graded_count}/{total_scripts}, "
            f"Failed: {len(failed_scripts)}"
        )

        return {
            "status": "COMPLETED",
            "task_id": task_id,
            "test_id": test_id,
            "graded_scripts": graded_count,
            "failed_scripts": failed_scripts,
            "total_scripts": total_scripts,
            "duration": duration,
            "eta_seconds": 0,
            "message": "Grading completed successfully.",
        }

    except SQLAlchemyError as db_err:
        db.session.rollback()
        db_state.status = "FAILED"
        db.session.commit()
        logger.exception(f"❌ Database error during grading test {test_id}: {db_err}")
        return {"status": "FAILED", "message": "Database error"}

    except Exception as e:
        db.session.rollback()
        db_state.status = "FAILED"
        db.session.commit()
        logger.exception(f"❌ Unexpected error in async_grade_all_students: {e}")
        return {"status": "FAILED", "message": str(e)}
