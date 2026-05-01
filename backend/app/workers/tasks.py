"""
Celery task definitions.
Implemented progressively per spec (SPEC-007, SPEC-019).
"""

from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.placeholder")
def placeholder():
    """Placeholder — ensures the tasks module is importable."""
    pass
