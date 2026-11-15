"""Demo accounts: provisioning, idempotency, logins, role permissions and isolation."""

import pytest
from fastapi import APIRouter, Depends

from app.api.deps import get_non_demo_user, require_roles
from app.core.config import Settings
from app.db.indexes import USERS_COLLECTION
from app.db.mongodb import mongodb
from app.demo.accounts import DEMO_ACCOUNTS
from app.demo.provisioning import DemoProvisioningDisabledError, ProvisionStatus, provision_demo_accounts
from app.main import app
from app.repositories.users import UserRepository
from app.schemas.user import Role

CREDENTIALS = {
    "elderly": ("elderly.demo@eldercare.com", "ElderDemo2026!"),
    "caretaker": ("caretaker.demo@eldercare.com", "CareDemo2026!"),
    "family_member": ("family.demo@eldercare.com", "FamilyDemo2026!"),
}
# role -> portal areas it may access
ALLOWED = {
    "elderly": {"elderly"},
    "caretaker": {"caretaker", "care-team"},
    "family_member": {"family", "care-team"},
}

# Test-only route standing in for a future endpoint that exposes real user data.
_real_data = APIRouter()


@_real_data.get("/api/_test/real-data")
def _real_data_endpoint(user=Depends(get_non_demo_user)):
    return {"ok": True}


@_real_data.get("/api/_test/real-care-team")
def _real_care_team(user=Depends(require_roles(Role.CARETAKER, Role.FAMILY_MEMBER, allow_demo=False))):
    return {"ok": True}


app.include_router(_real_data)


@pytest.fixture
def demo_client(client, auth_settings):
    auth_settings.demo_accounts_enabled = True
    return client


def users_repo():
    return UserRepository(mongodb.db)


def seed(settings):
    return provision_demo_accounts(users_repo(), settings)


def login(client, role):
    email, password = CREDENTIALS[role]
    return client.post("/api/auth/login", json={"email": email, "password": password})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


# ---- Configuration ----


def test_demo_disabled_by_default():
    s = Settings(_env_file=None)
    assert s.demo_accounts_enabled is False and s.demo_accounts_active is False


def test_production_requires_explicit_opt_in():
    prod = Settings(_env_file=None, environment="production", demo_accounts_enabled=True)
    assert prod.demo_accounts_active is False
    prod_ok = Settings(
        _env_file=None, environment="production", demo_accounts_enabled=True, demo_accounts_allow_production=True
    )
    assert prod_ok.demo_accounts_active is True


def test_definitions_match_requested_credentials():
    assert {a.role.value: (a.email, a.password) for a in DEMO_ACCOUNTS} == CREDENTIALS


# ---- Provisioning ----


def test_provisioning_refused_when_disabled(client, auth_settings):
    with pytest.raises(DemoProvisioningDisabledError):
        seed(auth_settings)
    assert mongodb.db[USERS_COLLECTION].count_documents({}) == 0


def test_startup_does_not_create_accounts(demo_client):
    # The client fixture has started the app (lifespan ran) with demo mode enabled.
    assert mongodb.db[USERS_COLLECTION].count_documents({}) == 0


def test_provisioning_creates_flagged_hashed_accounts(demo_client, auth_settings):
    results = seed(auth_settings)
    assert set(results.values()) == {ProvisionStatus.CREATED}
    docs = list(mongodb.db[USERS_COLLECTION].find())
    assert len(docs) == 3
    for d in docs:
        assert d["is_demo"] is True
        assert d["password_hash"].startswith("$argon2id$")
        assert all(pw not in str(d) for _, pw in CREDENTIALS.values())
    assert {d["role"] for d in docs} == set(CREDENTIALS)


def test_provisioning_is_idempotent_and_never_overwrites(demo_client, auth_settings):
    seed(auth_settings)
    before = {d["email"]: d["password_hash"] for d in mongodb.db[USERS_COLLECTION].find()}
    results = seed(auth_settings)
    assert set(results.values()) == {ProvisionStatus.EXISTS}
    after = {d["email"]: d["password_hash"] for d in mongodb.db[USERS_COLLECTION].find()}
    assert before == after and len(after) == 3


def test_existing_non_demo_account_is_left_untouched(demo_client, auth_settings):
    from app.core.security import hash_password

    original = hash_password("SomeoneElse123")
    users_repo().create(
        name="Real Person", email="elderly.demo@eldercare.com", password_hash=original, role=Role.CARETAKER
    )
    results = seed(auth_settings)
    assert results["elderly.demo@eldercare.com"] == ProvisionStatus.CONFLICT
    doc = mongodb.db[USERS_COLLECTION].find_one({"email": "elderly.demo@eldercare.com"})
    assert doc["password_hash"] == original and doc["is_demo"] is False and doc["role"] == "caretaker"


def test_demo_emails_cannot_be_registered_publicly(client):
    res = client.post(
        "/api/auth/register",
        json={
            "name": "Squatter",
            "email": "Caretaker.Demo@eldercare.com",
            "password": "MyOwnPassword123",
            "role": "caretaker",
        },
    )
    assert res.status_code == 409


# ---- Logins and permissions ----


@pytest.mark.parametrize("role", list(CREDENTIALS))
def test_demo_login_and_role_permissions(demo_client, auth_settings, role):
    seed(auth_settings)
    res = login(demo_client, role)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["user"]["role"] == role
    assert body["user"]["is_demo"] is True
    assert "password_hash" not in res.text

    token = body["access_token"]
    for area in ["elderly", "caretaker", "family", "care-team"]:
        r = demo_client.get(f"/api/portal/{area}", headers=bearer(token))
        assert r.status_code == (200 if area in ALLOWED[role] else 403), f"{role} -> {area}"
        if r.status_code == 200:
            assert r.json()["demo"] is True


@pytest.mark.parametrize("role", list(CREDENTIALS))
def test_demo_accounts_blocked_from_real_data(demo_client, auth_settings, role):
    seed(auth_settings)
    token = login(demo_client, role).json()["access_token"]
    res = demo_client.get("/api/_test/real-data", headers=bearer(token))
    assert res.status_code == 403
    assert res.json()["detail"] == "Demo accounts cannot access real user data."
    if role != "elderly":
        assert demo_client.get("/api/_test/real-care-team", headers=bearer(token)).status_code == 403


def test_real_users_can_access_real_data(demo_client):
    res = demo_client.post(
        "/api/auth/register",
        json={
            "name": "Real Carer",
            "email": "carer@example.org",
            "password": "RealPassword123",
            "role": "caretaker",
        },
    )
    token = res.json()["access_token"]
    assert res.json()["user"]["is_demo"] is False
    assert demo_client.get("/api/_test/real-data", headers=bearer(token)).status_code == 200
    assert demo_client.get("/api/_test/real-care-team", headers=bearer(token)).status_code == 200


def test_disabling_demo_mode_blocks_demo_login_and_tokens(demo_client, auth_settings):
    seed(auth_settings)
    token = login(demo_client, "caretaker").json()["access_token"]
    auth_settings.demo_accounts_enabled = False
    assert login(demo_client, "caretaker").json() == {"detail": "Invalid email or password."}
    assert demo_client.get("/api/auth/me", headers=bearer(token)).status_code == 401


def test_wrong_password_for_demo_account_rejected(demo_client, auth_settings):
    seed(auth_settings)
    res = demo_client.post("/api/auth/login", json={"email": CREDENTIALS["elderly"][0], "password": "WrongDemo2026!"})
    assert res.status_code == 401


# ---- Public demo-accounts listing ----


def test_listing_hidden_when_disabled(client):
    assert client.get("/api/auth/demo-accounts").status_code == 404


def test_listing_shows_only_provisioned_accounts(demo_client, auth_settings):
    assert demo_client.get("/api/auth/demo-accounts").json() == []
    seed(auth_settings)
    res = demo_client.get("/api/auth/demo-accounts")
    assert res.status_code == 200
    listed = {a["role"]: (a["email"], a["password"]) for a in res.json()}
    assert listed == CREDENTIALS
    assert "hash" not in res.text and "_id" not in res.text
