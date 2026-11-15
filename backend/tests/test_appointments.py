"""Appointment API tests (local throwaway MongoDB, frozen clock)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.db.indexes import APPOINTMENTS_COLLECTION
from app.db.mongodb import mongodb
from app.demo.provisioning import provision_demo_accounts
from app.demo.sample_data import provision_demo_sample_data
from app.repositories.users import UserRepository
from tests.helpers import create_profile, invite, new_user, redeem

UTC = UTC
T0 = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)

APPT = {
    "doctor_name": "Dr. Priya Shah",
    "specialization": "Cardiology",
    "clinic_name": "City Heart Clinic",
    "clinic_address": "5 High Street",
    "appointment_date": "2026-11-20",
    "appointment_time": "10:30",
    "appointment_type": "Check-up",
    "reason": "Blood pressure",
    "notes": "Bring medication list.",
}


class Clock:
    now = T0

    def __call__(self):
        return self.now


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    for mod in ("appointments", "medications", "profiles"):
        monkeypatch.setattr(f"app.api.routes.{mod}.utc_now", c)
    return c


@pytest.fixture
def owner(client, clock):
    user = new_user(client, "elderly")
    user["profile"] = create_profile(client, user)
    return user


def add(client, owner, **overrides):
    res = client.post("/api/appointments", json={**APPT, **overrides}, headers=owner["headers"])
    assert res.status_code == 201, res.text
    return res.json()


def listing(client, user, view="upcoming", base="/api"):
    res = client.get(f"{base}/appointments?view={view}", headers=user["headers"])
    assert res.status_code == 200, res.text
    return res.json()


# ---- create / read / edit / cancel / complete ----


def test_create_and_retrieve(client, owner):
    a = add(client, owner)
    assert a["status"] == "scheduled" and a["timezone"] == "UTC" and a["is_demo"] is False
    assert a["scheduled_at"].startswith("2026-11-20T10:30:00")
    assert a["can_edit"] and a["can_cancel"] and not a["can_complete"] and not a["is_past"]
    assert client.get(f"/api/appointments/{a['id']}", headers=owner["headers"]).json() == a
    assert [x["id"] for x in listing(client, owner)] == [a["id"]]
    assert listing(client, owner, "history") == []


def test_optional_fields_and_ordering(client, owner):
    later = add(
        client,
        owner,
        appointment_date="2026-12-01",
        specialization="",
        clinic_address=" ",
        appointment_type=None,
        reason=None,
        notes=None,
    )
    sooner = add(client, owner, doctor_name="Dr. Other")
    assert later["specialization"] is None and later["clinic_address"] is None
    assert [x["id"] for x in listing(client, owner)] == [sooner["id"], later["id"]]


def test_edit(client, owner):
    a = add(client, owner)
    res = client.put(
        f"/api/appointments/{a['id']}",
        json={**APPT, "appointment_time": "15:00", "notes": ""},
        headers=owner["headers"],
    )
    assert res.status_code == 200
    body = res.json()
    assert body["appointment_time"] == "15:00" and body["notes"] is None
    assert body["scheduled_at"].startswith("2026-11-20T15:00:00")


def test_cancel_is_atomic_and_final(client, owner):
    a = add(client, owner)
    res = client.post(f"/api/appointments/{a['id']}/cancel", headers=owner["headers"])
    assert res.status_code == 200 and res.json()["status"] == "cancelled"
    assert not res.json()["can_cancel"] and res.json()["status_changed_at"]
    assert client.post(f"/api/appointments/{a['id']}/cancel", headers=owner["headers"]).status_code == 409
    assert client.put(f"/api/appointments/{a['id']}", json=APPT, headers=owner["headers"]).status_code == 409
    assert listing(client, owner) == [] and listing(client, owner, "history")[0]["id"] == a["id"]
    # A cancelled slot can be booked again.
    add(client, owner)


def test_never_auto_completed_and_manual_completion(client, owner, clock):
    a = add(client, owner)
    assert client.post(f"/api/appointments/{a['id']}/complete", headers=owner["headers"]).status_code == 422
    clock.now = T0 + timedelta(days=5)  # appointment time has passed
    past = client.get(f"/api/appointments/{a['id']}", headers=owner["headers"]).json()
    assert past["status"] == "scheduled" and past["is_past"] and past["can_complete"] and not past["can_edit"]
    assert listing(client, owner) == [] and listing(client, owner, "history")[0]["status"] == "scheduled"
    assert client.put(f"/api/appointments/{a['id']}", json=APPT, headers=owner["headers"]).status_code == 409
    res = client.post(f"/api/appointments/{a['id']}/complete", headers=owner["headers"])
    assert res.status_code == 200 and res.json()["status"] == "completed"
    assert client.post(f"/api/appointments/{a['id']}/complete", headers=owner["headers"]).status_code == 409
    stored = mongodb.db[APPOINTMENTS_COLLECTION].find_one()
    assert [(h["from"], h["to"]) for h in stored["history"]] == [("scheduled", "completed")]


def test_duplicate_prevented(client, owner):
    add(client, owner)
    res = client.post("/api/appointments", json={**APPT, "doctor_name": "dr.  priya SHAH"}, headers=owner["headers"])
    assert res.status_code == 409
    add(client, owner, appointment_time="11:30")  # different time is fine
    other = add(client, owner, appointment_date="2026-11-21")
    assert client.put(f"/api/appointments/{other['id']}", json=APPT, headers=owner["headers"]).status_code == 409


# ---- validation ----


@pytest.mark.parametrize(
    "patch",
    [
        {"doctor_name": ""},
        {"doctor_name": "12345"},
        {"clinic_name": " "},
        {"appointment_date": "2026-02-30"},
        {"appointment_date": "not-a-date"},
        {"appointment_date": "1999-12-31"},
        {"appointment_date": "2040-01-01"},
        {"appointment_time": "25:00"},
        {"appointment_time": "9:30am"},
        {"appointment_time": ""},
        {"reason": "x" * 501},
        {"user_id": "someone-else"},
        {"profile_id": "x"},
        {"status": "completed"},
    ],
)
def test_invalid_input_rejected(client, owner, patch):
    res = client.post("/api/appointments", json={**APPT, **patch}, headers=owner["headers"])
    assert res.status_code == 422
    assert mongodb.db[APPOINTMENTS_COLLECTION].count_documents({}) == 0


def test_past_time_rejected_with_field_error(client, owner):
    res = client.post(
        "/api/appointments",
        json={**APPT, "appointment_date": "2026-11-16", "appointment_time": "11:59"},
        headers=owner["headers"],
    )
    assert res.status_code == 422
    assert res.json()["detail"][0]["loc"] == ["body", "appointment_date"]


# ---- time zones ----


def test_timezone_conversion(client, clock):
    user = new_user(client, "elderly")
    create_profile(client, user, timezone="America/New_York")
    winter = add(client, user, appointment_date="2026-12-01", appointment_time="09:00")
    summer = add(client, user, appointment_date="2027-07-01", appointment_time="09:00")
    assert winter["scheduled_at"].startswith("2026-12-01T14:00:00")  # EST, UTC-5
    assert summer["scheduled_at"].startswith("2027-07-01T13:00:00")  # EDT, UTC-4
    assert winter["timezone"] == "America/New_York" and winter["appointment_time"] == "09:00"


def test_nonexistent_dst_time_rejected(client, clock):
    user = new_user(client, "elderly")
    create_profile(client, user, timezone="America/New_York")
    res = client.post(
        "/api/appointments",
        json={**APPT, "appointment_date": "2027-03-14", "appointment_time": "02:30"},
        headers=user["headers"],
    )
    assert res.status_code == 422 and res.json()["detail"][0]["loc"] == ["body", "appointment_time"]


def test_kolkata_local_date_before_utc_date(client, clock):
    user = new_user(client, "elderly")
    create_profile(client, user, timezone="Asia/Kolkata")
    a = add(client, user, appointment_date="2026-11-20", appointment_time="03:00")
    assert a["scheduled_at"].startswith("2026-11-19T21:30:00") and a["appointment_date"] == "2026-11-20"


# ---- ownership and authorization ----


def test_unauthorized_and_wrong_role(client, owner):
    a = add(client, owner)
    assert client.get("/api/appointments").status_code == 401
    assert client.post("/api/appointments", json=APPT).status_code == 401
    assert client.get("/api/appointments", headers={"Authorization": "Bearer junk"}).status_code == 401
    caretaker = new_user(client, "caretaker")
    assert client.post("/api/appointments", json=APPT, headers=caretaker["headers"]).status_code == 403
    assert client.post(f"/api/appointments/{a['id']}/cancel", headers=caretaker["headers"]).status_code == 403
    no_profile = new_user(client, "elderly")
    assert client.post("/api/appointments", json=APPT, headers=no_profile["headers"]).status_code == 409


def test_ownership_isolation(client, owner):
    a = add(client, owner)
    other = new_user(client, "elderly")
    create_profile(client, other)
    h = other["headers"]
    assert listing(client, other) == []
    assert client.get(f"/api/appointments/{a['id']}", headers=h).status_code == 404
    assert client.put(f"/api/appointments/{a['id']}", json=APPT, headers=h).status_code == 404
    assert client.post(f"/api/appointments/{a['id']}/cancel", headers=h).status_code == 404
    assert client.post(f"/api/appointments/{a['id']}/complete", headers=h).status_code == 404
    assert client.get("/api/appointments/not-an-id", headers=h).status_code == 404
    assert client.get(f"/api/appointments/{a['id']}", headers=owner["headers"]).json()["status"] == "scheduled"


def test_member_read_only_and_revocation(client, owner):
    a = add(client, owner)
    member = new_user(client, "family_member")
    assert redeem(client, member, invite(client, owner, "family_member")["code"]).status_code == 201
    base = f"/api/linked-profiles/{owner['profile']['id']}"
    seen = listing(client, member, base=base)
    assert [x["id"] for x in seen] == [a["id"]]
    assert not (seen[0]["can_edit"] or seen[0]["can_cancel"] or seen[0]["can_complete"])
    assert client.get(f"{base}/appointments/{a['id']}", headers=member["headers"]).status_code == 200
    assert client.post(f"{base}/appointments", json=APPT, headers=member["headers"]).status_code == 405
    assert client.post(f"/api/appointments/{a['id']}/cancel", headers=member["headers"]).status_code == 403

    rel = client.get("/api/relationships", headers=owner["headers"]).json()[0]["id"]
    assert client.delete(f"/api/relationships/{rel}", headers=owner["headers"]).status_code == 204
    assert client.get(f"{base}/appointments", headers=member["headers"]).status_code == 404
    assert client.get(f"{base}/appointments/{a['id']}", headers=member["headers"]).status_code == 404


def test_unlinked_member_404(client, owner):
    add(client, owner)
    stranger = new_user(client, "caretaker")
    base = f"/api/linked-profiles/{owner['profile']['id']}"
    assert client.get(f"{base}/appointments", headers=stranger["headers"]).status_code == 404


# ---- demo ----


def demo_headers(client, email, password):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_demo_sample_appointments_isolated_and_idempotent(client, auth_settings, owner, clock):
    auth_settings.demo_accounts_enabled = True
    provision_demo_accounts(UserRepository(mongodb.db), auth_settings)
    first = provision_demo_sample_data(mongodb.db, horizon_days=7, early_minutes=120, now=clock.now)
    assert first["sample appointments"] == "created"
    count = mongodb.db[APPOINTMENTS_COLLECTION].count_documents({})
    again = provision_demo_sample_data(mongodb.db, horizon_days=7, early_minutes=120, now=clock.now)
    assert again["sample appointments"] == "already_exist"
    assert mongodb.db[APPOINTMENTS_COLLECTION].count_documents({}) == count == 3

    real = add(client, owner)
    demo_h = {"headers": demo_headers(client, "elderly.demo@eldercare.com", "ElderDemo2026!")}
    upcoming, history = listing(client, demo_h), listing(client, demo_h, "history")
    assert len(upcoming) == 2 and len(history) == 1 and history[0]["status"] == "completed"
    assert all(x["is_demo"] and "(sample)" in x["doctor_name"] for x in upcoming + history)
    assert client.get(f"/api/appointments/{real['id']}", headers=demo_h["headers"]).status_code == 404

    care_h = demo_headers(client, "caretaker.demo@eldercare.com", "CareDemo2026!")
    real_base = f"/api/linked-profiles/{owner['profile']['id']}"
    assert client.get(f"{real_base}/appointments", headers=care_h).status_code == 404
    demo_pid = client.get("/api/linked-profiles", headers=care_h).json()[0]["profile_id"]
    assert len(client.get(f"/api/linked-profiles/{demo_pid}/appointments", headers=care_h).json()) == 2
