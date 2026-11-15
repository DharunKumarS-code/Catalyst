"""Elderly-controlled permission for a caretaker to record doses they administered.

Rules under test: off by default; only the elderly owner can grant or withdraw it; only for
caretaker links (family members stay read-only); checked against the ACTIVE relationship on
every request; the dose records who changed it; medications themselves stay owner-only."""

from datetime import UTC, datetime

import pytest

from app.db.indexes import DOSES_COLLECTION
from app.db.mongodb import mongodb
from tests.helpers import create_profile, invite, new_user, redeem

T0 = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
MED = {
    "name": "Metformin",
    "dosage": "500 mg",
    "frequency": "twice_daily",
    "times": ["08:00", "20:00"],
    "start_date": "2026-11-16",
}


@pytest.fixture
def circle(client, monkeypatch):
    for mod in ("medications", "profiles", "care", "relationships"):
        monkeypatch.setattr(f"app.api.routes.{mod}.utc_now", lambda: T0)
    owner = new_user(client, "elderly", name="Margaret Owner")
    owner["profile"] = create_profile(client, owner, timezone="UTC")
    assert client.post("/api/medications", json=MED, headers=owner["headers"]).status_code == 201
    carer = new_user(client, "caretaker", name="Carl Carer")
    family = new_user(client, "family_member", name="Fay Family")
    assert redeem(client, carer, invite(client, owner, "caretaker")["code"]).status_code == 201
    assert redeem(client, family, invite(client, owner, "family_member")["code"]).status_code == 201
    conns = {c["member"]["name"]: c for c in client.get("/api/relationships", headers=owner["headers"]).json()}
    return {
        "owner": owner,
        "carer": carer,
        "family": family,
        "pid": owner["profile"]["id"],
        "carer_rel": conns["Carl Carer"]["id"],
        "family_rel": conns["Fay Family"]["id"],
        "conns": conns,
    }


def _today(client, who, pid):
    res = client.get(f"/api/linked-profiles/{pid}/doses/today", headers=who["headers"])
    assert res.status_code == 200, res.text
    return res.json()["doses"]


def _record(client, who, pid, dose, status="taken"):
    return client.patch(
        f"/api/linked-profiles/{pid}/doses/{dose['id']}/status",
        json={"status": status, "expected_status": dose["status"]},
        headers=who["headers"],
    )


def _grant(client, c, rel, allowed=True, who=None):
    return client.put(
        f"/api/relationships/{rel}/permissions",
        json={"can_record_doses": allowed},
        headers=(who or c["owner"])["headers"],
    )


def test_permission_is_off_by_default(client, circle):
    assert circle["conns"]["Carl Carer"]["can_record_doses"] is False
    due = _today(client, circle["carer"], circle["pid"])[0]
    assert due["local_time"] == "08:00" and due["can_mark_taken"] is False
    res = _record(client, circle["carer"], circle["pid"], due)
    assert res.status_code == 403
    assert "permission" in res.json()["detail"]


def test_granted_caretaker_records_a_dose_and_is_attributed(client, circle):
    res = _grant(client, circle, circle["carer_rel"])
    assert res.status_code == 200 and res.json()["can_record_doses"] is True

    due = _today(client, circle["carer"], circle["pid"])[0]
    assert due["can_mark_taken"] is True
    res = _record(client, circle["carer"], circle["pid"], due)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "taken"
    assert res.json()["recorded_by_name"] == "Carl Carer" and res.json()["recorded_by_role"] == "caretaker"

    # The owner sees who recorded it; the audit history keeps the caretaker as the actor.
    mine = client.get("/api/doses/today", headers=circle["owner"]["headers"]).json()["doses"][0]
    assert mine["status"] == "taken" and mine["recorded_by_name"] == "Carl Carer"
    stored = mongodb.db[DOSES_COLLECTION].find_one({"local_time": "08:00"})
    assert stored["history"][-1]["by_role"] == "caretaker"
    assert str(stored["history"][-1]["by"]) == circle["carer"]["user"]["id"]

    # Compare-and-set still applies: a stale repeat changes nothing.
    assert _record(client, circle["carer"], circle["pid"], due).status_code == 409


def test_family_members_stay_read_only(client, circle):
    res = _grant(client, circle, circle["family_rel"])
    assert res.status_code == 422
    assert "Family members can view only" in res.json()["detail"]
    due = _today(client, circle["family"], circle["pid"])[0]
    assert due["can_mark_taken"] is False
    assert _record(client, circle["family"], circle["pid"], due).status_code == 403


def test_only_the_owner_controls_the_permission(client, circle):
    # The caretaker cannot grant it to themselves (role check), nor can another elderly user (ownership check).
    assert _grant(client, circle, circle["carer_rel"], who=circle["carer"]).status_code == 403
    stranger = new_user(client, "elderly")
    assert _grant(client, circle, circle["carer_rel"], who=stranger).status_code == 404
    assert _grant(client, circle, "not-an-id").status_code == 404


def test_withdrawing_the_permission_or_the_link_takes_effect_immediately(client, circle):
    _grant(client, circle, circle["carer_rel"])
    due = _today(client, circle["carer"], circle["pid"])[0]
    assert _grant(client, circle, circle["carer_rel"], allowed=False).json()["can_record_doses"] is False
    assert _record(client, circle["carer"], circle["pid"], due).status_code == 403

    _grant(client, circle, circle["carer_rel"])
    assert (
        client.delete(f"/api/relationships/{circle['carer_rel']}", headers=circle["owner"]["headers"]).status_code
        == 204
    )
    assert _record(client, circle["carer"], circle["pid"], due).status_code == 404
    # A revoked link cannot be re-enabled.
    assert _grant(client, circle, circle["carer_rel"]).status_code == 404


def test_granted_caretaker_still_cannot_change_medications(client, circle):
    _grant(client, circle, circle["carer_rel"])
    med = client.get(f"/api/linked-profiles/{circle['pid']}/medications", headers=circle["carer"]["headers"]).json()[0]
    h = circle["carer"]["headers"]
    assert client.put(f"/api/medications/{med['id']}", json=MED, headers=h).status_code == 403
    assert client.delete(f"/api/medications/{med['id']}", headers=h).status_code == 403
    assert client.post("/api/medications", json=MED, headers=h).status_code == 403
    # The owner-only dose route is still refused for members.
    due = _today(client, circle["carer"], circle["pid"])[0]
    assert (
        client.patch(
            f"/api/doses/{due['id']}/status", json={"status": "taken", "expected_status": "pending"}, headers=h
        ).status_code
        == 403
    )


def test_care_dashboard_reflects_the_permission(client, circle):
    def card(who):
        return client.get("/api/care-dashboard", headers=who["headers"]).json()["profiles"][0]

    assert card(circle["carer"])["can_record_doses"] is False
    _grant(client, circle, circle["carer_rel"])
    granted = card(circle["carer"])
    assert granted["can_record_doses"] is True
    assert granted["today_doses"][0]["can_mark_taken"] is True
    assert card(circle["family"])["can_record_doses"] is False
