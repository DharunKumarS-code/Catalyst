"""Password hashing (Argon2id) and JWT access-token handling."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import Settings

# argon2-cffi defaults follow RFC 9106 recommendations; Type.ID selects Argon2id explicitly.
_hasher = PasswordHasher(type=Type.ID)

# Used to equalise response time when an email is not registered, so timing
# does not reveal whether an account exists.
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing-equalisation")

TOKEN_TYPE_ACCESS = "access"


class HashingBusyError(Exception):
    """Too many password hashes are running; the request should be retried shortly (503)."""


# Each Argon2 hash uses ~64 MiB, so concurrent hashes are capped (configure_hashing at startup).
HASH_WAIT_SECONDS = 10
_hash_slots = threading.BoundedSemaphore(4)


def configure_hashing(max_concurrent: int) -> None:
    global _hash_slots
    _hash_slots = threading.BoundedSemaphore(max_concurrent)


@contextmanager
def _hash_slot():
    slots = _hash_slots
    if not slots.acquire(timeout=HASH_WAIT_SECONDS):
        raise HashingBusyError
    try:
        yield
    finally:
        slots.release()


def hash_password(password: str) -> str:
    with _hash_slot():
        return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Return True if the password matches. Never raises for bad input
    (raises HashingBusyError only when the server is overloaded)."""
    with _hash_slot():
        try:
            return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return False


class TokenError(Exception):
    """Raised when a token is invalid. `expired` distinguishes expiry from other failures."""

    def __init__(self, message: str, *, expired: bool = False) -> None:
        super().__init__(message)
        self.expired = expired


def create_access_token(subject: str, role: str, settings: Settings) -> tuple[str, int]:
    """Return (token, expires_in_seconds)."""
    if settings.jwt_secret_key is None:
        raise RuntimeError("JWT_SECRET_KEY is not configured.")
    now = datetime.now(UTC)
    expires_in = settings.access_token_expire_minutes * 60
    payload = {
        "sub": subject,
        "role": role,
        "type": TOKEN_TYPE_ACCESS,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    token = jwt.encode(payload, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm)
    return token, expires_in


def decode_access_token(token: str, settings: Settings) -> dict:
    """Verify signature, expiry, issuer, audience and token type. Raises TokenError."""
    if settings.jwt_secret_key is None:
        raise RuntimeError("JWT_SECRET_KEY is not configured.")
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],  # pinned: rejects "none" and algorithm confusion
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token has expired.", expired=True) from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("Invalid authentication token.") from exc

    if payload.get("type") != TOKEN_TYPE_ACCESS:
        raise TokenError("Invalid authentication token.")
    return payload
