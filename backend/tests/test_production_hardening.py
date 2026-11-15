"""Phase 8 hardening: sign-in throttling and the single-runner scheduler lease."""

from datetime import timedelta

from pymongo import MongoClient

from app.core.time import utc_now
from app.services.scheduler import acquire_lease
from tests.conftest import TEST_MONGODB_URI
from tests.helpers import PASSWORD, new_user


def _login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_login_is_throttled_after_repeated_failures(client, auth_settings):
    auth_settings.login_max_failures = 3
    user = new_user(client, "elderly")
    email = user["user"]["email"]
    for _ in range(3):
        assert _login(client, email, "WrongPassword999").status_code == 401
    # Even the correct password is refused while throttled, and the message reveals nothing.
    res = _login(client, email.upper(), PASSWORD)
    assert res.status_code == 429
    assert "Too many sign-in attempts" in res.json()["detail"]
    # Other accounts are unaffected.
    other = new_user(client, "caretaker")
    assert _login(client, other["user"]["email"], PASSWORD).status_code == 200


def test_unknown_emails_are_throttled_too(client, auth_settings):
    auth_settings.login_max_failures = 3
    for _ in range(3):
        assert _login(client, "nobody@example.com", "WrongPassword999").status_code == 401
    assert _login(client, "nobody@example.com", "WrongPassword999").status_code == 429


def test_successful_login_resets_the_failure_count(client, auth_settings):
    auth_settings.login_max_failures = 3
    email = new_user(client, "elderly")["user"]["email"]
    for _ in range(2):
        _login(client, email, "WrongPassword999")
    assert _login(client, email, PASSWORD).status_code == 200
    for _ in range(2):
        _login(client, email, "WrongPassword999")
    assert _login(client, email, PASSWORD).status_code == 200


def test_scheduler_lease_allows_one_runner_and_fails_over(client, auth_settings):
    db = MongoClient(TEST_MONGODB_URI, tz_aware=True)[auth_settings.mongodb_db_name]
    now, ttl = utc_now(), timedelta(seconds=60)
    assert acquire_lease(db, "instance-a", now, ttl) is True
    assert acquire_lease(db, "instance-b", now, ttl) is False  # A holds it
    assert acquire_lease(db, "instance-a", now + timedelta(seconds=30), ttl) is True  # renewal
    assert acquire_lease(db, "instance-b", now + timedelta(seconds=60), ttl) is False  # renewed by A
    later = now + timedelta(seconds=91)  # A stopped renewing: lease expired
    assert acquire_lease(db, "instance-b", later, ttl) is True
    assert acquire_lease(db, "instance-a", later, ttl) is False
