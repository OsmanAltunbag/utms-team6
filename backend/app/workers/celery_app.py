"""
Celery application instance.
Full task implementations will be added in SPEC-019.
"""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "utms",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "app.workers.tasks.*": {"queue": "default"},
    },
)
