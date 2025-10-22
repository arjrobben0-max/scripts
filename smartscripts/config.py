import os
from pathlib import Path
from dotenv import load_dotenv

# ─── Load environment variables ───────────────────────────────────────────────
load_dotenv()

# ─── Base Paths ──────────────────────────────────────────────────────────────
PACKAGE_ROOT = Path(__file__).resolve().parent  # ...\Smartscripts\smartscripts
APP_DIR = PACKAGE_ROOT / "app"
STATIC_DIR = APP_DIR / "static"
UPLOAD_ROOT = STATIC_DIR / "uploads"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

# ─── Legacy top-level variable for backward compatibility ────────────────────
UPLOAD_FOLDER = UPLOAD_ROOT

# ─── Allowed file types ──────────────────────────────────────────────────────
BASE_ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "png", "jpg", "jpeg"}

# ─── Logging ────────────────────────────────────────────────────────────────
LOG_DIR = APP_DIR
LOG_FILE = LOG_DIR / "app.log"

# ─── Base Config Class ───────────────────────────────────────────────────────
class BaseConfig:
    """Base configuration shared by all environments."""

    DEBUG = False
    TESTING = False
    ENABLE_SUBMISSIONS = os.getenv("ENABLE_SUBMISSIONS", "True").lower() in ["true", "1", "yes"]
    WTF_CSRF_ENABLED = False

    # Flask folders
    STATIC_FOLDER = STATIC_DIR
    UPLOAD_FOLDER = UPLOAD_ROOT

    ALLOWED_EXTENSIONS = BASE_ALLOWED_EXTENSIONS
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB

    # Logging
    LOG_DIR = LOG_DIR
    LOG_FILE = LOG_FILE

    # Secret Key
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

    # Flask-Mail
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True").lower() in ["true", "1", "yes"]
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "False").lower() in ["true", "1", "yes"]
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = (
        os.getenv("MAIL_DEFAULT_SENDER_NAME", "SmartScripts Support"),
        MAIL_USERNAME,
    )

    # AI / ML
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
    TROCR_MODEL = os.getenv("TROCR_MODEL", "microsoft/trocr-base-handwritten")
    GPT_MODEL = os.getenv("GPT_MODEL", "gpt-4")

    # ─── Database (Common) ───────────────────────────────────────────────────
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ─── Celery ────────────────────────────────────────────────────────────────
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

    # If CELERY_RESULT_BACKEND is not set explicitly, use DATABASE_URL with correct prefix
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        CELERY_RESULT_BACKEND = os.getenv(
            "CELERY_RESULT_BACKEND",
            database_url.replace("postgresql://", "db+postgresql://")
        )
    else:
        CELERY_RESULT_BACKEND = os.getenv(
            "CELERY_RESULT_BACKEND",
            f"db+sqlite:///{PACKAGE_ROOT / 'celery_results.sqlite'}"
        )

    CELERY_TASK_TRACK_STARTED = True
    CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes

    @property
    def CELERY_CONFIG(self):
        """Return Celery configuration dict for Flask app."""
        return {
            "broker_url": self.CELERY_BROKER_URL,
            "result_backend": self.CELERY_RESULT_BACKEND,
            "task_track_started": self.CELERY_TASK_TRACK_STARTED,
            "task_time_limit": self.CELERY_TASK_TIME_LIMIT,
            "task_serializer": "json",
            "result_serializer": "json",
            "accept_content": ["json"],
            "timezone": "Africa/Kampala",
            "enable_utc": True,
        }

    # ─── Upload Directory Helpers ────────────────────────────────────────────
    @classmethod
    def test_root(cls, test_id: str) -> Path:
        """Root folder for a specific test."""
        return cls.UPLOAD_FOLDER / str(test_id)

    @classmethod
    def init_upload_dirs(cls, test_id: str, student_id: str = None, teacher_id: str = None):
        """Create expected upload subfolders for a test, optional student/teacher dirs."""
        base = cls.test_root(test_id)
        folders = [
            "answered_scripts",
            "audit_logs",
            "class_lists",
            "combined_scripts",
            "extracted",
            "feedback",
            "manifests",
            "marked",
            "marking_guides",
            "question_papers",
            "resources/images",
            "resources/code",
            "resources/datasets",
            "rubrics",
            "student_lists",
            "student_scripts",
            "submissions",
            "tmp",
            "exports",
        ]

        for folder in folders:
            (base / folder).mkdir(parents=True, exist_ok=True)

        if student_id:
            (base / "submissions" / str(student_id)).mkdir(parents=True, exist_ok=True)
            (base / "extracted" / str(student_id)).mkdir(parents=True, exist_ok=True)
        if teacher_id:
            (base / "tmp" / str(teacher_id) / "working_files").mkdir(parents=True, exist_ok=True)

        print(f"✅ Upload directories initialized at: {base}")
        return base


# ─── Environment-Specific Configs ────────────────────────────────────────────
class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TESTING = True
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{PACKAGE_ROOT / 'dev.sqlite3'}",
    )


class ProductionConfig(BaseConfig):
    SECRET_KEY = os.getenv("SECRET_KEY")
    if not os.getenv("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY environment variable is not set for production!")

    # Ensure Render Postgres has sslmode=require appended
    db_url = os.getenv("DATABASE_URL")
    if db_url and "sslmode" not in db_url:
        db_url += "?sslmode=require"

    SQLALCHEMY_DATABASE_URI = db_url
    if not SQLALCHEMY_DATABASE_URI:
        raise RuntimeError("DATABASE_URL must be set in production!")


class TestingConfig(BaseConfig):
    TESTING = True
    SECRET_KEY = os.getenv("SECRET_KEY", "test-secret-key")
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


# ─── Config Dictionary ──────────────────────────────────────────────────────
config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
