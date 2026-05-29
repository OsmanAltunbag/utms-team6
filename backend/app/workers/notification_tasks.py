"""
Celery notification delivery task (SPEC-020).
"""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.enums import NotifStatus
from app.domain.notification import Notification
from app.domain.user import User
from app.workers.celery_app import celery_app
from app.workers.email_renderer import render_email
from app.workers.smtp_client import smtp_send

logger = logging.getLogger(__name__)

RETRY_BASE_SECONDS = 60


def _retry_delay(retry_count: int) -> int:
    """Exponential backoff: 60, 120, 240, 480, 960 seconds."""
    return RETRY_BASE_SECONDS * (2 ** retry_count)


def _build_html(notification: Notification) -> str:
    if notification.template_name:
        context = dict(notification.template_context or {})
        context.setdefault("title", notification.subject or "UTMS Notification")
        if "note" not in context and notification.body:
            context.setdefault("note", notification.body)
        return render_email(notification.template_name, context)

    return render_email(
        "status_changed.html",
        {
            "title": notification.subject or "UTMS Notification",
            "old_status": "—",
            "new_status": notification.subject or "Update",
            "note": notification.body,
        },
    )


def send_notification_impl(notification_id: str) -> None:
    """Load notification, render template, send via SMTP, update status."""
    engine = create_engine(settings.DATABASE_URL_SYNC)

    with Session(engine) as session:
        notif = session.get(Notification, uuid.UUID(notification_id))
        if notif is None:
            logger.error("Notification %s not found", notification_id)
            return

        if notif.status == NotifStatus.SENT:
            logger.info("Notification %s already sent, skipping", notification_id)
            return

        user = session.get(User, notif.user_id)
        if user is None:
            notif.status = NotifStatus.FAILED
            notif.error_message = "Recipient user not found"
            session.commit()
            logger.error("User %s not found for notification %s", notif.user_id, notification_id)
            return

        html = _build_html(notif)
        subject = notif.subject or "UTMS Notification"

        try:
            smtp_send(user.email, subject, html)
            notif.status = NotifStatus.SENT
            notif.sent_at = datetime.now(timezone.utc)
            notif.error_message = None
            session.commit()
            logger.info("Notification %s sent to %s", notification_id, user.email)
        except Exception as exc:
            notif.retry_count += 1
            notif.error_message = str(exc)
            if notif.retry_count >= notif.max_retries:
                notif.status = NotifStatus.FAILED
                session.commit()
                logger.error(
                    "Notification %s failed permanently after %s attempts: %s",
                    notification_id,
                    notif.retry_count,
                    exc,
                )
            else:
                session.commit()
                logger.warning(
                    "Notification %s attempt %s failed: %s",
                    notification_id,
                    notif.retry_count,
                    exc,
                )
            raise


@celery_app.task(
    name="app.workers.notification_tasks.send_notification",
    bind=True,
    max_retries=5,
    default_retry_delay=RETRY_BASE_SECONDS,
)
def send_notification(self, notification_id: str) -> None:
    try:
        send_notification_impl(notification_id)
    except Exception as exc:
        delay = _retry_delay(self.request.retries)
        raise self.retry(exc=exc, countdown=delay)
