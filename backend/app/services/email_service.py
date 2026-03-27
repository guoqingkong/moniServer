import smtplib
from email.message import EmailMessage

from app.config import Settings


class EmailService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def is_configured(self) -> bool:
        return all(
            [
                self._settings.smtp_host,
                self._settings.smtp_username,
                self._settings.smtp_password,
                self._settings.smtp_from_email,
                self._settings.bandwidth_alert_recipient,
            ]
        )

    def send(self, subject: str, body: str, recipient: str) -> None:
        if not self.is_configured:
            raise RuntimeError("SMTP is not configured.")

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self._settings.smtp_from_email
        message["To"] = recipient
        message.set_content(body)

        if self._settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(self._settings.smtp_host, self._settings.smtp_port) as server:
                server.login(self._settings.smtp_username, self._settings.smtp_password)
                server.send_message(message)
            return

        with smtplib.SMTP(self._settings.smtp_host, self._settings.smtp_port) as server:
            server.starttls()
            server.login(self._settings.smtp_username, self._settings.smtp_password)
            server.send_message(message)
