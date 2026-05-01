"""
Celery task definitions.
"""
import logging

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.tasks.placeholder")
def placeholder():
    pass


@celery_app.task(name="app.workers.tasks.send_verification_email", bind=True, max_retries=3)
def send_verification_email(self, email: str, token: str) -> None:
    """Send email verification link to the given address."""
    try:
        verification_url = f"https://utms.iyte.edu.tr/verify-email/{token}"
        logger.info("Sending verification email to %s: %s", email, verification_url)
        # TODO(SPEC-019): integrate real SMTP via settings.SMTP_*
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="app.workers.tasks.send_password_reset_email", bind=True, max_retries=3)
def send_password_reset_email(self, email: str, token: str) -> None:
    """Send password reset link to the given address."""
    try:
        reset_url = f"https://utms.iyte.edu.tr/reset-password/{token}"
        logger.info("Sending password reset email to %s: %s", email, reset_url)
        # TODO(SPEC-019): integrate real SMTP via settings.SMTP_*
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
