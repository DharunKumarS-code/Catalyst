"""Integration tests for registration, login, token validation and role-based access."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.db.indexes import USERS_COLLECTION
from app.db.mongodb import mongodb
from tests.conftest import TEST_SECRET

PASSWORD = "SafePassword123"


def register(client, email="jane@example.com", role="elderly", password=PASSWORD, name="Jane Doe"):
    return client.post("/api/auth/register", json={"name": name, "email": email, "password": password, "role": role})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def token_for(client, role, email=None):
    res = register(client, email=email or f"{role}@example.com", role=role)
    assert res.status_code == 201, res.text
    return res.json()["access_token"]


# ---- Registration ----

def test_register_success(client, auth_settings):
    res = register(client)
    assert res.status_code == 201
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "jane@example.com"
    assert body["user"]["role"] == "elderly"
    assert "password" not in res.text and "password_hash" not in res.text

    stored = mongodb.db[USERS_COLLECTION].find_one({"email": "jane@example.com"})
    assert stored["password_hash"].startswith("$argon2id$")
    assert PASSWORD not in str(stored)


@pytest.mark.parametrize("role", ["elderly", "caretaker", "family_member"])
def test_register_all_roles(client, role):
    res = register(client, email=f"{role}@example.com", role=role)
    assert res.status_code == 201
    assert res.json()["user"]["role"] == role


def test_duplicate_email_rejected_case_insensitive(client):
    assert register(client, email="  Jane.Doe@Example.COM ").status_code == 201
    res = register(client, email="jane.doe@example.com")
    assert res.status_code == 409
    assert mongodb.db[USERS_COLLECTION].count_documents({}) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "Jane", "email": "not-an-email", "password": PASSWORD, "role": "elderly"},
        {"name": "Jane", "email": "j@example.com", "password": "short1A", "role": "elderly"},
        {"name": "Jane", "email": "j@example.com", "password": "alllowercase123", "role": "elderly"},
        {"name": "Jane", "email": "j@example.com", "password": "NoDigitsHereAtAll", "role": "elderly"},
        {"name": "Jane", "email": "j@example.com", "password": PASSWORD, "role": "admin"},
        {"name": "   ", "email": "j@example.com", "password": PASSWORD, "role": "elderly"},
        {"name": "12345", "email": "j@example.com", "password": PASSWORD, "role": "elderly"},
        {"name": "Jane", "email": "j@example.com", "password": PASSWORD, "role": "elderly", "is_admin": True},
        {"email": "j@example.com", "password": PASSWORD, "role": "elderly"},
    ],
)
def test_register_validation(client, payload):
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 422
    # Validation errors must not echo submitted values (e.g. passwords).
    assert PASSWORD not in res.text and "short1A" not in res.text


# ---- Login ----

def test_login_success(client):
    register(client)
    res = client.post("/api/auth/login", json={"email": "JANE@example.com", "password": PASSWORD})
    assert res.status_code == 200
    body = res.json()
    assert body["user"]["email"] == "jane@example.com"
    assert "password_hash" not in res.text
    me = client.get("/api/auth/me", headers=bearer(body["access_token"]))
    assert me.status_code == 200
    assert me.json()["role"] == "elderly"
    # Timestamps read back from MongoDB must be timezone-aware (UTC).
    assert me.json()["created_at"].endswith(("Z", "+00:00"))


def test_login_wrong_password_and_unknown_email_are_indistinguishable(client):
    register(client)
    wrong = client.post("/api/auth/login", json={"email": "jane@example.com", "password": "WrongPassword123"})
    unknown = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "Invalid email or password."}


# ---- Token validation / unauthorized access ----

def test_me_requires_token(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401
    assert res.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("header", ["Bearer not-a-jwt", "Basic dXNlcjpwYXNz", "Bearer "])
def test_me_rejects_bad_authorization_header(client, header):
    assert client.get("/api/auth/me", headers={"Authorization": header}).status_code == 401


def test_expired_token_rejected(client, auth_settings):
    user_id = register(client).json()["user"]["id"]
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    token = jwt.encode(
        {"sub": user_id, "role": "elderly", "type": "access", "iss": auth_settings.jwt_issuer,
         "aud": auth_settings.jwt_audience, "iat": past - timedelta(minutes=30), "exp": past},
        TEST_SECRET, algorithm="HS256",
    )
    res = client.get("/api/auth/me", headers=bearer(token))
    assert res.status_code == 401
    assert res.json()["detail"] == "Token has expired."


def test_forged_token_rejected(client, auth_settings):
    user_id = register(client).json()["user"]["id"]
    now = datetime.now(timezone.utc)
    forged = jwt.encode(
        {"sub": user_id, "role": "caretaker", "type": "access", "iss": auth_settings.jwt_issuer,
         "aud": auth_settings.jwt_audience, "iat": now, "exp": now + timedelta(minutes=5)},
        "attacker-controlled-secret-key-with-enough-length", algorithm="HS256",
    )
    assert client.get("/api/portal/caretaker", headers=bearer(forged)).status_code == 401


def test_token_for_deleted_user_rejected(client):
    token = token_for(client, "elderly")
    mongodb.db[USERS_COLLECTION].delete_many({})
    assert client.get("/api/auth/me", headers=bearer(token)).status_code == 401


# ---- Role-based access control ----

@pytest.mark.parametrize(
    "role,allowed",
    [
        ("elderly", {"elderly"}),
        ("caretaker", {"caretaker", "care-team"}),
        ("family_member", {"family", "care-team"}),
    ],
)
def test_role_based_access(client, role, allowed):
    token = token_for(client, role)
    for area in ["elderly", "caretaker", "family", "care-team"]:
        res = client.get(f"/api/portal/{area}", headers=bearer(token))
        expected = 200 if area in allowed else 403
        assert res.status_code == expected, f"{role} -> {area}: {res.status_code}"


def test_portal_requires_authentication(client):
    for area in ["elderly", "caretaker", "family", "care-team"]:
        assert client.get(f"/api/portal/{area}").status_code == 401


def test_role_claim_in_token_is_not_trusted(client, auth_settings):
    """A validly signed token claiming a different role must not grant that role:
    the role is always read from the stored user record."""
    user_id = register(client, role="elderly").json()["user"]["id"]
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": user_id, "role": "caretaker", "type": "access", "iss": auth_settings.jwt_issuer,
         "aud": auth_settings.jwt_audience, "iat": now, "exp": now + timedelta(minutes=5)},
        TEST_SECRET, algorithm="HS256",
    )
    assert client.get("/api/portal/caretaker", headers=bearer(token)).status_code == 403
    assert client.get("/api/portal/elderly", headers=bearer(token)).status_code == 200


def test_auth_returns_503_when_secret_not_configured(client, auth_settings):
    from app.core.config import get_settings
    from app.main import app

    unconfigured = auth_settings.model_copy(update={"jwt_secret_key": None})
    app.dependency_overrides[get_settings] = lambda: unconfigured
    res = register(client)
    assert res.status_code == 503
