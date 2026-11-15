"""Elderly profile: create/read/update, validation, ownership and role restrictions."""

import pytest

from app.db.indexes import PROFILES_COLLECTION
from app.db.mongodb import mongodb
from tests.helpers import PROFILE, create_profile, new_user


def test_create_and_get_profile(client):
    elderly = new_user(client, "elderly")
    assert client.get("/api/profiles/me", headers=elderly["headers"]).status_code == 404

    created = create_profile(client, elderly)
    assert created["full_name"] == "Margaret Smith"
    assert created["date_of_birth"] == "1941-03-12"
    assert "user_id" not in created and "is_demo" not in created

    fetched = client.get("/api/profiles/me", headers=elderly["headers"]).json()
    assert fetched == created
    stored = mongodb.db[PROFILES_COLLECTION].find_one()
    assert str(stored["user_id"]) == elderly["user"]["id"]
    assert stored["created_at"].tzinfo is not None  # UTC-aware timestamps


def test_create_twice_conflicts(client):
    elderly = new_user(client, "elderly")
    create_profile(client, elderly)
    res = client.post("/api/profiles/me", json=PROFILE, headers=elderly["headers"])
    assert res.status_code == 409
    assert mongodb.db[PROFILES_COLLECTION].count_documents({}) == 1


def test_update_profile(client):
    elderly = new_user(client, "elderly")
    create_profile(client, elderly)
    res = client.put(
        "/api/profiles/me",
        json={**PROFILE, "phone": "", "address": "  ", "notes": None, "full_name": "Margaret  A.  Smith"},
        headers=elderly["headers"],
    )
    assert res.status_code == 200
    body = res.json()
    assert body["phone"] is None and body["address"] is None and body["notes"] is None
    assert body["full_name"] == "Margaret A. Smith"
    assert body["updated_at"] >= body["created_at"]


def test_update_without_profile_is_404(client):
    elderly = new_user(client, "elderly")
    assert client.put("/api/profiles/me", json=PROFILE, headers=elderly["headers"]).status_code == 404


def test_optional_fields_can_be_omitted(client):
    elderly = new_user(client, "elderly")
    minimal = {k: PROFILE[k] for k in ("full_name", "emergency_contact_name", "emergency_contact_phone")}
    res = client.post("/api/profiles/me", json=minimal, headers=elderly["headers"])
    assert res.status_code == 201
    assert res.json()["date_of_birth"] is None


@pytest.mark.parametrize(
    "override",
    [
        {"full_name": ""},
        {"full_name": "12345"},
        {"emergency_contact_name": ""},
        {"emergency_contact_phone": ""},
        {"emergency_contact_phone": "12"},
        {"phone": "call me maybe"},
        {"phone": "+1 234 567 890 123 456 789"},
        {"date_of_birth": "2999-01-01"},
        {"date_of_birth": "1850-01-01"},
        {"date_of_birth": "not-a-date"},
        {"address": "x" * 301},
        {"notes": "x" * 1001},
        {"user_id": "507f1f77bcf86cd799439011"},  # cannot set owner
        {"is_demo": False},
    ],
)
def test_profile_validation(client, override):
    elderly = new_user(client, "elderly")
    res = client.post("/api/profiles/me", json={**PROFILE, **override}, headers=elderly["headers"])
    assert res.status_code == 422, override


def test_profiles_are_isolated_per_owner(client):
    a = new_user(client, "elderly")
    b = new_user(client, "elderly")
    create_profile(client, a, full_name="Alice Owner")
    # B has no profile; /me never returns A's profile, and B's update cannot touch it.
    assert client.get("/api/profiles/me", headers=b["headers"]).status_code == 404
    assert (
        client.put("/api/profiles/me", json={**PROFILE, "full_name": "Hijacked"}, headers=b["headers"]).status_code
        == 404
    )
    assert client.get("/api/profiles/me", headers=a["headers"]).json()["full_name"] == "Alice Owner"


@pytest.mark.parametrize("role", ["caretaker", "family_member"])
def test_non_elderly_roles_cannot_use_profile_endpoints(client, role):
    member = new_user(client, role)
    assert client.get("/api/profiles/me", headers=member["headers"]).status_code == 403
    assert client.post("/api/profiles/me", json=PROFILE, headers=member["headers"]).status_code == 403
    assert client.put("/api/profiles/me", json=PROFILE, headers=member["headers"]).status_code == 403


def test_profile_endpoints_require_authentication(client):
    assert client.get("/api/profiles/me").status_code == 401
    assert client.post("/api/profiles/me", json=PROFILE).status_code == 401
    assert client.put("/api/profiles/me", json=PROFILE).status_code == 401
