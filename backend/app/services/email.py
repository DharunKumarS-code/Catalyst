"""SMTP delivery. Credentials come only from backend settings and never appear in errors or logs."""

import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import Settings


class DeliveryError(Exception):
    """A safe, user-presentable failure reason (no hosts, usernames or secrets)."""


class SmtpSender:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send(self, to: str, subject: str, body: str) -> None:
        s = self.settings
        msg = EmailMessage()
        msg["From"] = s.smtp_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        try:
            context = ssl.create_default_context()
            if s.smtp_security == "ssl":
                server: smtplib.SMTP = smtplib.SMTP_SSL(
                    s.smtp_host, s.smtp_port, timeout=s.smtp_timeout_seconds, context=context
                )
            else:
                server = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=s.smtp_timeout_seconds)
            with server:
                if s.smtp_security == "starttls":
                    server.starttls(context=context)
                password = s.smtp_password.get_secret_value() if s.smtp_password else ""
                if s.smtp_username and password:
                    server.login(s.smtp_username, password)
                server.send_message(msg)
        except smtplib.SMTPAuthenticationError:
            raise DeliveryError("The mail server rejected the login.") from None
        except smtplib.SMTPRecipientsRefused:
            raise DeliveryError("The recipient address was rejected.") from None
        except smtplib.SMTPException as exc:
            raise DeliveryError(f"Mail server error ({type(exc).__name__}).") from None
        except (TimeoutError, OSError):
            raise DeliveryError("Could not connect to the mail server.") from None
