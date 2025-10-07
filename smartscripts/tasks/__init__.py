# smartscripts/tasks/__init__.py
"""
Tasks package initialization
----------------------------
Registers all Celery tasks so they are discovered automatically.
"""

# Import the Celery app instance directly (do NOT use current_app here)
from smartscripts.celery_app import celery

# Import all task modules so Celery knows about them
from . import ocr_tasks
from . import grade_tasks
from . import matching_tasks
from . import review_tasks
from . import tasks_control

# Expose celery app instance for easy access
__all__ = ["celery"]
