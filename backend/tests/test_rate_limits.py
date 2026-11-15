"""Per-IP throttling, lockout resistance, registration limits, hashing back-pressure and
production API-surface hardening."""

import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from app.core import security
from app.core.config import Settings
from tests.helpers import PASSWORD, new_user

IP_HEADER = "X-Test-Client-IP"
WRONG = "WrongPassword999"


@pytest.fixture
def ip_settings(auth_settings):
    auth_settings.client_ip_header = IP_HEADER
    auth_settings.login_max_failures = 3
    return auth_settings


def _login(client, email, password, ip="198.51.100.1"):
    return client.post("/api/auth/login", json={"email": email, "password": password}, headers={IP_HEADER: ip})


def test_attacker_cannot_lock_the_real_user_out(client, ip_settings):
    email = new_user(client, "elderly")["user"]["email"]
    for _ in range(3):
        assert _login(client, email, WRONG, ip="203.0.113.66").status_code == 401
    assert _login(client, email, PASSWORD, ip="203.0.113.66").status_code == 429  # the attacker is blocked
    assert _login(client, email, PASSWORD, ip="198.51.100.7").status_code == 200  # the real user is not


def test_one_ip_guessing_many_emails_is_throttled(client, ip_settings):
    ip_settings.login_ip_max_failures = 5
    for i in range(5):
        assert _login(client, f"victim{i}@example.com", WRONG, ip="203.0.113.9").status_code == 401
    res = _login(client, "someone.else@example.com", WRONG, ip="203.0.113.9")
    assert res.status_code == 429
    assert res.json()["detail"].startswith("Too many sign-in attempts")  # same generic message
    assert _login(client, "someone.else@example.com", WRONG, ip="198.51.100.2").status_code == 401


def test_distributed_guessing_hits_the_per_email_backstop(client, ip_settings):
    ip_settings.login_email_max_failures = 10
    email = new_user(client, "elderly")["user"]["email"]
    for i in range(10):
        assert _login(client, email, WRONG, ip=f"203.0.113.{i}").status_code == 401
    assert _login(client, email, PASSWORD, ip="198.51.100.200").status_code == 429


def test_success_clears_only_its_own_ip(client, ip_settings):
    ip_settings.login_email_max_failures = 10
    email = new_user(client, "elderly")["user"]["email"]
    for i in range(2):
        _login(client, email, WRONG, ip=f"203.0.113.{i}")
    assert _login(client, email, PASSWORD, ip="198.51.100.1").status_code == 200
    # The attacker's failures from other IPs still count towards the per-email backstop.
    for i in range(8):
        _login(client, email, WRONG, ip=f"203.0.114.{i}")
    assert _login(client, email, PASSWORD, ip="198.51.100.1").status_code == 429


def test_registration_is_throttled_per_ip(client, ip_settings):
    ip_settings.register_max_per_ip = 2

    def register(n, ip):
        return client.post(
            "/api/auth/register",
            json={"name": "New Person", "email": f"rl{n}@example.com", "password": PASSWORD, "role": "elderly"},
            headers={IP_HEADER: ip},
        )

    assert register(1, "203.0.113.5").status_code == 201
    assert register(2, "203.0.113.5").status_code == 201
    res = register(3, "203.0.113.5")
    assert res.status_code == 429
    assert "Too many accounts" in res.json()["detail"]
    assert register(4, "198.51.100.5").status_code == 201


def test_ip_limits_stay_off_in_production_without_a_trusted_header():
    base = dict(_env_file=None, environment="production", cors_origins="https://app.example")
    assert Settings(**base).ip_limits_active is False  # a shared proxy IP must not become a global lockout
    assert Settings(**base, client_ip_header="CF-Connecting-IP").ip_limits_active is True
    assert Settings(_env_file=None).ip_limits_active is True  # development: the socket address is real


def test_hashing_is_capped_and_overload_returns_busy(monkeypatch):
    monkeypatch.setattr(security, "HASH_WAIT_SECONDS", 0.05)
    security.configure_hashing(1)
    try:
        held, release = threading.Event(), threading.Event()

        def hold_slot():
            with security._hash_slot():
                held.set()
                release.wait(5)

        t = threading.Thread(target=hold_slot)
        t.start()
        held.wait(5)
        with pytest.raises(security.HashingBusyError):
            security.hash_password(PASSWORD)
        release.set()
        t.join()
        assert security.verify_password(PASSWORD, security.hash_password(PASSWORD))
    finally:
        security.configure_hashing(4)


def test_overloaded_hashing_returns_503(client, monkeypatch):
    def busy(*_a, **_k):
        raise security.HashingBusyError

    monkeypatch.setattr("app.api.routes.auth.verify_password", busy)
    res = client.post("/api/auth/login", json={"email": "a@example.com", "password": WRONG})
    assert res.status_code == 503
    assert res.headers["retry-after"] == "5"


def test_cors_does_not_allow_credentials_or_arbitrary_headers(client):
    res = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert "access-control-allow-credentials" not in res.headers
    assert "authorization" in res.headers["access-control-allow-headers"].lower()


def test_production_hides_interactive_api_docs():
    """The app is configured at import time, so check it in a fresh interpreter."""
    env = {
        **os.environ,
        "ENVIRONMENT": "production",
        "DEBUG": "false",
        "CORS_ORIGINS": "https://app.example",
        "NOTIFICATIONS_ENABLED": "false",
    }
    code = "from app.main import app; print(app.docs_url, app.redoc_url, app.openapi_url)"
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=Path(__file__).parents[1], env=env, capture_output=True, text=True, timeout=60
    )
    assert out.stdout.strip() == "None None None", out.stderr
