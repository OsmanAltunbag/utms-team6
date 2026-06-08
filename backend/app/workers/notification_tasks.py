"""
Celery notification worker — SPEC-020.
Handles all transactional email delivery with exponential-backoff retry.
"""
import logging
import smtplib
import uuid
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.workers.celery_app import celery_app
from app.workers.template_renderer import parse_notification_body, render_template

logger = logging.getLogger(__name__)


def _get_sync_session() -> Session:
    engine = create_engine(settings.DATABASE_URL_SYNC, pool_pre_ping=True)
    return Session(engine)


def _smtp_send(to_address: str, subject: str, html_body: str) -> None:
    if settings.BREVO_API_KEY:
        _brevo_api_send(to_address, subject, html_body)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.FROM_EMAIL
    msg["To"] = to_address
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT, timeout=30) as smtp:
        smtp.ehlo()
        if settings.SMTP_USE_TLS:
            smtp.starttls()
            smtp.ehlo()
        if settings.SMTP_USE_TLS and settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
            password = settings.SMTP_PASSWORD.replace(" ", "")
            smtp.login(settings.SMTP_USERNAME, password)
        smtp.sendmail(settings.FROM_EMAIL, [to_address], msg.as_string())


def _brevo_api_send(to_address: str, subject: str, html_body: str) -> None:
    import re, httpx
    # Parse "Name <email>" or plain "email" from FROM_EMAIL setting
    from_raw = settings.FROM_EMAIL or "UTMS <noreply@iyte.edu.tr>"
    match = re.match(r"^(.*?)\s*<(.+?)>\s*$", from_raw)
    if match:
        sender_name, sender_email = match.group(1).strip() or "UTMS", match.group(2)
    else:
        sender_name, sender_email = "UTMS", from_raw.strip()

    response = httpx.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "accept": "application/json",
            "api-key": settings.BREVO_API_KEY,
            "content-type": "application/json",
        },
        json={
            "sender": {"name": sender_name, "email": sender_email},
            "to": [{"email": to_address}],
            "subject": subject,
            "htmlContent": html_body,
        },
        timeout=30,
    )
    response.raise_for_status()


def _render_html(subject: str, body: str) -> str:
    template_name, variables, plain = parse_notification_body(body)
    if template_name:
        variables.setdefault("title", subject or "UTMS Bildirimi")
        return render_template(template_name, variables)
    from app.workers.template_renderer import _env
    return _env.get_template("base.html").render(
        title=subject or "UTMS Bildirimi",
        body_content=f'<p style="color:#444;font-size:15px;line-height:1.7;">{plain}</p>',
    )


@celery_app.task(
    name="app.workers.notification_tasks.send_notification",
    bind=True,
    max_retries=5,
    default_retry_delay=60,
    acks_late=True,
)
def send_notification(self, notification_id: str) -> None:
    from app.domain.notification import Notification
    from app.domain.enums import NotifStatus

    session = _get_sync_session()
    try:
        notif = session.execute(
            select(Notification)
            .options(selectinload(Notification.user))
            .where(Notification.id == uuid.UUID(notification_id))
        ).scalar_one_or_none()
        if notif is None:
            logger.error("Notification %s not found", notification_id)
            return

        if notif.status == NotifStatus.SENT:
            return

        to_address = notif.user.email
        subject = notif.subject or "UTMS Bildirimi"
        html_body = _render_html(subject, notif.body)

        if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
            # Local dev: no SMTP — deliver in-app only, mark as sent so the
            # applicant Messages tab shows a completed notification.
            logger.warning(
                "SMTP not configured — notification %s recorded for %s (email skipped)",
                notification_id,
                to_address,
            )
        else:
            _smtp_send(to_address, subject, html_body)
            logger.info("Notification %s emailed to %s", notification_id, to_address)

        notif.status = NotifStatus.SENT
        notif.sent_at = datetime.now(timezone.utc)
        session.commit()

    except Exception as exc:
        session.rollback()
        try:
            notif = session.get(Notification, uuid.UUID(notification_id))
            if notif:
                notif.retry_count = (notif.retry_count or 0) + 1
                if notif.retry_count >= notif.max_retries:
                    notif.status = NotifStatus.FAILED
                    logger.error(
                        "Notification %s failed after %s retries: %s",
                        notification_id,
                        notif.retry_count,
                        exc,
                    )
                session.commit()
        except Exception:
            pass

        if self.request.retries >= self.max_retries:
            return

        delay = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=delay)
    finally:
        session.close()
