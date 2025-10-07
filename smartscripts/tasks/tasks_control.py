"""
Task Control & Pipeline Orchestration
-------------------------------------
Centralized management for Celery pipelines:
 - OCR pipeline (detect, OCR, match, review ZIP)
 - Grading pipeline (mark student scripts)
 - TaskControl integration for pause/resume/cancel
 - Flask blueprint for HTTP endpoints
"""

import logging
from typing import Dict, Any
from flask import Blueprint, request, jsonify
from sqlalchemy.exc import SQLAlchemyError
from smartscripts.extensions import db
from smartscripts.models.task_control import TaskControl
from smartscripts.models.submission_manifest import SubmissionManifest
from celery.result import AsyncResult

# Import tasks (ignore Pylance for dynamic Celery tasks)
from smartscripts.tasks.ocr_tasks import run_student_script_ocr_pipeline  # type: ignore
from smartscripts.tasks.grade_tasks import async_grade_all_students  # type: ignore

# -------------------------------
# Logging
# -------------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# -------------------------------
# OCR & Grading Pipelines
# -------------------------------
def launch_ocr_pipeline(test_id: int, scripts_pdf_path: str, class_list_path: str) -> Dict[str, Any]:
    """
    Launches the full OCR pipeline:
    - Convert PDF to images
    - Detect front pages
    - Extract student IDs/names
    - Fuzzy match against class list
    - Generate review ZIP
    """
    try:
        # Run the full OCR pipeline as a single Celery task
        workflow: AsyncResult = run_student_script_ocr_pipeline.apply_async(
            args=[test_id, scripts_pdf_path, class_list_path]
        )

        # Create SubmissionManifest safely
        manifest: SubmissionManifest = SubmissionManifest()
        manifest.test_id = test_id
        setattr(manifest, "name", f"test_{test_id}_submission")  # safe for Pylance
        db.session.add(manifest)
        db.session.commit()

        # Create TaskControl entry
        tc: TaskControl = TaskControl(
            task_id=str(workflow.id),
            test_id=test_id,
            status="RUNNING"
        )
        db.session.add(tc)
        db.session.commit()

        logger.info(f"[Pipeline] OCR pipeline launched for test {test_id}, task={workflow.id}")
        return {"status": "STARTED", "task_id": workflow.id, "workflow_id": workflow.id, "test_id": test_id}

    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"[Pipeline] DB error launching OCR pipeline for test {test_id}: {e}")
        return {"status": "FAILED", "error": "DB error"}

    except Exception as e:
        logger.exception(f"[Pipeline] Unexpected error launching OCR pipeline for test {test_id}: {e}")
        return {"status": "FAILED", "error": str(e)}


def launch_student_ocr_only(test_id: int, scripts_pdf_path: str) -> Dict[str, Any]:
    """
    Launches only the OCR extraction (no matching or ZIP generation)
    """
    try:
        result: AsyncResult = run_student_script_ocr_pipeline.apply_async(
            args=[test_id, scripts_pdf_path]
        )

        manifest: SubmissionManifest = SubmissionManifest()
        manifest.test_id = test_id
        setattr(manifest, "name", f"test_{test_id}_ocr_only")
        db.session.add(manifest)
        db.session.commit()

        tc: TaskControl = TaskControl(
            task_id=str(result.id),
            test_id=test_id,
            status="RUNNING"
        )
        db.session.add(tc)
        db.session.commit()

        logger.info(f"[Pipeline] Student OCR-only pipeline launched for test {test_id}, task={result.id}")
        return {"status": "STARTED", "task_id": result.id, "workflow_id": result.id, "test_id": test_id}

    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"[Pipeline] DB error launching OCR-only pipeline for test {test_id}: {e}")
        return {"status": "FAILED", "error": "DB error"}

    except Exception as e:
        logger.exception(f"[Pipeline] Unexpected error launching OCR-only pipeline for test {test_id}: {e}")
        return {"status": "FAILED", "error": str(e)}


def launch_grading_pipeline(test_id: int) -> Dict[str, Any]:
    """
    Launches the grading pipeline asynchronously
    """
    try:
        result: AsyncResult = async_grade_all_students.apply_async(args=[test_id])

        tc: TaskControl = TaskControl(
            task_id=str(result.id),
            test_id=test_id,
            status="RUNNING"
        )
        db.session.add(tc)
        db.session.commit()

        logger.info(f"[Pipeline] Grading launched for test {test_id}, task={result.id}")
        return {"status": "STARTED", "task_id": result.id, "workflow_id": result.id, "test_id": test_id}

    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"[Pipeline] DB error launching grading for test {test_id}: {e}")
        return {"status": "FAILED", "error": "DB error"}

    except Exception as e:
        logger.exception(f"[Pipeline] Unexpected error launching grading for test {test_id}: {e}")
        return {"status": "FAILED", "error": str(e)}


# -------------------------------
# Flask Blueprint for Task Control
# -------------------------------
ocr_control_bp = Blueprint("ocr_control_bp", __name__)


@ocr_control_bp.route("/ocr/full", methods=["POST"])
def start_full_ocr():
    data: Dict[str, Any] = request.get_json() or {}

    test_id_raw = data.get("test_id")
    scripts_pdf_path_raw = data.get("scripts_pdf_path")
    class_list_path_raw = data.get("class_list_path")

    if test_id_raw is None or scripts_pdf_path_raw is None or class_list_path_raw is None:
        return jsonify({"status": "FAILED", "error": "Missing required parameters"}), 400

    test_id: int = int(test_id_raw)
    scripts_pdf_path: str = str(scripts_pdf_path_raw)
    class_list_path: str = str(class_list_path_raw)

    result = launch_ocr_pipeline(test_id, scripts_pdf_path, class_list_path)
    return jsonify(result)


@ocr_control_bp.route("/ocr/only", methods=["POST"])
def start_ocr_only():
    data: Dict[str, Any] = request.get_json() or {}

    test_id_raw = data.get("test_id")
    scripts_pdf_path_raw = data.get("scripts_pdf_path")

    if test_id_raw is None or scripts_pdf_path_raw is None:
        return jsonify({"status": "FAILED", "error": "Missing required parameters"}), 400

    test_id: int = int(test_id_raw)
    scripts_pdf_path: str = str(scripts_pdf_path_raw)

    result = launch_student_ocr_only(test_id, scripts_pdf_path)
    return jsonify(result)


@ocr_control_bp.route("/grading", methods=["POST"])
def start_grading():
    data: Dict[str, Any] = request.get_json() or {}

    test_id_raw = data.get("test_id")
    if test_id_raw is None:
        return jsonify({"status": "FAILED", "error": "Missing required parameters"}), 400

    test_id: int = int(test_id_raw)

    result = launch_grading_pipeline(test_id)
    return jsonify(result)
