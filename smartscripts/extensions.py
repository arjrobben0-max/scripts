from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from celery import Celery

# Initialize Flask extensions (singletons)
db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
migrate = Migrate()

# Placeholder Celery instance (will be configured in create_app)
celery = Celery(__name__)


def make_celery(app):
    """Create and configure a new Celery instance tied to the Flask app context."""
    celery.conf.update(
        broker_url=app.config.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
        result_backend=app.config.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1'),
        task_track_started=True,
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone=app.config.get('CELERY_TIMEZONE', 'Africa/Kampala'),
        enable_utc=app.config.get('CELERY_ENABLE_UTC', True),
    )

    # Ensure tasks run within Flask app context
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery


def configure_login_manager(app):
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "Please log in to access this page."


__all__ = [
    'db',
    'login_manager',
    'mail',
    'migrate',
    'celery',
    'make_celery',
    'configure_login_manager',
]
