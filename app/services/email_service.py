import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import settings
from app.database import log_event


def send_notification(subject: str, body: str):
    """Send an email notification. Fails silently if SMTP not configured."""
    if not settings.smtp_user or not settings.notification_email:
        return

    try:
        msg = MIMEMultipart()
        msg["From"] = settings.smtp_user
        msg["To"] = settings.notification_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)

        log_event("email", f"Notification sent: {subject}")
    except Exception as e:
        log_event("error", f"Email failed: {str(e)}")
