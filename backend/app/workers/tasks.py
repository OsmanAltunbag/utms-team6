"""
Celery task definitions for auth and legacy wrappers.
Notification delivery is handled by notification_tasks.py (SPEC-020).
"""
import logging

from app.core.config import settings
from app.workers.celery_app import celery_app
from app.workers.email_renderer import render_email
from app.workers.smtp_client import smtp_send

logger = logging.getLogger(__name__)


def send_verification_email_impl(email: str, token: str) -> None:
    logger.info("Attempting to send verification email to %s", email)
    url = f"{settings.FRONTEND_URL}/verify-email/{token}"
    html = render_email(
        "email_verification.html",
        {"title": "E-posta Doğrulama — UTMS", "verify_link": url},
    )
    smtp_send(email, "UTMS — E-posta Adresinizi Doğrulayın", html)
    logger.info("Verification email sent to %s", email)


def send_password_reset_email_impl(email: str, token: str) -> None:
    logger.info("Attempting to send password reset email to %s", email)
    url = f"{settings.FRONTEND_URL}/reset-password/{token}"
    html = render_email(
        "password_reset.html",
        {"title": "Şifre Sıfırlama — UTMS", "reset_link": url},
    )
    smtp_send(email, "UTMS — Şifre Sıfırlama Talebi", html)
    logger.info("Password reset email sent to %s", email)


@celery_app.task(name="app.workers.tasks.placeholder")
def placeholder():
    pass


@celery_app.task(name="app.workers.tasks.send_verification_email", bind=True, max_retries=3)
def send_verification_email(self, email: str, token: str) -> None:
    try:
        send_verification_email_impl(email, token)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="app.workers.tasks.send_password_reset_email", bind=True, max_retries=3)
def send_password_reset_email(self, email: str, token: str) -> None:
    try:
        send_password_reset_email_impl(email, token)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="app.workers.tasks.send_application_confirmation", bind=True, max_retries=3)
def send_application_confirmation(self, user_id: str, tracking_number: str) -> None:
    """
    Deprecated: application submission now uses NotificationService.enqueue.
    Kept for backward compatibility with any queued tasks.
    """
    logger.info(
        "Legacy send_application_confirmation called for user=%s tracking=%s",
        user_id,
        tracking_number,
    )
