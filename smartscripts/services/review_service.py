# File: smartscripts/services/review_service.py
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from smartscripts.extensions import db
from smartscripts.models import AuditLog


# -------------------------------
# Database Helpers
# -------------------------------
def _commit_session() -> None:
    """Commit the current SQLAlchemy session; rollback if it fails."""
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise RuntimeError(f"DB commit failed: {e}") from e


# -------------------------------
# Audit / Manual Override
# -------------------------------
def log_manual_override(
    reviewer_id: int,
    student_id: Optional[str] = None,
    test_id: Optional[int] = None,
    ocr_submission_id: Optional[int] = None,
    original_name: Optional[str] = None,
    corrected_name: Optional[str] = None,
    original_id: Optional[str] = None,
    corrected_id: Optional[str] = None,
    confidence: Optional[float] = None,
    comment: Optional[str] = None,
) -> AuditLog:
    """Logs a manual override entry for a student's OCR info."""
    audit = AuditLog(
        event_type="manual_override",
        user_id=reviewer_id,
        student_id=student_id,
        test_id=test_id,
        ocr_submission_id=ocr_submission_id,
        original_name=original_name,
        corrected_name=corrected_name,
        original_id=original_id,
        corrected_id=corrected_id,
        confidence=confidence,
        comment=comment,
        description=f"Manual override by user {reviewer_id} for student {student_id}",
        timestamp=datetime.utcnow(),
    )
    db.session.add(audit)
    _commit_session()
    return audit


def get_review_history(student_id: str) -> List[Dict[str, Any]]:
    """Retrieve all manual override audit logs for a student."""
    logs = (
        AuditLog.query.filter_by(student_id=student_id, event_type="manual_override")
        .order_by(AuditLog.timestamp.desc())
        .all()
    )
    return [
        {
            "id": log.id,
            "event_type": log.event_type,
            "user_id": log.user_id,
            "student_id": log.student_id,
            "test_id": log.test_id,
            "ocr_submission_id": log.ocr_submission_id,
            "original_name": log.original_name,
            "corrected_name": log.corrected_name,
            "original_id": log.original_id,
            "corrected_id": log.corrected_id,
            "confidence": log.confidence,
            "comment": log.comment,
            "description": log.description,
            "timestamp": log.timestamp,
        }
        for log in logs
    ]


def get_latest_override(student_id: str, reviewer_id: Optional[int] = None) -> Optional[AuditLog]:
    """Returns the most recent manual override for a student, optionally filtered by reviewer."""
    query = AuditLog.query.filter_by(student_id=student_id, event_type="manual_override")
    if reviewer_id is not None:
        query = query.filter_by(user_id=reviewer_id)
    return query.order_by(AuditLog.timestamp.desc()).first()


def process_teacher_review(
    reviewer_id: int,
    student_id: Optional[str] = None,
    test_id: Optional[int] = None,
    ocr_submission_id: Optional[int] = None,
    original_name: Optional[str] = None,
    corrected_name: Optional[str] = None,
    original_id: Optional[str] = None,
    corrected_id: Optional[str] = None,
    confidence: Optional[float] = None,
    comment: Optional[str] = None,
) -> AuditLog:
    """Processes a teacher's manual override by creating an AuditLog entry."""
    return log_manual_override(
        reviewer_id=reviewer_id,
        student_id=student_id,
        test_id=test_id,
        ocr_submission_id=ocr_submission_id,
        original_name=original_name,
        corrected_name=corrected_name,
        original_id=original_id,
        corrected_id=corrected_id,
        confidence=confidence,
        comment=comment,
    )


def override_diff(old_data: Dict[str, Any], new_data: Dict[str, Any]) -> Dict[str, Any]:
    """Returns differences between old and new override data {field: (old_value, new_value)}."""
    return {
        k: (old_data.get(k), new_data.get(k))
        for k in set(old_data) | set(new_data)
        if old_data.get(k) != new_data.get(k)
    }
