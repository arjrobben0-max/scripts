# smartscripts/models/task_control.py

from smartscripts.extensions import db


class TaskControl(db.Model):
    """
    Stores the control state of a long-running Celery task.
    This is used to support pause, resume, and cancel functionality
    for tasks like preprocessing or OCR pipelines.
    """

    __tablename__ = 'task_control'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(128), unique=True, nullable=False, index=True)
    status = db.Column(db.String(20), default='RUNNING', nullable=False)
    # Possible values:
    # RUNNING, PAUSED, CANCELED, COMPLETED

    def __repr__(self):
        return f"<TaskControl(task_id={self.task_id}, status={self.status})>"
