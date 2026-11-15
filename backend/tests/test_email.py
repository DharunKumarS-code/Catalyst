"""SmtpSender behaviour with a stubbed smtplib (no network)."""

import smtplib

import pytest

from app.core.config import Settings
from app.services import email as email_mod
from app.services.email import DeliveryError, SmtpSender


class StubSMTP:
    instances: list["StubSMTP"] = []
    fail: Exception | None = None

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port, self.calls = host, port, []
        StubSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(("login", user, password))
        if isinstance(StubSMTP.fail, smtplib.SMTPAuthenticationError):
            raise StubSMTP.fail

    def send_message(self, msg):
        if StubSMTP.fail and not isinstance(StubSMTP.fail, smtplib.SMTPAuthenticationError):
            raise StubSMTP.fail
        self.calls.append(("send", msg["To"], msg["Subject"], msg["From"]))


@pytest.fixture
def stub(monkeypatch):
    StubSMTP.instances, StubSMTP.fail = [], None
    monkeypatch.setattr(email_mod.smtplib, "SMTP", StubSMTP)
    monkeypatch.setattr(email_mod.smtplib, "SMTP_SSL", StubSMTP)
    return StubSMTP


def settings(**over):
    return Settings(
        _env_file=None,
        email_mode="smtp",
        smtp_host="smtp.example.test",
        smtp_from="noreply@example.test",
        smtp_username="user",
        smtp_password="s3cret-pass",
        **over,
    )


def test_settings_flags():
    assert Settings(_env_file=None).email_delivery_active is False  # safe default: preview
    assert settings().email_delivery_active is True
    assert "s3cret-pass" not in repr(settings())  # SecretStr


def test_send_uses_starttls_and_login(stub):
    SmtpSender(settings()).send("a@example.org", "Hi", "Body")
    calls = stub.instances[0].calls
    assert calls[0] == "starttls" and calls[1] == ("login", "user", "s3cret-pass")
    assert calls[2] == ("send", "a@example.org", "Hi", "noreply@example.test")


@pytest.mark.parametrize(
    "error, message",
    [
        (smtplib.SMTPAuthenticationError(535, b"bad"), "The mail server rejected the login."),
        (smtplib.SMTPRecipientsRefused({"a@example.org": (550, b"no")}), "The recipient address was rejected."),
        (smtplib.SMTPDataError(554, b"x"), "Mail server error (SMTPDataError)."),
        (ConnectionRefusedError(), "Could not connect to the mail server."),
    ],
)
def test_failures_become_safe_messages(stub, error, message):
    stub.fail = error
    with pytest.raises(DeliveryError) as exc:
        SmtpSender(settings()).send("a@example.org", "Hi", "Body")
    assert str(exc.value) == message
    assert "s3cret" not in str(exc.value) and "smtp.example.test" not in str(exc.value)
