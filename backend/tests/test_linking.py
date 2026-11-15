"""Invitations, linking, relationship management, revocation and demo isolation."""

from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId

from app.db.indexes import INVITATIONS_COLLECTION, RELATIONSHIPS_COLLECTION
from app.db.mongodb import mongodb
from app.demo.provisioning import provision_demo_accounts
from app.repositories.users import UserRepository
from app.services.invitation_codes import ALPHABET, generate_code, hash_code, normalize_code
from tests.helpers import bearer, create_profile, invite, new_user, redeem

FAKE_CODE = "ABCD-EFGH-JKMN-PQRS"


@pytest.fixture
def elderly(client):
    e = new_user(client, "elderly", name="Margaret Smith")
    e["profile"] = create_profile(client, e)
    return e


# ---- Code generation ----

def test_codes_are_random_well_formed_and_normalized():
    codes = {generate_code() for _ in range(200)}
    assert len(codes) == 200
    for c in list(codes)[:20]:
        assert len(c) == 19 and c.count("-") == 3
        assert all(ch in ALPHABET for ch in c.replace("-", ""))
        assert normalize_code(c.lower().replace("-", " ")) == c.replace("-", "")
    assert normalize_code("abcd efgh jkmn pqrO") == "ABCDEFGHJKMNPQR0"  # O -> 0
    assert normalize_code("too-short") is None
    assert normalize_code("ABCD-EFGH-JKMN-PQR!") is None


# ---- Invitation creation ----

def test_create_invitation_stores_only_hash(client, elderly):
    inv = invite(client, elderly, "caretaker")
    assert inv["status"] == "pending" and inv["role"] == "caretaker"
    assert len(inv["code"]) == 19
    stored = mongodb.db[INVITATIONS_COLLECTION].find_one({"_id": ObjectId(inv["id"])})
    assert stored["code_hash"] == hash_code(normalize_code(inv["code"]))
    assert inv["code"] not in str(stored) and inv["code"].replace("-", "") not in str(stored)
    assert stored["expires_at"] - stored["created_at"] == timedelta(hours=72)


def test_invitation_listing_never_exposes_code_or_hash(client, elderly):
    inv = invite(client, elderly, "family_member")
    res = client.get("/api/invitations", headers=elderly["headers"])
    assert res.status_code == 200
    assert [i["id"] for i in res.json()] == [inv["id"]]
    assert "code" not in res.json()[0] and "hash" not in res.text and inv["code"] not in res.text


def test_invitation_requires_profile(client):
    e = new_user(client, "elderly")
    res = client.post("/api/invitations", json={"role": "caretaker"}, headers=e["headers"])
    assert res.status_code == 409


@pytest.mark.parametrize("body", [{"role": "elderly"}, {"role": "admin"}, {"role": "caretaker", "expires_in_hours": 0},
                                  {"role": "caretaker", "expires_in_hours": 1000}, {"role": "caretaker", "code": "x"}])
def test_invitation_validation(client, elderly, body):
    assert client.post("/api/invitations", json=body, headers=elderly["headers"]).status_code == 422


def test_open_invitation_limit(client, elderly, auth_settings):
    auth_settings.invitation_max_pending = 2
    invite(client, elderly, "caretaker")
    invite(client, elderly, "caretaker")
    assert client.post("/api/invitations", json={"role": "caretaker"}, headers=elderly["headers"]).status_code == 429


@pytest.mark.parametrize("role", ["caretaker", "family_member"])
def test_only_elderly_can_create_or_list_invitations(client, role):
    member = new_user(client, role)
    assert client.post("/api/invitations", json={"role": "caretaker"}, headers=member["headers"]).status_code == 403
    assert client.get("/api/invitations", headers=member["headers"]).status_code == 403


def test_cancel_invitation(client, elderly):
    inv = invite(client, elderly, "caretaker")
    other = new_user(client, "elderly")
    create_profile(client, other)
    assert client.delete(f"/api/invitations/{inv['id']}", headers=other["headers"]).status_code == 404  # not owner
    assert client.delete(f"/api/invitations/{inv['id']}", headers=elderly["headers"]).status_code == 204
    assert client.delete(f"/api/invitations/{inv['id']}", headers=elderly["headers"]).status_code == 404
    caretaker = new_user(client, "caretaker")
    assert redeem(client, caretaker, inv["code"]).status_code == 400  # cancelled invitations cannot be redeemed


# ---- Redemption ----

@pytest.mark.parametrize("role", ["caretaker", "family_member"])
def test_successful_redemption_links_member(client, elderly, role):
    inv = invite(client, elderly, role)
    member = new_user(client, role)
    res = redeem(client, member, inv["code"].lower().replace("-", " "))  # forgiving input
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["message"] == "You are now connected to Margaret Smith."
    assert body["linked"]["profile_id"] == elderly["profile"]["id"]
    assert body["linked"]["role"] == role

    linked = client.get("/api/linked-profiles", headers=member["headers"]).json()
    assert [p["profile_id"] for p in linked] == [elderly["profile"]["id"]]
    detail = client.get(f"/api/linked-profiles/{elderly['profile']['id']}", headers=member["headers"])
    assert detail.status_code == 200
    assert detail.json()["profile"]["emergency_contact_name"] == "Tom Smith"

    connections = client.get("/api/relationships", headers=elderly["headers"]).json()
    assert len(connections) == 1
    assert connections[0]["member"]["id"] == member["user"]["id"]
    assert "password" not in str(connections)

    invitations = client.get("/api/invitations", headers=elderly["headers"]).json()
    assert invitations[0]["status"] == "redeemed"


def test_invalid_code(client, elderly):
    member = new_user(client, "caretaker")
    res = redeem(client, member, FAKE_CODE)
    assert res.status_code == 400
    assert res.json()["detail"].startswith("This invitation code is not valid")


def test_malformed_code_rejected_without_counting(client, elderly, auth_settings):
    auth_settings.redeem_max_failures = 1
    member = new_user(client, "caretaker")
    for _ in range(3):
        assert redeem(client, member, "nope").status_code == 400
    assert redeem(client, member, invite(client, elderly, "caretaker")["code"]).status_code == 201


def test_expired_invitation(client, elderly):
    inv = invite(client, elderly, "caretaker")
    mongodb.db[INVITATIONS_COLLECTION].update_one(
        {"_id": ObjectId(inv["id"])}, {"$set": {"expires_at": datetime.now(timezone.utc) - timedelta(minutes=1)}}
    )
    res = redeem(client, new_user(client, "caretaker"), inv["code"])
    assert res.status_code == 410
    assert "expired" in res.json()["detail"]
    assert client.get("/api/invitations", headers=elderly["headers"]).json()[0]["status"] == "expired"


def test_reused_invitation(client, elderly):
    inv = invite(client, elderly, "caretaker")
    assert redeem(client, new_user(client, "caretaker"), inv["code"]).status_code == 201
    res = redeem(client, new_user(client, "caretaker"), inv["code"])
    assert res.status_code == 409
    assert "already been used" in res.json()["detail"]
    assert mongodb.db[RELATIONSHIPS_COLLECTION].count_documents({}) == 1


def test_wrong_role_redemption(client, elderly):
    inv = invite(client, elderly, "family_member")
    res = redeem(client, new_user(client, "caretaker"), inv["code"])
    assert res.status_code == 403
    assert res.json()["detail"] == "This invitation is for a family member, but you are signed in as a caretaker."
    # Not consumed: the intended family member can still use it.
    assert redeem(client, new_user(client, "family_member"), inv["code"]).status_code == 201


def test_elderly_cannot_redeem(client, elderly):
    inv = invite(client, elderly, "caretaker")
    other = new_user(client, "elderly")
    assert redeem(client, other, inv["code"]).status_code == 403
    assert redeem(client, elderly, inv["code"]).status_code == 403  # no self-linking


def test_repeated_wrong_role_attempts_lock_the_invitation(client, elderly, auth_settings):
    auth_settings.redeem_max_failures = 3
    inv = invite(client, elderly, "family_member")
    for _ in range(3):
        assert redeem(client, new_user(client, "caretaker"), inv["code"]).status_code == 403
    res = redeem(client, new_user(client, "family_member"), inv["code"])
    assert res.status_code == 400
    assert "no longer valid" in res.json()["detail"]


def test_excessive_failed_attempts_are_rate_limited(client, elderly, auth_settings):
    auth_settings.redeem_max_failures = 5
    member = new_user(client, "caretaker")
    for _ in range(5):
        assert redeem(client, member, FAKE_CODE).status_code == 400
    valid = invite(client, elderly, "caretaker")["code"]
    blocked = redeem(client, member, valid)
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0
    assert "Too many unsuccessful attempts" in blocked.json()["detail"]
    # Other users are unaffected.
    assert redeem(client, new_user(client, "caretaker"), valid).status_code == 201


def test_rate_limit_window_expires(client, elderly, auth_settings):
    auth_settings.redeem_max_failures = 2
    member = new_user(client, "caretaker")
    redeem(client, member, FAKE_CODE)
    redeem(client, member, FAKE_CODE)
    assert redeem(client, member, FAKE_CODE).status_code == 429
    mongodb.db["redemption_failures"].update_many({}, {"$set": {"created_at": datetime.now(timezone.utc) - timedelta(hours=1)}})
    assert redeem(client, member, invite(client, elderly, "caretaker")["code"]).status_code == 201


def test_duplicate_relationship_prevented(client, elderly):
    member = new_user(client, "caretaker")
    assert redeem(client, member, invite(client, elderly, "caretaker")["code"]).status_code == 201
    second = invite(client, elderly, "caretaker")
    res = redeem(client, member, second["code"])
    assert res.status_code == 409
    assert res.json()["detail"] == "You are already connected to this person."
    # The second invitation was not consumed.
    statuses = {i["id"]: i["status"] for i in client.get("/api/invitations", headers=elderly["headers"]).json()}
    assert statuses[second["id"]] == "pending"
    assert mongodb.db[RELATIONSHIPS_COLLECTION].count_documents({"status": "active"}) == 1


def test_partial_unique_index_blocks_duplicate_active_relationship(client, elderly):
    member = new_user(client, "caretaker")
    redeem(client, member, invite(client, elderly, "caretaker")["code"])
    rel = mongodb.db[RELATIONSHIPS_COLLECTION].find_one()
    dup = {k: v for k, v in rel.items() if k != "_id"}
    with pytest.raises(Exception):
        mongodb.db[RELATIONSHIPS_COLLECTION].insert_one(dup)


# ---- Relationship management / revocation ----

def test_revocation_removes_access_immediately(client, elderly):
    member = new_user(client, "family_member")
    redeem(client, member, invite(client, elderly, "family_member")["code"])
    profile_url = f"/api/linked-profiles/{elderly['profile']['id']}"
    token_before = member["headers"]
    assert client.get(profile_url, headers=token_before).status_code == 200

    rel_id = client.get("/api/relationships", headers=elderly["headers"]).json()[0]["id"]
    assert client.delete(f"/api/relationships/{rel_id}", headers=elderly["headers"]).status_code == 204

    # Same token, no re-login: access is gone.
    assert client.get(profile_url, headers=token_before).status_code == 404
    assert client.get("/api/linked-profiles", headers=token_before).json() == []
    assert client.get("/api/relationships", headers=elderly["headers"]).json() == []
    assert client.delete(f"/api/relationships/{rel_id}", headers=elderly["headers"]).status_code == 404


def test_member_can_be_reinvited_after_revocation(client, elderly):
    member = new_user(client, "caretaker")
    redeem(client, member, invite(client, elderly, "caretaker")["code"])
    rel_id = client.get("/api/relationships", headers=elderly["headers"]).json()[0]["id"]
    client.delete(f"/api/relationships/{rel_id}", headers=elderly["headers"])
    assert redeem(client, member, invite(client, elderly, "caretaker")["code"]).status_code == 201


def test_only_owner_can_revoke(client, elderly):
    member = new_user(client, "caretaker")
    redeem(client, member, invite(client, elderly, "caretaker")["code"])
    rel_id = client.get("/api/relationships", headers=elderly["headers"]).json()[0]["id"]
    other = new_user(client, "elderly")
    assert client.delete(f"/api/relationships/{rel_id}", headers=other["headers"]).status_code == 404
    assert client.delete(f"/api/relationships/{rel_id}", headers=member["headers"]).status_code == 403
    assert client.delete("/api/relationships/not-an-id", headers=elderly["headers"]).status_code == 404
    assert len(client.get("/api/relationships", headers=elderly["headers"]).json()) == 1


def test_member_cannot_view_unlinked_profile(client, elderly):
    other_elderly = new_user(client, "elderly")
    other_profile = create_profile(client, other_elderly, full_name="Not Yours")
    member = new_user(client, "caretaker")
    redeem(client, member, invite(client, elderly, "caretaker")["code"])
    assert client.get(f"/api/linked-profiles/{other_profile['id']}", headers=member["headers"]).status_code == 404
    assert client.get("/api/linked-profiles/garbage", headers=member["headers"]).status_code == 404
    assert client.get(f"/api/linked-profiles/{ObjectId()}", headers=member["headers"]).status_code == 404
    names = [p["full_name"] for p in client.get("/api/linked-profiles", headers=member["headers"]).json()]
    assert names == ["Margaret Smith"]


def test_role_restrictions_on_linking_endpoints(client, elderly):
    caretaker = new_user(client, "caretaker")
    assert client.get("/api/relationships", headers=caretaker["headers"]).status_code == 403
    assert client.get("/api/linked-profiles", headers=elderly["headers"]).status_code == 403
    assert client.get(f"/api/linked-profiles/{elderly['profile']['id']}", headers=elderly["headers"]).status_code == 403


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/invitations"),
        ("post", "/api/invitations"),
        ("delete", f"/api/invitations/{ObjectId()}"),
        ("post", "/api/invitations/redeem"),
        ("get", "/api/relationships"),
        ("delete", f"/api/relationships/{ObjectId()}"),
        ("get", "/api/linked-profiles"),
        ("get", f"/api/linked-profiles/{ObjectId()}"),
    ],
)
def test_unauthenticated_access_rejected(client, method, path):
    kwargs = {"json": {"role": "caretaker", "code": FAKE_CODE}} if method == "post" else {}
    assert getattr(client, method)(path, **kwargs).status_code == 401
    assert getattr(client, method)(path, headers=bearer("garbage"), **kwargs).status_code == 401


# ---- Demo isolation ----

DEMO = {
    "elderly": ("elderly.demo@eldercare.com", "ElderDemo2026!"),
    "caretaker": ("caretaker.demo@eldercare.com", "CareDemo2026!"),
    "family_member": ("family.demo@eldercare.com", "FamilyDemo2026!"),
}


@pytest.fixture
def demo(client, auth_settings):
    auth_settings.demo_accounts_enabled = True
    provision_demo_accounts(UserRepository(mongodb.db), auth_settings)
    out = {}
    for role, (email, password) in DEMO.items():
        token = client.post("/api/auth/login", json={"email": email, "password": password}).json()["access_token"]
        out[role] = {"token": token, "headers": bearer(token)}
    return out


def test_demo_accounts_can_use_linking_within_demo_data(client, demo):
    create_profile(client, demo["elderly"], full_name="Demo Grandma")
    code = invite(client, demo["elderly"], "caretaker")["code"]
    assert redeem(client, demo["caretaker"], code).status_code == 201
    linked = client.get("/api/linked-profiles", headers=demo["caretaker"]["headers"]).json()
    assert [p["full_name"] for p in linked] == ["Demo Grandma"]
    stored = mongodb.db[RELATIONSHIPS_COLLECTION].find_one()
    assert stored["is_demo"] is True


def test_demo_member_cannot_redeem_real_invitation(client, elderly, demo):
    real_code = invite(client, elderly, "caretaker")["code"]
    res = redeem(client, demo["caretaker"], real_code)
    assert res.status_code == 400
    assert res.json()["detail"].startswith("This invitation code is not valid")  # indistinguishable from unknown
    assert client.get("/api/linked-profiles", headers=demo["caretaker"]["headers"]).json() == []
    # The real invitation is untouched and still works for a real caretaker.
    assert redeem(client, new_user(client, "caretaker"), real_code).status_code == 201


def test_real_member_cannot_redeem_demo_invitation(client, demo):
    create_profile(client, demo["elderly"], full_name="Demo Grandma")
    demo_code = invite(client, demo["elderly"], "family_member")["code"]
    res = redeem(client, new_user(client, "family_member"), demo_code)
    assert res.status_code == 400
    assert mongodb.db[RELATIONSHIPS_COLLECTION].count_documents({}) == 0


def test_demo_member_cannot_view_real_profile_even_with_forged_relationship(client, elderly, demo):
    """Defense in depth: even if a cross-partition relationship row existed, it is ignored."""
    demo_user = UserRepository(mongodb.db).get_by_email("caretaker.demo@eldercare.com")
    mongodb.db[RELATIONSHIPS_COLLECTION].insert_one({
        "profile_id": ObjectId(elderly["profile"]["id"]), "elderly_user_id": ObjectId(elderly["user"]["id"]),
        "member_user_id": demo_user["_id"], "role": "caretaker", "status": "active", "is_demo": False,
        "created_at": datetime.now(timezone.utc),
    })
    headers = demo["caretaker"]["headers"]
    assert client.get(f"/api/linked-profiles/{elderly['profile']['id']}", headers=headers).status_code == 404
    assert client.get("/api/linked-profiles", headers=headers).json() == []
