from celery import Celery

def make_celery() -> Celery:
    celery = Celery(
        "smartscripts",
        broker="redis://localhost:6379/0",
        backend="redis://localhost:6379/1",
        include=[
            "smartscripts.tasks.ocr_tasks",
            "smartscripts.tasks.grade_tasks",
            "smartscripts.utils.pdf_helpers",
            "smartscripts.ai.marking_pipeline",
        ],
    )

    # Strict JSON-only config
    celery.conf.update(
        task_track_started=True,
        task_serializer="json",
        accept_content=["json"],  # only allow JSON (avoid pickle)
        result_serializer="json",
        timezone="Africa/Kampala",
        enable_utc=True,
    )

    # Autodiscover tasks inside smartscripts.*
    celery.autodiscover_tasks(["smartscripts"])

    return celery


celery = make_celery()
