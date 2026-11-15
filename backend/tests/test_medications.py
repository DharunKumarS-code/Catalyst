"""Medication, dose and adherence API tests (local throwaway MongoDB, frozen clock)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.db.indexes import DOSES_COLLECTION, MEDICATIONS_COLLECTION
from app.db.mongodb import mongodb
from app.demo.provisioning import provision_demo_accounts
from app.demo.sample_data import provision_demo_sample_data
from app.repositories.users import UserRepository
from tests.helpers import create_profile, invite, new_user, redeem

UTC = UTC
T0 = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)  # a Monday, noon UTC
TODAY = "2026-11-16"

MED = {
    "name": "Metformin",
    "dosage": "500 mg",
    "frequency": "twice_daily",
    "times": ["20:00", "08:00"],
    "start_date": TODAY,
    "instructions": "Take with food.",
    "prescribing_doctor": "Dr. Patel",
}


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr("app.api.routes.medications.utc_now", c)
    monkeypatch.setattr("app.api.routes.profiles.utc_now", c)
    return c


@pytest.fixture
def owner(client, clock):
    user = new_user(client, "elderly")
    user["profile"] = create_profile(client, user)
    return user


def add_med(client, owner, **overrides):
    res = client.post("/api/medications", json={**MED, **overrides}, headers=owner["headers"])
    assert res.status_code == 201, res.text
    return res.json()


def today(client, owner):
    res = client.get("/api/doses/today", headers=owner["headers"])
    assert res.status_code == 200, res.text
    return res.json()


def set_status(client, owner, dose, status, expected=None):
    return client.patch(
        f"/api/doses/{dose['id']}/status",
        json={"status": status, "expected_status": expected or dose["status"]},
        headers=owner["headers"],
    )


def link(client, owner, role="caretaker"):
    member = new_user(client, role)
    assert redeem(client, member, invite(client, owner, role)["code"]).status_code == 201
    return member


def doses_count(**query):
    return mongodb.db[DOSES_COLLECTION].count_documents(query)


# ---- CRUD and validation ----


def test_create_list_get_update(client, owner):
    med = add_med(client, owner)
    assert med["times"] == ["08:00", "20:00"] and med["status"] == "active" and med["is_demo"] is False
    assert [m["id"] for m in client.get("/api/medications", headers=owner["headers"]).json()] == [med["id"]]
    assert client.get(f"/api/medications/{med['id']}", headers=owner["headers"]).json() == med
    res = client.put(f"/api/medications/{med['id']}", json={**MED, "dosage": "850 mg"}, headers=owner["headers"])
    assert res.status_code == 200 and res.json()["dosage"] == "850 mg"


@pytest.mark.parametrize(
    "patch",
    [
        {"name": "   "},
        {"name": "1234"},
        {"dosage": ""},
        {"frequency": "hourly"},
        {"times": ["08:00"]},  # count must match twice_daily
        {"times": ["08:00", "08:00"]},
        {"times": ["8am", "20:00"]},
        {"times": ["24:00", "20:00"]},
        {"end_date": "2026-11-01"},  # before start
        {"start_date": "1999-01-01"},
        {"start_date": "2030-01-01"},
        {"instructions": "x" * 501},
        {"user_id": "someone-else"},  # owner can never be set from the body
    ],
)
def test_invalid_medication_rejected(client, owner, patch):
    res = client.post("/api/medications", json={**MED, **patch}, headers=owner["headers"])
    assert res.status_code == 422
    assert mongodb.db[MEDICATIONS_COLLECTION].count_documents({}) == 0


def test_profile_required_and_roles(client, clock):
    no_profile = new_user(client, "elderly")
    assert client.get("/api/medications", headers=no_profile["headers"]).status_code == 409
    caretaker = new_user(client, "caretaker")
    assert client.post("/api/medications", json=MED, headers=caretaker["headers"]).status_code == 403
    assert client.get("/api/medications").status_code == 401


def test_ownership_isolation(client, owner):
    med = add_med(client, owner)
    other = new_user(client, "elderly")
    create_profile(client, other)
    h = other["headers"]
    assert client.get("/api/medications", headers=h).json() == []
    assert client.get(f"/api/medications/{med['id']}", headers=h).status_code == 404
    assert client.put(f"/api/medications/{med['id']}", json=MED, headers=h).status_code == 404
    assert client.post(f"/api/medications/{med['id']}/discontinue", headers=h).status_code == 404
    assert client.delete(f"/api/medications/{med['id']}", headers=h).status_code == 404
    dose = today(client, owner)["doses"][0]
    assert set_status(client, other, dose, "taken").status_code == 404
    assert client.get("/api/medications/not-an-id", headers=h).status_code == 404


# ---- schedule generation ----


def test_doses_generated_without_duplicates(client, owner):
    med = add_med(client, owner)
    sched = today(client, owner)
    assert sched["date"] == TODAY and sched["timezone"] == "UTC"
    assert [(d["local_time"], d["status"]) for d in sched["doses"]] == [("08:00", "pending"), ("20:00", "pending")]
    first = doses_count(medication_id=mongodb.db[MEDICATIONS_COLLECTION].find_one()["_id"])
    assert first == 2 * 8  # today + 7-day horizon
    for _ in range(3):  # repeated reads do not duplicate
        today(client, owner)
        client.get("/api/adherence", headers=owner["headers"])
    assert doses_count() == first
    assert med["id"] in {d["medication_id"] for d in sched["doses"]}


def test_schedule_uses_profile_timezone(client, clock):
    user = new_user(client, "elderly")
    create_profile(client, user, timezone="Asia/Kolkata")
    add_med(client, user, frequency="once_daily", times=["08:00"])
    dose = today(client, user)["doses"][0]
    assert dose["local_time"] == "08:00"
    assert dose["scheduled_at"].startswith("2026-11-16T02:30:00")  # stored in UTC


def test_invalid_timezone_rejected(client, clock):
    user = new_user(client, "elderly")
    res = client.post(
        "/api/profiles/me",
        json={
            "full_name": "A B",
            "emergency_contact_name": "C D",
            "emergency_contact_phone": "07700 900123",
            "timezone": "Nowhere/City",
        },
        headers=user["headers"],
    )
    assert res.status_code == 422


def test_timezone_change_reschedules_future_doses(client, owner, clock):
    add_med(client, owner, frequency="once_daily", times=["20:00"])
    today(client, owner)
    profile = {k: v for k, v in owner["profile"].items() if k not in ("id", "created_at", "updated_at")}
    res = client.put("/api/profiles/me", json={**profile, "timezone": "America/New_York"}, headers=owner["headers"])
    assert res.status_code == 200
    sched = today(client, owner)  # 12:00Z is 07:00 in New York: still 16 Nov
    assert [d["scheduled_at"][:19] for d in sched["doses"]] == ["2026-11-17T01:00:00"]  # 20:00 EST
    assert doses_count(scheduled_at=datetime(2026, 11, 16, 20, 0, tzinfo=UTC)) == 0  # old UTC dose removed


def test_future_start_and_end_dates(client, owner):
    add_med(client, owner, start_date="2026-11-18", end_date="2026-11-19", frequency="once_daily", times=["09:00"])
    assert today(client, owner)["doses"] == []
    dates = sorted(d["local_date"] for d in mongodb.db[DOSES_COLLECTION].find())
    assert dates == ["2026-11-18", "2026-11-19"]


def test_edit_rebuilds_future_pending_but_keeps_recorded(client, owner, clock):
    med = add_med(client, owner)
    morning = today(client, owner)["doses"][0]
    assert set_status(client, owner, morning, "taken").status_code == 200
    res = client.put(
        f"/api/medications/{med['id']}",
        json={**MED, "frequency": "once_daily", "times": ["21:00"]},
        headers=owner["headers"],
    )
    assert res.status_code == 200
    doses = today(client, owner)["doses"]
    assert [(d["local_time"], d["status"]) for d in doses] == [("08:00", "taken"), ("21:00", "pending")]


def test_discontinue_cancels_future_and_delete_removes(client, owner, clock):
    med = add_med(client, owner)
    today(client, owner)
    res = client.post(f"/api/medications/{med['id']}/discontinue", headers=owner["headers"])
    assert res.status_code == 200 and res.json()["status"] == "discontinued"
    assert client.post(f"/api/medications/{med['id']}/discontinue", headers=owner["headers"]).status_code == 409
    assert client.put(f"/api/medications/{med['id']}", json=MED, headers=owner["headers"]).status_code == 409
    # Past dose kept, future doses cancelled and hidden from today's schedule.
    assert [d["local_time"] for d in today(client, owner)["doses"]] == ["08:00"]
    assert doses_count(status="cancelled") == 15
    active = client.get("/api/medications?status=active", headers=owner["headers"]).json()
    assert active == []
    assert client.delete(f"/api/medications/{med['id']}", headers=owner["headers"]).status_code == 204
    assert doses_count() == 0 and mongodb.db[MEDICATIONS_COLLECTION].count_documents({}) == 0


# ---- dose status transitions ----


def test_status_transitions_and_audit_trail(client, owner, clock):
    add_med(client, owner)
    morning, evening = today(client, owner)["doses"]
    assert morning["can_mark_taken"] and morning["can_mark_missed"]
    assert not evening["can_mark_missed"]  # 20:00 has not happened yet

    res = set_status(client, owner, morning, "taken")
    assert res.status_code == 200
    taken = res.json()
    assert taken["status"] == "taken" and taken["taken_at"] and taken["status_changed_at"]

    # Repeated / stale submissions change nothing.
    assert set_status(client, owner, morning, "taken", expected="pending").status_code == 409
    assert set_status(client, owner, taken, "taken").status_code == 409

    # Corrections are allowed and recorded.
    assert set_status(client, owner, taken, "missed").json()["status"] == "missed"
    stored = mongodb.db[DOSES_COLLECTION].find_one({"local_time": "08:00", "local_date": TODAY})
    assert [(h["from"], h["to"]) for h in stored["history"]] == [("pending", "taken"), ("taken", "missed")]
    assert stored["taken_at"] is None


def test_timing_rules(client, owner, clock):
    add_med(client, owner, times=["08:00", "13:30"])
    _, soon = today(client, owner)["doses"]
    assert set_status(client, owner, soon, "missed").status_code == 422  # not due yet
    assert set_status(client, owner, soon, "taken").status_code == 200  # within the 2h early window
    today_adherence = client.get("/api/adherence", headers=owner["headers"]).json()["today"]
    assert (today_adherence["total"], today_adherence["taken"]) == (2, 1)  # early-taken dose counts once recorded
    history = client.get("/api/doses/history", headers=owner["headers"]).json()
    assert soon["id"] in [d["id"] for d in history]  # ...and appears in history straight away
    tomorrow = mongodb.db[DOSES_COLLECTION].find_one({"local_date": "2026-11-17"})
    res = client.patch(
        f"/api/doses/{tomorrow['_id']}/status",
        json={"status": "taken", "expected_status": "pending"},
        headers=owner["headers"],
    )
    assert res.status_code == 422


def test_cancelled_dose_is_immutable(client, owner):
    med = add_med(client, owner)
    today(client, owner)
    client.post(f"/api/medications/{med['id']}/discontinue", headers=owner["headers"])
    cancelled = mongodb.db[DOSES_COLLECTION].find_one({"status": "cancelled"})
    res = client.patch(
        f"/api/doses/{cancelled['_id']}/status",
        json={"status": "taken", "expected_status": "pending"},
        headers=owner["headers"],
    )
    assert res.status_code == 409


def test_never_auto_marked(client, owner, clock):
    add_med(client, owner)
    today(client, owner)
    clock.now = T0 + timedelta(days=2)
    today(client, owner)
    assert doses_count(status="taken") == 0 and doses_count(status="missed") == 0


def test_invalid_status_body(client, owner):
    add_med(client, owner)
    dose = today(client, owner)["doses"][0]
    for body in (
        {"status": "cancelled", "expected_status": "pending"},
        {"status": "taken"},
        {"status": "taken", "expected_status": "pending", "taken_at": "2020-01-01"},
    ):
        assert client.patch(f"/api/doses/{dose['id']}/status", json=body, headers=owner["headers"]).status_code == 422


# ---- history and adherence ----


def test_history_and_adherence(client, owner, clock):
    add_med(client, owner)
    empty = client.get("/api/adherence", headers=owner["headers"]).json()
    morning = today(client, owner)["doses"][0]
    assert empty["today"]["total"] == 1 and empty["today"]["adherence_percent"] == 0.0
    set_status(client, owner, morning, "taken")

    clock.now = T0 + timedelta(days=1)  # next day noon: yesterday 20:00 unrecorded, today 08:00 due
    tomorrow_morning = today(client, owner)["doses"][0]
    set_status(client, owner, tomorrow_morning, "missed")
    summary = client.get("/api/adherence", headers=owner["headers"]).json()
    assert summary["week"]["total"] == 3  # future doses excluded
    assert (summary["week"]["taken"], summary["week"]["missed"], summary["week"]["pending"]) == (1, 1, 1)
    assert summary["week"]["adherence_percent"] == 33.3
    assert summary["today"]["adherence_percent"] == 0.0
    assert len(summary["days"]) == 7 and summary["days"][0]["adherence_percent"] is None  # nothing due

    history = client.get("/api/doses/history?days=7", headers=owner["headers"]).json()
    assert [d["status"] for d in history] == ["missed", "pending", "taken"]  # newest first, no future doses
    assert client.get("/api/doses/history?days=0", headers=owner["headers"]).status_code == 422


def test_adherence_excludes_cancelled_and_handles_no_doses(client, owner):
    summary = client.get("/api/adherence", headers=owner["headers"]).json()
    assert summary["week"]["total"] == 0 and summary["week"]["adherence_percent"] is None
    med = add_med(client, owner, frequency="once_daily", times=["18:00"])
    client.post(f"/api/medications/{med['id']}/discontinue", headers=owner["headers"])
    assert client.get("/api/adherence", headers=owner["headers"]).json()["week"]["total"] == 0


# ---- caretaker / family read-only access ----


def test_member_read_only_access_and_revocation(client, owner):
    med = add_med(client, owner)
    member = link(client, owner, "family_member")
    base = f"/api/linked-profiles/{owner['profile']['id']}"
    h = member["headers"]
    assert [m["id"] for m in client.get(f"{base}/medications", headers=h).json()] == [med["id"]]
    assert client.get(f"{base}/medications/{med['id']}", headers=h).status_code == 200
    doses = client.get(f"{base}/doses/today", headers=h).json()["doses"]
    assert doses and not any(d["can_mark_taken"] or d["can_mark_missed"] for d in doses)
    assert client.get(f"{base}/doses/history", headers=h).status_code == 200
    assert client.get(f"{base}/adherence", headers=h).status_code == 200

    # No write paths for members.
    assert set_status(client, member, doses[0], "taken").status_code == 403
    assert client.post("/api/medications", json=MED, headers=h).status_code == 403
    assert client.delete(f"/api/medications/{med['id']}", headers=h).status_code == 403
    assert client.post(f"{base}/medications", json=MED, headers=h).status_code == 405

    # Revocation is immediate.
    rel_id = client.get("/api/relationships", headers=owner["headers"]).json()[0]["id"]
    assert client.delete(f"/api/relationships/{rel_id}", headers=owner["headers"]).status_code == 204
    for path in ("/medications", "/doses/today", "/doses/history", "/adherence"):
        assert client.get(base + path, headers=h).status_code == 404


def test_unlinked_member_gets_404(client, owner):
    add_med(client, owner)
    stranger = new_user(client, "caretaker")
    base = f"/api/linked-profiles/{owner['profile']['id']}"
    assert client.get(f"{base}/medications", headers=stranger["headers"]).status_code == 404
    assert client.get("/api/linked-profiles/bogus/medications", headers=stranger["headers"]).status_code == 404
    other_owner = new_user(client, "elderly")
    assert client.get(f"{base}/medications", headers=other_owner["headers"]).status_code == 403


# ---- demo isolation and sample data ----


def demo_login(client, email, password):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_demo_sample_data_isolated_and_idempotent(client, auth_settings, owner, clock):
    auth_settings.demo_accounts_enabled = True
    provision_demo_accounts(UserRepository(mongodb.db), auth_settings)
    first = provision_demo_sample_data(mongodb.db, horizon_days=7, early_minutes=120, now=clock.now)
    assert first["sample medications"] == "created" and first["demo link (caretaker)"] == "created"
    counts = (mongodb.db[MEDICATIONS_COLLECTION].count_documents({}), doses_count())
    again = provision_demo_sample_data(mongodb.db, horizon_days=7, early_minutes=120, now=clock.now)
    assert set(again.values()) == {"already_exists", "already_exist"}
    assert (mongodb.db[MEDICATIONS_COLLECTION].count_documents({}), doses_count()) == counts

    real_med = add_med(client, owner)
    demo_h = demo_login(client, "elderly.demo@eldercare.com", "ElderDemo2026!")
    demo_meds = client.get("/api/medications", headers=demo_h).json()
    assert len(demo_meds) == 3 and all(m["is_demo"] for m in demo_meds)
    assert real_med["id"] not in {m["id"] for m in demo_meds}
    assert client.get(f"/api/medications/{real_med['id']}", headers=demo_h).status_code == 404
    assert mongodb.db[DOSES_COLLECTION].count_documents({"is_demo": True}) == doses_count(is_demo=True) > 0
    yesterday = client.get("/api/adherence", headers=demo_h).json()["days"][-2]  # seeded history
    assert (yesterday["total"], yesterday["taken"], yesterday["missed"]) == (4, 3, 1)

    # Demo caretaker can read the demo profile only, never a real one.
    care_h = demo_login(client, "caretaker.demo@eldercare.com", "CareDemo2026!")
    linked = client.get("/api/linked-profiles", headers=care_h).json()
    assert len(linked) == 1
    assert client.get(f"/api/linked-profiles/{linked[0]['profile_id']}/medications", headers=care_h).status_code == 200
    real_base = f"/api/linked-profiles/{owner['profile']['id']}"
    assert client.get(f"{real_base}/medications", headers=care_h).status_code == 404


def test_overview_matches_the_three_separate_endpoints(client, owner, clock):
    """The combined endpoint returns exactly what the three separate requests return."""
    add_med(client, owner)
    add_med(client, owner, name="Aspirin", frequency="once_daily", times=["09:00"])
    dose = next(d for d in today(client, owner)["doses"] if d["is_due"])
    assert set_status(client, owner, dose, "taken").status_code == 200

    res = client.get("/api/medications/overview", headers=owner["headers"])
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["today"] == today(client, owner)
    assert body["adherence"] == client.get("/api/adherence", headers=owner["headers"]).json()
    assert body["medications"] == client.get("/api/medications", headers=owner["headers"]).json()


def test_overview_access_rules(client, owner, clock):
    add_med(client, owner)
    member = new_user(client, "caretaker")
    stranger = new_user(client, "family_member")
    assert redeem(client, member, invite(client, owner, "caretaker")["code"]).status_code == 201
    pid = owner["profile"]["id"]

    linked = client.get(f"/api/linked-profiles/{pid}/medications/overview", headers=member["headers"])
    assert linked.status_code == 200
    assert linked.json()["today"]["doses"][0]["can_mark_taken"] is False  # read-only without a grant
    assert (
        client.get(f"/api/linked-profiles/{pid}/medications/overview", headers=stranger["headers"]).status_code == 404
    )
    assert client.get("/api/medications/overview", headers=member["headers"]).status_code == 403
    assert client.get("/api/medications/overview").status_code == 401
