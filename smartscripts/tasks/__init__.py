"""
Tasks package initialization
----------------------------
Registers all Celery tasks so they are discovered automatically by Celery.
"""

# ✅ Import only the global Celery instance
from smartscripts.extensions import celery

# ✅ Import individual task modules so Celery autodiscovers them
from . import ocr_tasks
from . import grade_tasks
from . import matching_tasks
from . import review_tasks
from . import tasks_control

__all__ = ["celery"]
