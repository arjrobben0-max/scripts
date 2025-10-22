import sys
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from flask import Flask, render_template, g, current_app
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv
from alembic.config import Config
from alembic import command
from concurrent_log_handler import ConcurrentRotatingFileHandler  # ✅ NEW

# Load environment variables
load_dotenv()

# ─── Extensions ─────────────────────────────────────────────
from smartscripts.extensions import (
    db,
    login_manager,
    mail,
    migrate,
    configure_login_manager,
    make_celery,  # used inside tasks, not here
)

csrf = CSRFProtect()


# ─── Flask subclass to attach Celery instance ───────────────
class MyFlask(Flask):
    celery: Optional[object] = None  # type: ignore


# ─── Factory ──────────────────────────────────────────────
def create_app(config_name: str = "default"):
    """Application factory function."""
    from smartscripts.config import config_by_name, BaseConfig

    config_class = config_by_name[config_name]

    app = MyFlask(
        __name__,
        template_folder="templates",
        static_folder=str(config_class.STATIC_FOLDER),
        static_url_path="/static",
    )
    app.config.from_object(config_class)

    # ─── Secret key ─────────────────────────────────────────
    app.config["SECRET_KEY"] = app.config.get(
        "SECRET_KEY", os.getenv("SECRET_KEY", "your-default-secret-key")
    )

    # ─── Mail config ────────────────────────────────────────
    app.config.update(
        MAIL_SERVER="smtp.gmail.com",
        MAIL_PORT=587,
        MAIL_USE_TLS=True,
        MAIL_USERNAME=os.getenv("MAIL_USERNAME", "your_email@gmail.com"),
        MAIL_PASSWORD=os.getenv("MAIL_PASSWORD", "your_app_password"),
        MAIL_DEFAULT_SENDER=os.getenv("MAIL_DEFAULT_SENDER", "your_email@gmail.com"),
    )

    # ─── Initialize Flask extensions ─────────────────────────
    csrf.init_app(app)
    db.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)
    configure_login_manager(app)

    # ─── Ensure folders exist ───────────────────────────────
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["LOG_DIR"]).mkdir(parents=True, exist_ok=True)

    # ─── CORS ───────────────────────────────────────────────
    if app.config.get("ENV") == "development":
        CORS(app, origins=["http://localhost:3000"], supports_credentials=True)
    else:
        CORS(app, supports_credentials=True)

    # ─── Logging ────────────────────────────────────────────
    setup_logging(app)

    # ─── Database engine setup ──────────────────────────────
    from smartscripts.database import get_engine, get_session
    try:
        engine = get_engine(config_name)
        session = get_session(engine)
        app.db_engine = engine
        app.db_session = session
        app.logger.info("DB engine and session initialized.")
    except Exception as e:
        app.logger.error(f"DB setup error: {e}", exc_info=True)

    @app.before_request
    def set_session():
        g.db_session = get_session(app.db_engine)

    @app.teardown_appcontext
    def cleanup_session(exception=None):
        session = g.pop("db_session", None)
        if session:
            try:
                if exception:
                    session.rollback()
                    app.logger.warning("DB session rolled back due to exception.")
                session.close()
            except Exception as e:
                app.logger.error(f"DB session cleanup error: {e}", exc_info=True)

    # ─── Register Blueprints ────────────────────────────────
    from smartscripts.app.auth import auth_bp
    from smartscripts.app.main.routes import main_bp
    from smartscripts.app.teacher import teacher_bp
    from smartscripts.app.teacher.ai_marking_routes import ai_marking_bp
    from smartscripts.app.teacher.analytics_routes import analytics_bp
    from smartscripts.app.teacher.upload_routes import upload_bp
    from smartscripts.app.teacher.preview_routes import preview_bp
    from smartscripts.app.teacher.download_routes import download_bp
    from smartscripts.app.teacher.profile_routes import teacher_profile_bp
    from smartscripts.app.teacher.manage_routes import manage_bp
    from smartscripts.app.student import student_bp
    from smartscripts.app.admin.routes import admin_bp
    from smartscripts.tasks.tasks_control import ocr_control_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(main_bp)
    app.register_blueprint(teacher_bp, url_prefix="/teacher")
    app.register_blueprint(upload_bp, url_prefix="/upload")
    app.register_blueprint(student_bp, url_prefix="/api/student")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(ai_marking_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(teacher_profile_bp, url_prefix="/teacher/profile")
    app.register_blueprint(preview_bp)
    app.register_blueprint(download_bp)
    app.register_blueprint(manage_bp, url_prefix="/teacher/manage")
    app.register_blueprint(ocr_control_bp)

    # ─── User loader ────────────────────────────────────────
    from smartscripts.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return User.query.get(int(user_id))
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"[load_user] DB error: {e}", exc_info=True)
            return None

    # ─── Alembic migrations (dev only) ──────────────────────
    if app.config.get("ENV") == "development":
        run_alembic_migrations(app)

    # ─── Error handlers ─────────────────────────────────────
    register_error_handlers(app)

    # ─── Context processors ─────────────────────────────────
    @app.context_processor
    def inject_current_year():
        return {"current_year": datetime.utcnow().year}

    # ─── Shell context ──────────────────────────────────────
    @app.shell_context_processor
    def make_shell_context():
        from smartscripts.models.test import Test
        from smartscripts.models.student_submission import StudentSubmission
        return {"db": db, "Test": Test, "StudentSubmission": StudentSubmission}

    app.logger.info("App created successfully.")
    app.logger.info(f"Uploads folder: {app.config['UPLOAD_FOLDER']}")
    app.logger.info(f"Static folder: {app.static_folder}")

    return app


# ─── Alembic ──────────────────────────────────────────────
def run_alembic_migrations(app):
    try:
        ini_path = os.path.abspath(os.path.join(app.root_path, "..", "..", "alembic.ini"))
        alembic_cfg = Config(ini_path)
        command.upgrade(alembic_cfg, "head")
        app.logger.info("Alembic migrations applied.")
    except Exception as e:
        app.logger.error(f"Alembic migration error: {e}", exc_info=True)


# ─── Logging (Concurrent-safe) ──────────────────────────────
def setup_logging(app):
    """Thread-safe logging setup using ConcurrentRotatingFileHandler."""
    from smartscripts.config import BaseConfig

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
    )

    # Ensure log directory exists
    os.makedirs(BaseConfig.LOG_DIR, exist_ok=True)
    log_path = BaseConfig.LOG_FILE

    # Stream handler (console)
    if not any(isinstance(h, logging.StreamHandler) for h in app.logger.handlers):
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(logging.DEBUG if app.debug else logging.INFO)
        stream_handler.setFormatter(formatter)
        app.logger.addHandler(stream_handler)

    # Concurrent-safe file handler
    if not any(isinstance(h, ConcurrentRotatingFileHandler) for h in app.logger.handlers):
        file_handler = ConcurrentRotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        app.logger.addHandler(file_handler)

    app.logger.setLevel(logging.INFO)
    app.logger.info(f"Concurrent logging initialized -> {log_path}")


# ─── Error handlers ───────────────────────────────────────
def register_error_handlers(app):
    @app.errorhandler(403)
    def forbidden_error(error):
        app.logger.warning("403 Forbidden")
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found_error(error):
        app.logger.warning("404 Not Found")
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error("500 Internal Server Error", exc_info=True)
        return render_template("errors/500.html"), 500
