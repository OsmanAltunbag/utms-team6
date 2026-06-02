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

import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_HEADER_COLOR = "#1a3a6b"
_BTN_COLOR = "#1a3a6b"


# ---------------------------------------------------------------------------
# Sync DB helper (Celery workers are synchronous)
# ---------------------------------------------------------------------------

def _get_sync_session() -> Session:
    engine = create_engine(settings.DATABASE_URL_SYNC, pool_pre_ping=True)
    return Session(engine)


# ---------------------------------------------------------------------------
# SMTP helper
# ---------------------------------------------------------------------------

def _smtp_send(to_address: str, subject: str, html_body: str) -> None:
    if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
        raise RuntimeError("SMTP credentials are not configured")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.FROM_EMAIL
    msg["To"] = to_address
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    password = settings.SMTP_PASSWORD.replace(" ", "")
    with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(settings.SMTP_USERNAME, password)
        smtp.sendmail(settings.FROM_EMAIL, [to_address], msg.as_string())


def _wrap_html(title: str, body_content: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="tr">
<head><meta charset="UTF-8"><title>{title}</title></head>
<body style="margin:0;padding:0;background:#f0f4f8;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="padding:40px 0;background:#f0f4f8;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0"
             style="background:#fff;border-radius:10px;overflow:hidden;
                    box-shadow:0 4px 16px rgba(0,0,0,.1);max-width:600px;width:100%;">
        <tr>
          <td style="background:{_HEADER_COLOR};padding:32px 40px;text-align:center;">
            <p style="margin:0;color:#a0b8d8;font-size:13px;letter-spacing:1px;text-transform:uppercase;">
              İzmir Yüksek Teknoloji Enstitüsü
            </p>
            <h1 style="margin:8px 0 0;color:#fff;font-size:20px;font-weight:700;">
              UTMS
            </h1>
          </td>
        </tr>
        <tr>
          <td style="padding:40px 40px 32px;">
            {body_content}
          </td>
        </tr>
        <tr>
          <td style="background:#f7f9fc;border-top:1px solid #e8ecf0;padding:24px 40px;text-align:center;">
            <p style="margin:0;color:#8a9ab0;font-size:12px;">
              Bu e-posta otomatik olarak gönderilmiştir. Lütfen yanıtlamayınız.<br>
              &copy; 2026 UTMS — İzmir Yüksek Teknoloji Enstitüsü
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Main Celery task
# ---------------------------------------------------------------------------

@celery_app.task(
    name="app.workers.notification_tasks.send_notification",
    bind=True,
    max_retries=5,
    task_acks_late=True,
)
def send_notification(self, notification_id: str) -> None:
    from app.domain.notification import Notification
    from app.domain.enums import NotifStatus

    session = _get_sync_session()
    try:
        notif = session.get(Notification, uuid.UUID(notification_id))
        if notif is None:
            logger.error("Notification %s not found", notification_id)
            return

        if notif.status == NotifStatus.SENT:
            return

        user = notif.user
        to_address = user.email

        html_body = _wrap_html(
            notif.subject or "UTMS Bildirimi",
            notif.body,
        )

        _smtp_send(to_address, notif.subject or "UTMS Bildirimi", html_body)

        notif.status = NotifStatus.SENT
        notif.sent_at = datetime.now(timezone.utc)
        session.commit()
        logger.info("Notification %s sent to %s", notification_id, to_address)

    except Exception as exc:
        session.rollback()
        try:
            from app.domain.notification import Notification
            from app.domain.enums import NotifStatus
            notif = session.get(Notification, uuid.UUID(notification_id))
            if notif:
                notif.retry_count = (notif.retry_count or 0) + 1
                if notif.retry_count >= notif.max_retries:
                    notif.status = NotifStatus.FAILED
                session.commit()
        except Exception:
            pass

        delay = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=delay)
    finally:
        session.close()
