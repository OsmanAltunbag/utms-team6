import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings


def smtp_send(to_address: str, subject: str, html_body: str) -> None:
    """Send HTML email via SMTP. Raises on failure."""
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
