# File: smartscripts/services/analytics_service.py
from collections import defaultdict, Counter
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
import csv
import logging

from smartscripts.models import AuditLog, ExtractedStudentScript
from smartscripts.extensions import db
from smartscripts.services.ocr_utils import generate_review_zip  # Canonical ZIP function

logger = logging.getLogger(__name__)


# -------------------------------
# 1️⃣ Grading / Feedback Analytics
# -------------------------------

def compute_success_rates(results: List[Dict]) -> Dict[str, float]:
    """Compute per-question success rates."""
    totals = defaultdict(int)
    corrects = defaultdict(int)
    for r in results:
        qid = r["question_id"]
        totals[qid] += 1
        if r.get("is_correct"):
            corrects[qid] += 1
    return {qid: corrects[qid] / totals[qid] for qid in totals}


def compute_average_score(results: List[Dict]) -> float:
    """Compute the average score across all results."""
    scores = [r["score"] for r in results if "score" in r]
    return sum(scores) / len(scores) if scores else 0.0


def aggregate_feedback(results: List[Dict]) -> Dict[str, List[str]]:
    """Aggregate textual feedback by question."""
    feedback_map = defaultdict(list)
    for r in results:
        qid = r["question_id"]
        feedback = r.get("feedback")
        if feedback:
            feedback_map[qid].append(feedback)
    return feedback_map


def compute_grading_distribution(results: List[Dict], bins: Optional[List[int]] = None) -> Dict[str, int]:
    """Compute a distribution of scores into bins."""
    bins = bins or [0, 50, 70, 85, 100]
    distribution = Counter()
    for r in results:
        score = r.get("score", 0)
        for i in range(1, len(bins)):
            if bins[i - 1] <= score < bins[i]:
                distribution[f"{bins[i-1]}–{bins[i]-1}"] += 1
                break
        else:
            if score >= bins[-1]:
                distribution[f"{bins[-1]}+"] += 1
    return dict(distribution)


def average_manual_review_time() -> float:
    """Estimate average time (seconds) between manual corrections."""
    logs = AuditLog.query.filter_by(action="manual_override").order_by(AuditLog.timestamp).all()
    if len(logs) < 2:
        return 0.0
    deltas = [(logs[i].timestamp - logs[i-1].timestamp).total_seconds() for i in range(1, len(logs))]
    return sum(deltas) / len(deltas)


def export_manual_corrections(csv_filepath: str = "manual_corrections.csv"):
    """Export all manual corrections to CSV."""
    corrections = AuditLog.query.filter_by(action="manual_override").all()
    with open(csv_filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["question_id", "new_text", "reviewer", "timestamp"])
        for c in corrections:
            writer.writerow([
                c.question_id or "",
                (c.new_text or "").replace('"', '""'),
                c.user_id or "",
                c.timestamp.isoformat() if c.timestamp else ""
            ])
    logger.info("Exported %d manual corrections to %s", len(corrections), csv_filepath)


# -------------------------------
# 2️⃣ Presence Table & PDF Naming
# -------------------------------

def generate_presence_table(extracted_scripts: List[ExtractedStudentScript], class_list: List[Dict[str, str]]) -> List[Dict]:
    """Generate a presence table matching OCR-extracted IDs to the class list."""
    class_map = {s["id"]: s["name"] for s in class_list}
    presence = []
    for s in extracted_scripts:
        sid = s.ocr_student_id or ""
        name = s.ocr_name or ""
        matched_name = class_map.get(sid)
        presence.append({
            "student_id": sid,
            "name": name,
            "matched": bool(matched_name),
            "matched_name": matched_name or "",
            "confidence": s.confidence or 0.0
        })
    return presence


def rename_student_pdfs(extracted_scripts: List[ExtractedStudentScript], upload_dir: str):
    """Rename student PDFs based on OCR name and ID."""
    upload_path = Path(upload_dir)
    for s in extracted_scripts:
        orig = upload_path / (s.extracted_pdf_path or "")
        name_safe = (s.ocr_name or "").replace(" ", "_")
        new_filename = f"{s.ocr_student_id}-{name_safe}.pdf"
        new_path = upload_path / new_filename
        if orig.exists():
            orig.rename(new_path)
            s.extracted_pdf_path = str(new_path.relative_to(upload_path))
            logger.info("Renamed %s → %s", orig.name, new_filename)



