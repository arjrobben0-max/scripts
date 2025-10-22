# smartscripts/models/task_control.py

from datetime import datetime
from smartscripts.extensions import db


class TaskControl(db.Model):
    """
    Stores the control state of a long-running Celery task.
    Used for pause, resume, cancel, and tracking OCR preprocessing.
    """

    __tablename__ = "task_control"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(128), unique=True, nullable=False, index=True)
    status = db.Column(db.String(20), default="RUNNING", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ✅ Correct Foreign Key: matches __tablename__ = "tests"
    test_id = db.Column(db.Integer, db.ForeignKey("tests.id"), nullable=False)

    # ✅ Optional relationship for convenience
    test = db.relationship("Test", backref=db.backref("tasks", lazy=True))

    def __repr__(self):
        return f"<TaskControl(task_id={self.task_id}, status={self.status}, test_id={self.test_id})>"
