import os
import io
import zipfile
from pathlib import Path

from flask import Blueprint, send_from_directory, current_app, jsonify, request, send_file
from smartscripts.extensions import db
from smartscripts.models import Test
from smartscripts.models.extracted_student_script import ExtractedStudentScript
from smartscripts.utils.file_helpers import get_uploaded_file_path, get_student_script_pdf_path

file_bp = Blueprint("file_bp", __name__)

# In-memory OCR progress state (replace with Redis/DB in production)
ocr_state = {"progress": 0, "task_id": None, "status": "IDLE"}


# ---------------- Routes ----------------
@file_bp.route("/file/ping")
def ping_file():
    return "File routes are working"


@file_bp.route("/uploaded/<path:filename>")
def uploaded_file(filename):
    uploads_dir = os.path.join(current_app.root_path, "static", "uploads")
    return send_from_directory(uploads_dir, filename)


# ---------------- OCR Preprocessing ----------------
@file_bp.route("/start-ocr/<int:test_id>", methods=["POST"])
def start_ocr(test_id: int):
    # Lazy import to avoid circular dependency
    from smartscripts.tasks.ocr_tasks import run_student_script_ocr_pipeline

    test = Test.query.get_or_404(test_id)
    required_files = ["marking_guide_path", "question_paper_path", "combined_scripts_path", "class_list_path"]
    missing = [f for f in required_files if not getattr(test, f)]
    if missing:
        return jsonify({"error": f"Missing required files: {', '.join(missing)}"}), 400

    task = run_student_script_ocr_pipeline.delay(
        test.id,
        str(get_uploaded_file_path(test.combined_scripts_path)),
        str(get_uploaded_file_path(test.class_list_path))
    )
    ocr_state.update({"task_id": task.id, "status": "RUNNING", "progress": 0})
    return jsonify({"task_id": task.id, "status": "started"})


# ---------------- OCR Progress ----------------
@file_bp.route("/ocr-progress/<task_id>", methods=["GET"])
def ocr_progress(task_id: str):
    from celery.result import AsyncResult

    result = AsyncResult(task_id)
    if result.state == "PENDING":
        progress, status = 0, "PENDING"
    elif result.state == "PROGRESS":
        progress, status = result.info.get("percent", 0), "RUNNING"
    elif result.state == "SUCCESS":
        progress, status = 100, "COMPLETED"
    elif result.state in ("REVOKED", "FAILURE"):
        progress, status = 0, "FAILED"
    else:
        progress, status = 0, result.state

    return jsonify({"task_id": task_id, "progress": progress, "status": status})


# ---------------- Preprocessing Summary ----------------
@file_bp.route("/preprocess-summary/<int:test_id>", methods=["GET"])
def preprocess_summary(test_id: int):
    scripts = ExtractedStudentScript.query.filter_by(test_id=test_id).all()
    summary = []
    matched_count = 0

    for s in scripts:
        is_matched = bool(s.matched_id)
        if is_matched:
            matched_count += 1
        summary.append({
            "script_id": s.id,
            "ocr_name": s.ocr_name,
            "ocr_student_id": s.ocr_student_id,
            "matched": is_matched,
            "confidence": getattr(s, "confidence", None),
        })

    return jsonify({
        "test_id": test_id,
        "total_scripts": len(scripts),
        "matched": matched_count,
        "unmatched": len(scripts) - matched_count,
        "scripts": summary,
    })


# ---------------- Export ZIP ----------------
@file_bp.route("/export-zip/<int:test_id>")
def export_zip(test_id: int):
    scripts = ExtractedStudentScript.query.filter_by(test_id=test_id).all()
    if not scripts:
        return jsonify({"error": "No extracted scripts to export"}), 404

    memory_file = io.BytesIO()
    rows = []

    with zipfile.ZipFile(memory_file, "w") as zf:
        for script in scripts:
            pdf_path = get_student_script_pdf_path(test_id, script.ocr_student_id)
            if pdf_path:
                arcname = f"{script.ocr_student_id or 'Unknown'}-{script.ocr_name or 'Unknown'}.pdf"
                zf.write(pdf_path, arcname=arcname)
            rows.append({
                "script_id": script.id,
                "ocr_name": script.ocr_name,
                "ocr_student_id": script.ocr_student_id,
                "matched_id": script.matched_id,
                "confidence": getattr(script, "confidence", None),
            })
        if rows:
            import pandas as pd
            df = pd.DataFrame(rows)
            zf.writestr("logs/preprocess_summary.csv", df.to_csv(index=False))

    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"test_{test_id}_scripts.zip",
    )


# ---------------- Manual Override ----------------
@file_bp.route("/script/<int:script_id>/override", methods=["POST"])
def override_script(script_id: int):
    script = ExtractedStudentScript.query.get_or_404(script_id)
    data = request.get_json(force=True)

    script.ocr_name = data.get("ocr_name", script.ocr_name)
    script.ocr_student_id = data.get("ocr_student_id", script.ocr_student_id)
    script.matched_id = data.get("matched_id", script.matched_id)
    if "confidence" in data:
        script.confidence = float(data["confidence"])

    db.session.commit()
    return jsonify({"status": "ok", "script_id": script.id})
