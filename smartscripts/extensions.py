"""
smartscripts/extensions.py: Flask & Celery Extensions
-----------------------------------------------------
This module initializes all Flask extensions and integrates Celery.
Ensures Celery runs safely on Windows and shares Flask's app context.
"""

import os
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from celery import Celery

# ────────────────────────────────────────────────────────────────
# Flask Extensions (Singletons)
# ────────────────────────────────────────────────────────────────
db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
migrate = Migrate()

# ────────────────────────────────────────────────────────────────
# Celery Global Instance
# ────────────────────────────────────────────────────────────────
celery = Celery("smartscripts")

# ────────────────────────────────────────────────────────────────
# Celery Factory
# ────────────────────────────────────────────────────────────────
def make_celery(app):
    """
    Bind the global Celery instance to the Flask app context.
    Ensures tasks run within Flask's context and work on Windows.
    """

    # Update Celery configuration from Flask config
    celery.conf.update(
        broker_url=app.config["CELERY_BROKER_URL"],
        result_backend=app.config["CELERY_RESULT_BACKEND"],
        broker_connection_retry_on_startup=True,
        task_track_started=True,
        task_time_limit=30 * 60,  # 30 minutes
        worker_max_tasks_per_child=100,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone=app.config.get("CELERY_TIMEZONE", "Africa/Kampala"),
        enable_utc=True,
        result_extended=True,
        include=[
            "smartscripts.tasks",
            "smartscripts.tasks.ocr_tasks",
            "smartscripts.tasks.grade_tasks",
            "smartscripts.tasks.matching_tasks",
            "smartscripts.tasks.review_tasks",
            "smartscripts.tasks.tasks_control",
        ],
    )

    # Context-aware Celery Task — runs inside Flask app context
    class ContextTask(celery.Task):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask

    # Bind app to Celery instance
    app.celery = celery
    app.logger.info(f"✅ Celery initialized with broker: {app.config['CELERY_BROKER_URL']} "
                    f"and backend: {app.config['CELERY_RESULT_BACKEND']}")

    return celery

# ────────────────────────────────────────────────────────────────
# Flask-Login Manager Configuration
# ────────────────────────────────────────────────────────────────
def configure_login_manager(app):
    """
    Initialize Flask-Login and set login settings.
    """
    login_manager.init_app(app)
    login_manager.login_view = "auth_bp.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"

# ────────────────────────────────────────────────────────────────
# Exports
# ────────────────────────────────────────────────────────────────
__all__ = [
    "db",
    "login_manager",
    "mail",
    "migrate",
    "celery",
    "make_celery",
    "configure_login_manager",
]

# ────────────────────────────────────────────────────────────────
# Force Celery to load all task modules (prevents KeyError)
# ────────────────────────────────────────────────────────────────
try:
    import smartscripts.tasks
    import smartscripts.tasks.ocr_tasks
    import smartscripts.tasks.grade_tasks
    import smartscripts.tasks.matching_tasks
    import smartscripts.tasks.review_tasks
    import smartscripts.tasks.tasks_control
except ImportError as e:
    print(f"[WARN] Task import failed: {e}")
