"""Unit tests for password hashing and JWT handling (no database needed)."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import Settings
from app.core.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    password_needs_rehash,
    verify_password,
)

SECRET = "unit-test-secret-key-that-is-long-enough-xyz"


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, jwt_secret_key=SECRET)


def _encode(settings: Settings, **overrides) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": "507f1f77bcf86cd799439011",
        "role": "elderly",
        "type": "access",
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    payload.update(overrides)
    payload = {k: v for k, v in payload.items() if v is not None}
    return jwt.encode(payload, SECRET, algorithm="HS256")


# ---- Password hashing ----


def test_hash_is_argon2id_and_not_plaintext():
    h = hash_password("CorrectHorse9Battery")
    assert h.startswith("$argon2id$")
    assert "CorrectHorse9Battery" not in h


def test_hash_is_salted():
    assert hash_password("SamePassword123") != hash_password("SamePassword123")


def test_verify_password_correct_and_incorrect():
    h = hash_password("CorrectHorse9Battery")
    assert verify_password("CorrectHorse9Battery", h) is True
    assert verify_password("WrongHorse9Battery", h) is False


def test_verify_password_handles_missing_and_corrupt_hash():
    assert verify_password("anything", None) is False
    assert verify_password("anything", "not-a-hash") is False


def test_fresh_hash_does_not_need_rehash():
    assert password_needs_rehash(hash_password("CorrectHorse9Battery")) is False


# ---- JWT ----


def test_token_roundtrip(settings):
    token, expires_in = create_access_token("abc123", "caretaker", settings)
    payload = decode_access_token(token, settings)
    assert payload["sub"] == "abc123"
    assert payload["role"] == "caretaker"
    assert expires_in == settings.access_token_expire_minutes * 60


def test_expired_token_rejected(settings):
    past = datetime.now(UTC) - timedelta(minutes=10)
    token = _encode(settings, iat=past - timedelta(minutes=5), exp=past)
    with pytest.raises(TokenError) as info:
        decode_access_token(token, settings)
    assert info.value.expired is True


def test_tampered_signature_rejected(settings):
    token, _ = create_access_token("abc123", "elderly", settings)
    header, body, sig = token.split(".")
    tampered = f"{header}.{body}.{sig[:-2]}{'A' if sig[-2] != 'A' else 'B'}{sig[-1]}"
    with pytest.raises(TokenError):
        decode_access_token(tampered, settings)


def test_token_signed_with_other_secret_rejected(settings):
    other = Settings(_env_file=None, jwt_secret_key="a-completely-different-secret-key-0987654321")
    token, _ = create_access_token("abc123", "elderly", other)
    with pytest.raises(TokenError):
        decode_access_token(token, settings)


def test_alg_none_rejected(settings):
    token = jwt.encode({"sub": "abc", "type": "access"}, key=None, algorithm="none")
    with pytest.raises(TokenError):
        decode_access_token(token, settings)


@pytest.mark.parametrize(
    "overrides",
    [{"aud": "someone-else"}, {"iss": "someone-else"}, {"type": "refresh"}, {"sub": None}, {"exp": None}],
)
def test_wrong_claims_rejected(settings, overrides):
    with pytest.raises(TokenError):
        decode_access_token(_encode(settings, **overrides), settings)


def test_garbage_token_rejected(settings):
    with pytest.raises(TokenError):
        decode_access_token("not.a.jwt", settings)


def test_short_secret_rejected_by_settings():
    with pytest.raises(ValueError):
        Settings(_env_file=None, jwt_secret_key="too-short")
