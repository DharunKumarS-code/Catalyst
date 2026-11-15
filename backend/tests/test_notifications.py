"""Notification generation, delivery, history and preferences (frozen clock, fake SMTP)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.db.indexes import DOSES_COLLECTION, NOTIFICATIONS_COLLECTION
from app.db.mongodb import mongodb
from app.demo.provisioning import provision_demo_accounts
from app.demo.sample_data import provision_demo_sample_data
from app.repositories.users import UserRepository
from app.services.email import DeliveryError
from app.services.notifications import NotificationEngine
from tests.helpers import create_profile, invite, new_user, redeem

UTC = timezone.utc
T0 = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
ONCE = {"name": "Metformin", "dosage": "500 mg", "frequency": "once_daily", "start_date": "2026-11-16"}


class Clock:
    now = T0

    def __call__(self):
        return self.now


class FakeSender:
    def __init__(self, fail_with: str | None = None):
        self.sent: list[tuple[str, str, str]] = []
        self.fail_with = fail_with

    def send(self, to, subject, body):
        if self.fail_with:
            raise DeliveryError(self.fail_with)
        self.sent.append((to, subject, body))


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    for mod in ("appointments", "medications", "profiles", "notifications"):
        monkeypatch.setattr(f"app.api.routes.{mod}.utc_now", c)
    return c


@pytest.fixture
def smtp(auth_settings):
    auth_settings.email_mode = "smtp"
    auth_settings.smtp_host = "smtp.test"
    auth_settings.smtp_from = "noreply@test"
    return auth_settings


def engine(settings, sender=None):
    return NotificationEngine(mongodb.db, settings, sender)


def elderly(client, **profile):
    user = new_user(client, "elderly")
    user["profile"] = create_profile(client, user, **profile)
    return user


def notes(**query):
    return list(mongodb.db[NOTIFICATIONS_COLLECTION].find(query))


# ---- medication reminders ----


def test_medication_reminder_timing_timezone_and_content(client, clock, smtp):
    owner = elderly(client, timezone="America/New_York")  # 07:00 local at T0
    client.post("/api/medications", json={**ONCE, "times": ["08:00"]}, headers=owner["headers"])  # 13:00Z
    sender = FakeSender()
    assert engine(smtp, sender).run_cycle(T0 + timedelta(minutes=40)).created == 0  # 20 min before: too early
    result = engine(smtp, sender).run_cycle(T0 + timedelta(minutes=46))  # 14 min before (default 15)
    assert result.created == 1 and result.delivered == {"sent": 1}
    to, subject, body = sender.sent[0]
    assert to == owner["user"]["email"] and "08:00" in subject
    assert "America/New York" in body and "Metformin" not in body + subject  # no medical detail in email
    doc = notes()[0]
    assert doc["kind"] == "medication_reminder" and doc["status"] == "sent" and doc["related_label"] == "Metformin 500 mg"


def test_reminder_preferences_respected(client, clock, smtp):
    owner = elderly(client)
    client.post("/api/medications", json={**ONCE, "times": ["12:50"]}, headers=owner["headers"])
    prefs = client.get("/api/notifications/preferences", headers=owner["headers"]).json()
    client.put("/api/notifications/preferences", json={**prefs, "medication_reminder_minutes": 60},
               headers=owner["headers"])
    assert engine(smtp, FakeSender()).run_cycle(T0).created == 1  # 50 min before, within 60
    client.put("/api/notifications/preferences", json={**prefs, "email_enabled": False}, headers=owner["headers"])
    client.post("/api/medications", json={**ONCE, "name": "Aspirin", "times": ["12:55"]}, headers=owner["headers"])
    assert engine(smtp, FakeSender()).run_cycle(T0 + timedelta(minutes=45)).created == 0


# ---- missed doses ----


def test_missed_dose_escalation_without_changing_status(client, clock, smtp):
    owner = elderly(client)
    client.post("/api/medications", json={**ONCE, "times": ["10:30"]}, headers=owner["headers"])  # 90 min ago
    carer, family, stranger = new_user(client, "caretaker"), new_user(client, "family_member"), new_user(client, "caretaker")
    assert redeem(client, carer, invite(client, owner, "caretaker")["code"]).status_code == 201
    assert redeem(client, family, invite(client, owner, "family_member")["code"]).status_code == 201
    prefs = client.get("/api/notifications/preferences", headers=family["headers"]).json()
    client.put("/api/notifications/preferences", json={**prefs, "missed_dose_alerts": False}, headers=family["headers"])

    sender = FakeSender()
    assert engine(smtp, sender).run_cycle(T0).created == 2
    recipients = sorted(n["recipient_role"] for n in notes(kind="missed_dose"))
    assert recipients == ["caretaker", "self"]  # family opted out; stranger never linked
    assert stranger["user"]["email"] not in [s[0] for s in sender.sent]
    carer_mail = next(s for s in sender.sent if s[0] == carer["user"]["email"])
    assert "Margaret Smith" in carer_mail[1] and "Metformin" not in carer_mail[2]
    assert mongodb.db[DOSES_COLLECTION].find_one({"local_time": "10:30"})["status"] == "pending"  # never changed


def test_no_missed_alert_within_grace_or_for_cancelled(client, clock, smtp):
    owner = elderly(client)
    client.post("/api/medications", json={**ONCE, "times": ["11:30"]}, headers=owner["headers"])  # 30 min ago
    assert engine(smtp, FakeSender()).run_cycle(T0).created == 0  # grace is 60 minutes
    mongodb.db[DOSES_COLLECTION].update_many({}, {"$set": {"status": "cancelled"}})
    assert engine(smtp, FakeSender()).run_cycle(T0 + timedelta(hours=2)).created == 0


def test_revocation_and_recording_before_delivery_skip_sending(client, clock, smtp):
    owner = elderly(client)
    client.post("/api/medications", json={**ONCE, "times": ["10:00"]}, headers=owner["headers"])
    carer = new_user(client, "caretaker")
    redeem(client, carer, invite(client, owner, "caretaker")["code"])
    assert engine(smtp, None).generate(T0) == 2  # queued, not yet delivered
    rel = client.get("/api/relationships", headers=owner["headers"]).json()[0]["id"]
    client.delete(f"/api/relationships/{rel}", headers=owner["headers"])
    sender = FakeSender()
    engine(smtp, sender).deliver_due(T0)
    assert notes(recipient_role="caretaker")[0]["status"] == "skipped"
    assert notes(recipient_role="self")[0]["status"] == "sent"
    assert [s[0] for s in sender.sent] == [owner["user"]["email"]]
    # A revoked caretaker is not alerted again later.
    assert engine(smtp, sender).generate(T0 + timedelta(hours=1)) == 0


# ---- appointments ----


def test_appointment_reminders(client, clock, smtp):
    owner = elderly(client, timezone="Asia/Kolkata")
    appt = {"doctor_name": "Dr. Shah", "clinic_name": "Heart Clinic", "appointment_time": "10:30"}
    soon = client.post("/api/appointments", json={**appt, "appointment_date": "2026-11-17"}, headers=owner["headers"]).json()
    far = client.post("/api/appointments", json={**appt, "appointment_date": "2026-11-25"}, headers=owner["headers"]).json()
    cancelled = client.post("/api/appointments", json={**appt, "appointment_date": "2026-11-17", "appointment_time": "11:00"},
                            headers=owner["headers"]).json()
    client.post(f"/api/appointments/{cancelled['id']}/cancel", headers=owner["headers"])
    sender = FakeSender()
    assert engine(smtp, sender).run_cycle(T0).created == 1  # default 24h; 10:30 IST = 05:00Z on the 17th
    doc = notes(kind="appointment_reminder")[0]
    assert doc["related_id"] == mongodb.db["appointments"].find_one({"doctor_name": "Dr. Shah", "appointment_date": "2026-11-17", "appointment_time": "10:30"})["_id"]
    assert "Asia/Kolkata" in sender.sent[0][2] and "Heart Clinic" in sender.sent[0][2] and "Dr. Shah" not in sender.sent[0][2]
    assert far["id"] and soon["id"]


def test_rescheduled_appointment_gets_new_reminder_old_one_skipped(client, clock, smtp):
    owner = elderly(client)
    body = {"doctor_name": "Dr. Lee", "clinic_name": "Eye Clinic", "appointment_date": "2026-11-17", "appointment_time": "09:00"}
    a = client.post("/api/appointments", json=body, headers=owner["headers"]).json()
    assert engine(smtp, None).generate(T0) == 1
    client.put(f"/api/appointments/{a['id']}", json={**body, "appointment_time": "10:00"}, headers=owner["headers"])
    sender = FakeSender()
    engine(smtp, sender).run_cycle(T0 + timedelta(minutes=1))
    assert sorted(n["status"] for n in notes()) == ["sent", "skipped"]
    assert len(sender.sent) == 1


# ---- duplicates, restarts, delivery outcomes ----


def test_no_duplicates_across_cycles_and_restarts(client, clock, smtp):
    owner = elderly(client)
    client.post("/api/medications", json={**ONCE, "times": ["10:00"]}, headers=owner["headers"])
    sender = FakeSender()
    for minutes in (0, 1, 2):
        engine(smtp, sender).run_cycle(T0 + timedelta(minutes=minutes))  # new engine = like a restart
    assert len(notes()) == 1 and len(sender.sent) == 1


def test_interrupted_send_is_retried_once_after_lease(client, clock, smtp):
    owner = elderly(client)
    client.post("/api/medications", json={**ONCE, "times": ["10:00"]}, headers=owner["headers"])
    e = engine(smtp, FakeSender())
    e.generate(T0)
    claimed = e.notifications.claim_next(T0)  # process "crashes" before finishing
    assert claimed["status"] == "sending"
    sender = FakeSender()
    assert engine(smtp, sender).deliver_due(T0 + timedelta(minutes=1)) == {}  # lease still held
    assert engine(smtp, sender).deliver_due(T0 + timedelta(minutes=6)) == {"sent": 1}
    assert len(sender.sent) == 1 and notes()[0]["attempts"] == 2


def test_smtp_failure_retries_then_fails(client, clock, smtp):
    owner = elderly(client)
    client.post("/api/medications", json={**ONCE, "times": ["10:00"]}, headers=owner["headers"])
    bad = FakeSender(fail_with="Could not connect to the mail server.")
    assert engine(smtp, bad).run_cycle(T0).delivered == {"retrying": 1}
    doc = notes()[0]
    assert doc["status"] == "pending" and doc["failure_reason"] == "Could not connect to the mail server."
    engine(smtp, bad).deliver_due(T0 + timedelta(minutes=6))
    engine(smtp, bad).deliver_due(T0 + timedelta(minutes=12))
    doc = notes()[0]
    assert doc["status"] == "failed" and doc["attempts"] == 3
    assert engine(smtp, FakeSender()).deliver_due(T0 + timedelta(minutes=30)) == {}  # not retried forever


def test_preview_mode_never_sends(client, clock, auth_settings):
    owner = elderly(client)
    client.post("/api/medications", json={**ONCE, "times": ["10:00"]}, headers=owner["headers"])
    sender = FakeSender()
    assert engine(auth_settings, sender).run_cycle(T0).delivered == {"preview": 1}  # default email_mode=preview
    assert sender.sent == [] and "not configured" in notes()[0]["delivery_note"]


# ---- history, preferences, status, test message ----


def test_history_access(client, clock, smtp):
    owner = elderly(client)
    client.post("/api/medications", json={**ONCE, "times": ["10:00"]}, headers=owner["headers"])
    carer = new_user(client, "caretaker")
    redeem(client, carer, invite(client, owner, "caretaker")["code"])
    other = elderly(client)
    engine(smtp, FakeSender()).run_cycle(T0)

    mine = client.get("/api/notifications", headers=owner["headers"]).json()
    assert sorted((n["recipient_role"], n["recipient_is_you"]) for n in mine) == [("caretaker", False), ("self", True)]
    assert all("recipient_email" not in n and "body" not in n for n in mine)
    theirs = client.get("/api/notifications", headers=carer["headers"]).json()
    assert [(n["recipient_role"], n["about_name"], n["status"]) for n in theirs] == [("caretaker", "Margaret Smith", "sent")]
    assert client.get("/api/notifications", headers=other["headers"]).json() == []
    assert client.get("/api/notifications").status_code == 401


def test_preferences_validation_and_ownership(client, clock):
    owner = elderly(client)
    carer = new_user(client, "caretaker")
    defaults = client.get("/api/notifications/preferences", headers=owner["headers"]).json()
    assert defaults["medication_reminder_minutes"] == 15 and defaults["appointment_reminder_minutes"] == 1440
    for bad in ({"medication_reminder_minutes": 1}, {"appointment_reminder_minutes": 99999}, {"user_id": "x"}):
        assert client.put("/api/notifications/preferences", json={**defaults, **bad},
                          headers=owner["headers"]).status_code == 422
    client.put("/api/notifications/preferences", json={**defaults, "email_enabled": False}, headers=carer["headers"])
    assert client.get("/api/notifications/preferences", headers=owner["headers"]).json()["email_enabled"] is True


def test_status_and_test_message(client, clock):
    owner = elderly(client)
    st = client.get("/api/notifications/status", headers=owner["headers"]).json()
    assert st["delivery"] == "preview" and st["smtp_configured"] is False
    assert set(st) == {"delivery", "smtp_configured", "scheduler_running", "check_interval_seconds",
                       "missed_dose_grace_minutes", "last_check_at"}
    res = client.post("/api/notifications/test", headers=owner["headers"])
    assert res.status_code == 202 and res.json()["kind"] == "test"
    history = client.get("/api/notifications", headers=owner["headers"]).json()
    assert history[0]["status"] == "preview"  # delivered by the background task after the response
    assert client.post("/api/notifications/test", headers=owner["headers"]).status_code == 429


def test_demo_isolation_never_emails(client, clock, smtp):
    smtp.demo_accounts_enabled = True
    provision_demo_accounts(UserRepository(mongodb.db), smtp)
    provision_demo_sample_data(mongodb.db, horizon_days=7, early_minutes=120, now=T0)
    real = elderly(client)
    client.post("/api/medications", json={**ONCE, "times": ["10:00"]}, headers=real["headers"])
    sender = FakeSender()
    engine(smtp, sender).run_cycle(T0)
    demo_docs = notes(is_demo=True)
    assert demo_docs and all(n["status"] == "preview" for n in demo_docs)
    assert all(s[0] == real["user"]["email"] for s in sender.sent)  # only the real user was emailed
    token = client.post("/api/auth/login", json={"email": "caretaker.demo@eldercare.com", "password": "CareDemo2026!"}).json()["access_token"]
    demo_hist = client.get("/api/notifications", headers={"Authorization": f"Bearer {token}"}).json()
    assert demo_hist and all(n["about_name"] == "Demo Elderly User" for n in demo_hist)
    assert all(n["about_name"] != "Demo Elderly User" for n in client.get("/api/notifications", headers=real["headers"]).json())
