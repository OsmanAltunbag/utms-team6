"""
Celery task definitions.
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_HEADER_COLOR = "#1a3a6b"
_BTN_COLOR = "#1a3a6b"


def _base_html(title: str, body_content: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background-color:#f0f4f8;font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f0f4f8;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0"
               style="background:#ffffff;border-radius:10px;overflow:hidden;
                      box-shadow:0 4px 16px rgba(0,0,0,0.10);max-width:600px;width:100%;">

          <!-- Header -->
          <tr>
            <td style="background-color:{_HEADER_COLOR};padding:32px 40px;text-align:center;">
              <p style="margin:0;color:#a0b8d8;font-size:13px;letter-spacing:1px;
                         text-transform:uppercase;">İzmir Institute of Technology</p>
              <h1 style="margin:8px 0 0;color:#ffffff;font-size:20px;font-weight:700;
                          line-height:1.3;">
                Undergraduate Transfer Management System<br>
                <span style="font-size:14px;font-weight:400;color:#a0b8d8;">(UTMS)</span>
              </h1>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:40px 40px 32px;">
              {body_content}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color:#f7f9fc;border-top:1px solid #e8ecf0;
                        padding:24px 40px;text-align:center;">
              <p style="margin:0;color:#8a9ab0;font-size:12px;line-height:1.6;">
                Bu e-posta otomatik olarak gönderilmiştir. Lütfen yanıtlamayınız.<br>
                &copy; 2026 UTMS — İzmir Institute of Technology
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _smtp_send(to_address: str, subject: str, html_body: str) -> None:
    """Low-level SMTP send — raises on failure."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.FROM_EMAIL
    msg["To"] = to_address
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        smtp.sendmail(settings.FROM_EMAIL, [to_address], msg.as_string())


# ---------------------------------------------------------------------------
# Standalone implementations — called by both BackgroundTasks and Celery tasks
# ---------------------------------------------------------------------------

def send_verification_email_impl(email: str, token: str) -> None:
    """Send a verification email. Usable directly via BackgroundTasks."""
    logger.info("Attempting to send verification email to %s", email)
    url = f"{settings.FRONTEND_URL}/verify-email/{token}"
    body = f"""
      <h2 style="margin:0 0 16px;color:#1a3a6b;font-size:22px;">E-posta Adresinizi Doğrulayın</h2>
      <p style="margin:0 0 12px;color:#444;font-size:15px;line-height:1.7;">
        UTMS'e hoş geldiniz! Hesabınızı etkinleştirmek için aşağıdaki butona tıklayın.
      </p>
      <p style="margin:0 0 28px;color:#666;font-size:14px;line-height:1.6;">
        Bu bağlantı <strong>24 saat</strong> geçerlidir. Süre dolmadan işlemi tamamlamanız gerekmektedir.
      </p>
      <table cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
        <tr>
          <td style="border-radius:6px;background-color:{_BTN_COLOR};">
            <a href="{url}"
               style="display:inline-block;padding:14px 36px;color:#ffffff;
                      font-size:15px;font-weight:700;text-decoration:none;
                      border-radius:6px;">
              E-postamı Doğrula
            </a>
          </td>
        </tr>
      </table>
      <p style="margin:0;color:#999;font-size:12px;line-height:1.6;">
        Butona tıklanamıyorsa aşağıdaki bağlantıyı tarayıcınıza yapıştırın:<br>
        <a href="{url}" style="color:#1a3a6b;word-break:break-all;">{url}</a>
      </p>
      <hr style="border:none;border-top:1px solid #eee;margin:28px 0;">
      <p style="margin:0;color:#bbb;font-size:12px;">
        Bu isteği siz yapmadıysanız bu e-postayı görmezden gelebilirsiniz.
      </p>
    """
    try:
        _smtp_send(email, "UTMS — E-posta Adresinizi Doğrulayın", _base_html("E-posta Doğrulama — UTMS", body))
        logger.info("✅ SUCCESS: Verification email sent to %s", email)
    except Exception as e:
        logger.error("❌ ERROR: Failed to send email to %s. Reason: %s", email, e)
        raise


def send_password_reset_email_impl(email: str, token: str) -> None:
    """Send a password reset email. Usable directly via BackgroundTasks."""
    logger.info("Attempting to send password reset email to %s", email)
    url = f"{settings.FRONTEND_URL}/reset-password/{token}"
    body = f"""
      <h2 style="margin:0 0 16px;color:#1a3a6b;font-size:22px;">Şifrenizi Sıfırlayın</h2>
      <p style="margin:0 0 12px;color:#444;font-size:15px;line-height:1.7;">
        UTMS hesabınız için bir şifre sıfırlama talebi aldık.
      </p>
      <p style="margin:0 0 28px;color:#666;font-size:14px;line-height:1.6;">
        Bu bağlantı <strong>30 dakika</strong> geçerlidir. Şifrenizi sıfırlamak için aşağıdaki butona tıklayın.
      </p>
      <table cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
        <tr>
          <td style="border-radius:6px;background-color:{_BTN_COLOR};">
            <a href="{url}"
               style="display:inline-block;padding:14px 36px;color:#ffffff;
                      font-size:15px;font-weight:700;text-decoration:none;
                      border-radius:6px;">
              Şifremi Sıfırla
            </a>
          </td>
        </tr>
      </table>
      <p style="margin:0;color:#999;font-size:12px;line-height:1.6;">
        Butona tıklanamıyorsa aşağıdaki bağlantıyı tarayıcınıza yapıştırın:<br>
        <a href="{url}" style="color:#1a3a6b;word-break:break-all;">{url}</a>
      </p>
      <hr style="border:none;border-top:1px solid #eee;margin:28px 0;">
      <p style="margin:0;color:#bbb;font-size:12px;">
        Bu isteği siz yapmadıysanız şifreniz değişmeyecektir. Bu e-postayı görmezden gelebilirsiniz.
      </p>
    """
    try:
        _smtp_send(email, "UTMS — Şifre Sıfırlama Talebi", _base_html("Şifre Sıfırlama — UTMS", body))
        logger.info("✅ SUCCESS: Password reset email sent to %s", email)
    except Exception as e:
        logger.error("❌ ERROR: Failed to send email to %s. Reason: %s", email, e)
        raise


# ---------------------------------------------------------------------------
# Celery task wrappers (enqueue via .delay() for async processing)
# ---------------------------------------------------------------------------

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
