"""Care dashboard (caretaker / family monitoring) tests. Frozen clock, throwaway MongoDB."""

from datetime import datetime, timedelta, timezone

import pytest

from app.db.mongodb import mongodb
from app.demo.provisioning import provision_demo_accounts
from app.demo.sample_data import provision_demo_sample_data
from app.repositories.users import UserRepository
from tests.helpers import create_profile, invite, new_user, redeem

UTC = timezone.utc
T0 = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
MED = {"name": "Metformin", "dosage": "500 mg", "frequency": "twice_daily", "times": ["08:00", "20:00"],
       "start_date": "2026-11-16"}
APPT = {"doctor_name": "Dr. Shah", "clinic_name": "Heart Clinic", "appointment_date": "2026-11-20",
        "appointment_time": "10:30"}


class Clock:
    now = T0

    def __call__(self):
        return self.now


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    for mod in ("care", "appointments", "medications", "profiles"):
        monkeypatch.setattr(f"app.api.routes.{mod}.utc_now", c)
    return c


def elderly(client, name="Margaret Smith", **profile):
    user = new_user(client, "elderly")
    user["profile"] = create_profile(client, user, full_name=name, **profile)
    return user


def link(client, owner, member, role):
    assert redeem(client, member, invite(client, owner, role)["code"]).status_code == 201


def dashboard(client, member):
    res = client.get("/api/care-dashboard", headers=member["headers"])
    assert res.status_code == 200, res.text
    return res.json()


def by_name(data):
    return {p["full_name"]: p for p in data["profiles"]}


def test_access_rules(client, clock):
    assert client.get("/api/care-dashboard").status_code == 401
    owner = elderly(client)
    assert client.get("/api/care-dashboard", headers=owner["headers"]).status_code == 403
    assert dashboard(client, new_user(client, "caretaker"))["profiles"] == []  # empty state


def test_multiple_profiles_only_linked(client, clock):
    a = elderly(client, "Alice Adams")
    b = elderly(client, "Bob Brown", timezone="Asia/Kolkata")
    stranger = elderly(client, "Carol Stranger")
    client.post("/api/medications", json=MED, headers=stranger["headers"])
    carer = new_user(client, "caretaker")
    link(client, a, carer, "caretaker")
    link(client, b, carer, "caretaker")
    data = dashboard(client, carer)
    assert sorted(by_name(data)) == ["Alice Adams", "Bob Brown"]  # never the unlinked profile
    assert by_name(data)["Bob Brown"]["timezone"] == "Asia/Kolkata"
    assert by_name(data)["Bob Brown"]["local_date"] == "2026-11-16"  # 17:30 in Kolkata
    assert by_name(data)["Alice Adams"]["role"] == "caretaker"


def test_medication_overview_and_adherence_consistency(client, clock):
    owner = elderly(client)
    family = new_user(client, "family_member")
    link(client, owner, family, "family_member")
    client.post("/api/medications", json=MED, headers=owner["headers"])
    client.post("/api/medications", json={**MED, "name": "Aspirin", "frequency": "once_daily", "times": ["09:00"]},
                headers=owner["headers"])
    doses = client.get("/api/doses/today", headers=owner["headers"]).json()["doses"]
    met_morning = next(d for d in doses if d["medication_name"] == "Metformin" and d["local_time"] == "08:00")
    client.patch(f"/api/doses/{met_morning['id']}/status", json={"status": "taken", "expected_status": "pending"},
                 headers=owner["headers"])
    aspirin = next(d for d in doses if d["medication_name"] == "Aspirin")
    client.patch(f"/api/doses/{aspirin['id']}/status", json={"status": "missed", "expected_status": "pending"},
                 headers=owner["headers"])

    p = dashboard(client, family)["profiles"][0]
    assert p["active_medications"] == 2
    assert [(d["local_time"], d["status"]) for d in p["today_doses"]] == [
        ("08:00", "taken"), ("09:00", "missed"), ("20:00", "pending")]
    assert not any(d["can_mark_taken"] or d["can_mark_missed"] for d in p["today_doses"])  # read-only
    assert p["next_dose"]["local_time"] == "20:00"
    assert (p["today"]["total"], p["today"]["taken"], p["today"]["missed"], p["today"]["pending"]) == (2, 1, 1, 0)
    assert p["today"]["adherence_percent"] == 50.0

    # Same numbers as the existing adherence endpoints (one rule, not a second calculation).
    owner_today = client.get("/api/adherence", headers=owner["headers"]).json()["today"]
    member_today = client.get(f"/api/linked-profiles/{owner['profile']['id']}/adherence",
                              headers=family["headers"]).json()["today"]
    assert p["today"] == owner_today == member_today

    activity = p["recent_activity"]
    assert {(i["kind"], i["subject"]) for i in activity} == {("dose_taken", "Metformin 500 mg"),
                                                           ("dose_missed", "Aspirin 500 mg")}


def test_no_doses_means_no_percentage(client, clock):
    owner = elderly(client)
    carer = new_user(client, "caretaker")
    link(client, owner, carer, "caretaker")
    p = dashboard(client, carer)["profiles"][0]
    assert p["today"]["total"] == 0 and p["today"]["adherence_percent"] is None
    assert p["today_doses"] == [] and p["next_dose"] is None and p["upcoming_appointments"] == []
    assert p["recent_activity"] == []


def test_appointment_overview(client, clock):
    owner = elderly(client)
    carer = new_user(client, "caretaker")
    link(client, owner, carer, "caretaker")
    for day in ("2026-11-25", "2026-11-18", "2026-11-30", "2026-12-05"):
        client.post("/api/appointments", json={**APPT, "appointment_date": day}, headers=owner["headers"])
    cancelled = client.post("/api/appointments", json={**APPT, "appointment_date": "2026-11-17"},
                            headers=owner["headers"]).json()
    client.post(f"/api/appointments/{cancelled['id']}/cancel", headers=owner["headers"])

    p = dashboard(client, carer)["profiles"][0]
    assert [a["appointment_date"] for a in p["upcoming_appointments"]] == ["2026-11-18", "2026-11-25", "2026-11-30"]
    assert p["upcoming_appointment_count"] == 4
    assert not any(a["can_edit"] or a["can_cancel"] for a in p["upcoming_appointments"])
    assert [(i["kind"], i["place"]) for i in p["recent_activity"]] == [("appointment_cancelled", "Heart Clinic")]

    clock.now = T0 + timedelta(days=3)  # first appointment passed; never auto-completed
    p = dashboard(client, carer)["profiles"][0]
    assert p["upcoming_appointments"][0]["appointment_date"] == "2026-11-25"
    assert p["upcoming_appointment_count"] == 3


def test_revocation_removes_profile_immediately(client, clock):
    a, b = elderly(client, "Alice Adams"), elderly(client, "Bob Brown")
    carer = new_user(client, "caretaker")
    link(client, a, carer, "caretaker")
    link(client, b, carer, "caretaker")
    rel = client.get("/api/relationships", headers=a["headers"]).json()[0]["id"]
    assert client.delete(f"/api/relationships/{rel}", headers=a["headers"]).status_code == 204
    assert list(by_name(dashboard(client, carer))) == ["Bob Brown"]


def test_demo_isolation(client, auth_settings, clock):
    auth_settings.demo_accounts_enabled = True
    real_owner = elderly(client, "Real Person")
    client.post("/api/medications", json=MED, headers=real_owner["headers"])
    real_carer = new_user(client, "caretaker")
    link(client, real_owner, real_carer, "caretaker")

    provision_demo_accounts(UserRepository(mongodb.db), auth_settings)
    provision_demo_sample_data(mongodb.db, horizon_days=7, early_minutes=120, now=clock.now)
    for email, pw in (("caretaker.demo@eldercare.com", "CareDemo2026!"), ("family.demo@eldercare.com", "FamilyDemo2026!")):
        token = client.post("/api/auth/login", json={"email": email, "password": pw}).json()["access_token"]
        data = dashboard(client, {"headers": {"Authorization": f"Bearer {token}"}})
        assert [p["full_name"] for p in data["profiles"]] == ["Demo Elderly User"]
        p = data["profiles"][0]
        assert p["is_demo"] and p["active_medications"] == 3 and p["today_doses"]
        assert p["upcoming_appointment_count"] == 2
        assert {i["kind"] for i in p["recent_activity"]} >= {"dose_taken", "appointment_completed"}
    assert [p["full_name"] for p in dashboard(client, real_carer)["profiles"]] == ["Real Person"]
