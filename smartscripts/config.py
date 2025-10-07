# smartscripts/config.py
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
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "png", "jpg", "jpeg"}

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

    ALLOWED_EXTENSIONS = ALLOWED_EXTENSIONS
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB

    # Logging
    LOG_DIR = LOG_DIR
    LOG_FILE = LOG_FILE

    # Mail
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True").lower() in ["true", "1", "yes"]
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = ("CoGrader", MAIL_USERNAME)

    # AI / ML models
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
    TROCR_MODEL = os.getenv("TROCR_MODEL", "microsoft/trocr-base-handwritten")
    GPT_MODEL = os.getenv("GPT_MODEL", "gpt-4")

    # Celery
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
    CELERY_TASK_TRACK_STARTED = True
    CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes

    # SQLAlchemy
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    @property
    def CELERY_CONFIG(self):
        return {
            "broker_url": self.CELERY_BROKER_URL,
            "result_backend": self.CELERY_RESULT_BACKEND,
            "task_track_started": self.CELERY_TASK_TRACK_STARTED,
            "task_time_limit": self.CELERY_TASK_TIME_LIMIT,
        }

    # ─── Dynamic Upload Paths ────────────────────────────────────────────────
    @classmethod
    def test_root(cls, test_id: str) -> Path:
        return cls.UPLOAD_FOLDER / str(test_id)

    @classmethod
    def answered_scripts(cls, test_id: str) -> Path:
        return cls.test_root(test_id) / "answered_scripts"

    @classmethod
    def audit_logs(cls, test_id: str) -> Path:
        return cls.test_root(test_id) / "audit_logs"

    @classmethod
    def class_lists(cls, test_id: str) -> Path:
        return cls.test_root(test_id) / "class_lists"

    @classmethod
    def combined_scripts(cls, test_id: str) -> Path:
        return cls.test_root(test_id) / "combined_scripts"

    @classmethod
    def extracted(cls, test_id: str, student_id: str) -> Path:
        return cls.test_root(test_id) / "extracted" / str(student_id)

    @classmethod
    def feedback(cls, test_id: str) -> Path:
        return cls.test_root(test_id) / "feedback"

    @classmethod
    def manifests(cls, test_id: str) -> Path:
        return cls.test_root(test_id) / "manifests"

    @classmethod
    def marked(cls, test_id: str) -> Path:
        return cls.test_root(test_id) / "marked"

    @classmethod
    def marking_guides(cls, test_id: str) -> Path:
        return cls.test_root(test_id) / "marking_guides"

    @classmethod
    def question_papers(cls, test_id: str) -> Path:
        return cls.test_root(test_id) / "question_papers"

    @classmethod
    def question_paper_rubrics(cls, test_id: str) -> Path:
        return cls.question_papers(test_id) / "rubrics"

    @classmethod
    def resources(cls, test_id: str) -> Path:
        return cls.test_root(test_id) / "resources"

    @classmethod
    def rubrics(cls, test_id: str) -> Path:
        return cls.test_root(test_id) / "rubrics"

    @classmethod
    def student_lists(cls, test_id: str) -> Path:
        return cls.test_root(test_id) / "student_lists"

    @classmethod
    def student_scripts(cls, test_id: str) -> Path:
        return cls.test_root(test_id) / "student_scripts"

    @classmethod
    def submissions(cls, test_id: str, student_id: str) -> Path:
        return cls.test_root(test_id) / "submissions" / str(student_id)

    @classmethod
    def tmp(cls, test_id: str, teacher_id: str) -> Path:
        return cls.test_root(test_id) / "tmp" / str(teacher_id) / "working_files"

    @classmethod
    def exports(cls, test_id: str) -> Path:
        return cls.test_root(test_id) / "exports"

    @classmethod
    def init_upload_dirs(cls, test_id: str, student_id: str = None, teacher_id: str = None):
        """Create all required directories for a given test (and optionally student/teacher)."""
        required_dirs = [
            cls.answered_scripts(test_id),
            cls.audit_logs(test_id),
            cls.class_lists(test_id),
            cls.combined_scripts(test_id),
            cls.feedback(test_id),
            cls.manifests(test_id),
            cls.marked(test_id),
            cls.marking_guides(test_id),
            cls.question_papers(test_id),
            cls.question_paper_rubrics(test_id),
            cls.resources(test_id),
            cls.rubrics(test_id),
            cls.student_lists(test_id),
            cls.student_scripts(test_id),
            cls.exports(test_id),
            cls.LOG_DIR,
        ]
        if student_id:
            required_dirs.append(cls.extracted(test_id, student_id))
            required_dirs.append(cls.submissions(test_id, student_id))
        if teacher_id:
            required_dirs.append(cls.tmp(test_id, teacher_id))

        for folder in required_dirs:
            Path(folder).mkdir(parents=True, exist_ok=True)

# ─── Environment-Specific Configs ──────────────────────────────────────────
class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TESTING = True
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", f"sqlite:///{PACKAGE_ROOT / 'dev.sqlite3'}")

class ProductionConfig(BaseConfig):
    SECRET_KEY = os.getenv("SECRET_KEY")
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY environment variable is not set for production!")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
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
