"""
smartscripts/celery_worker.py
Entry point for running Celery workers on Windows.
Ensures Celery shares Flask app context and full configuration.
"""

from smartscripts.app import create_app
from smartscripts.extensions import celery, make_celery

# Create the Flask app
flask_app = create_app("development")  # or "production"

# Bind Celery to Flask context
make_celery(flask_app)

# Debug confirmation
print("✅ Celery configured with broker:", celery.conf.broker_url)
print("✅ Celery result backend:", celery.conf.result_backend)
