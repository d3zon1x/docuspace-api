import logging
import smtplib
from email.message import EmailMessage

from app.core.config import Settings

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build_verification_url(self, token: str) -> str:
        """Construct the full verification link for `GET /auth/verify`."""
        base = self._settings.public_base_url.rstrip("/")
        return f"{base}/auth/verify?token={token}"

    def send_verification_email(self, *, recipient_email: str, login: str, token: str) -> str:
        """Send an email verification link to a newly registered user and return the URL."""
        verify_url = self.build_verification_url(token)
        subject = f"[{self._settings.app_name}] Verify your email address"
        body = (
            f"Hello {login},\n\n"
            f"Please verify your email address by opening the link below:\n"
            f"{verify_url}\n\n"
            f"If you did not register on {self._settings.app_name}, you can ignore this message."
        )
        self._deliver(recipient_email=recipient_email, subject=subject, body=body)
        return verify_url

    def _deliver(self, *, recipient_email: str, subject: str, body: str) -> None:
        """Deliver an email via SMTP when enabled, otherwise log it."""
        if not self._settings.smtp_enabled:
            logger.info(
                "SMTP disabled; email logged instead of sent",
                extra={"to": recipient_email, "subject": subject, "body": body},
            )
            return

        msg = EmailMessage()
        msg["From"] = self._settings.smtp_from_email
        msg["To"] = recipient_email
        msg["Subject"] = subject
        msg.set_content(body)

        with smtplib.SMTP(
            host=self._settings.smtp_host,
            port=self._settings.smtp_port,
            timeout=10,
        ) as smtp:
            if self._settings.smtp_use_tls:
                smtp.starttls()
            if self._settings.smtp_username:
                smtp.login(self._settings.smtp_username, self._settings.smtp_password)
            smtp.send_message(msg)
