"""Reminder / alert generation and delivery.

One `run_cycle` (called by the background scheduler every NOTIFICATION_INTERVAL_SECONDS):

1. Top up dose schedules (so reminders never depend on someone opening the app).
2. Create notifications that are due now. Each has a deterministic `dedupe_key` with a unique
   index, so re-running a cycle, several app instances, or a restart never creates duplicates.
3. Deliver pending notifications, each claimed atomically with a lease (a crash mid-send is
   retried after the lease; at most MAX_ATTEMPTS tries). Relevance and caretaker access are
   re-checked right before sending.

Dose and appointment statuses are only READ here - nothing is ever marked taken/missed/completed.
Emails contain times, never medication names or other medical detail.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol

from bson import ObjectId
from pymongo.database import Database

from app.core.config import Settings
from app.core.time import zone
from app.db.indexes import (
    APPOINTMENTS_COLLECTION,
    DOSES_COLLECTION,
    MEDICATIONS_COLLECTION,
    PROFILES_COLLECTION,
    RELATIONSHIPS_COLLECTION,
)
from app.repositories.doses import DoseRepository
from app.repositories.medications import MedicationRepository
from app.repositories.notifications import MAX_ATTEMPTS, NotificationRepository, PreferenceRepository
from app.repositories.users import UserRepository
from app.services.email import DeliveryError
from app.services.medications import MedicationService, Scope

logger = logging.getLogger(__name__)

MAX_MED_REMINDER = timedelta(minutes=120)
MAX_APPT_REMINDER = timedelta(minutes=10080)
MISSED_LOOKBACK = timedelta(hours=24)  # older unrecorded doses (e.g. after downtime) are not alerted
RETRY_DELAY = timedelta(minutes=5)
DELIVERIES_PER_CYCLE = 100

PREVIEW_NOT_CONFIGURED = "Email delivery is not configured, so this was recorded as a preview and not sent."
PREVIEW_DEMO = "Demo account: emails are never sent for demo data."


class Sender(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


@dataclass
class CycleResult:
    created: int = 0
    delivered: dict[str, int] = field(default_factory=dict)


def _fmt_date(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime("%A %d %B %Y")


class NotificationEngine:
    def __init__(self, db: Database, settings: Settings, sender: Sender | None) -> None:
        self.db = db
        self.settings = settings
        self.sender = sender
        self.notifications = NotificationRepository(db)
        self.prefs = PreferenceRepository(db)
        self.users = UserRepository(db)
        self.med_service = MedicationService(
            MedicationRepository(db), DoseRepository(db),
            horizon_days=settings.dose_schedule_horizon_days, early_minutes=settings.dose_early_take_minutes,
        )

    # ---- cycle ---------------------------------------------------------------------------------

    def run_cycle(self, now: datetime) -> CycleResult:
        result = CycleResult()
        result.created = self.generate(now)
        result.delivered = self.deliver_due(now)
        return result

    def generate(self, now: datetime) -> int:
        profiles = {p["user_id"]: p for p in self.db[PROFILES_COLLECTION].find({})}
        self._top_up_schedules(profiles, now)

        grace = timedelta(minutes=self.settings.missed_dose_grace_minutes)
        upcoming_doses = list(self.db[DOSES_COLLECTION].find(
            {"status": "pending", "scheduled_at": {"$gt": now, "$lte": now + MAX_MED_REMINDER}}, {"history": 0}))
        missed_doses = list(self.db[DOSES_COLLECTION].find(
            {"status": "pending", "scheduled_at": {"$gte": now - MISSED_LOOKBACK, "$lte": now - grace}}, {"history": 0}))
        appointments = list(self.db[APPOINTMENTS_COLLECTION].find(
            {"status": "scheduled", "scheduled_at": {"$gt": now, "$lte": now + MAX_APPT_REMINDER}}, {"history": 0}))

        owners = {d["user_id"] for d in upcoming_doses + missed_doses} | {a["user_id"] for a in appointments}
        if not owners:
            return 0
        rels = list(self.db[RELATIONSHIPS_COLLECTION].find({"elderly_user_id": {"$in": list(owners)}, "status": "active"}))
        people = self.users.get_many(list(owners | {r["member_user_id"] for r in rels}))
        prefs = self.prefs.get_many(list(people))
        meds = {m["_id"]: m for m in self.db[MEDICATIONS_COLLECTION].find(
            {"_id": {"$in": list({d["medication_id"] for d in upcoming_doses + missed_doses})}})}

        created = 0
        for d in upcoming_doses:
            owner, p = people.get(d["user_id"]), prefs.get(d["user_id"])
            profile = profiles.get(d["user_id"])
            if not (owner and p and profile and p.email_enabled and p.medication_reminders):
                continue
            if now < d["scheduled_at"] - timedelta(minutes=p.medication_reminder_minutes):
                continue
            created += self._create(now, "medication_reminder", owner, "self", profile, d, meds.get(d["medication_id"]))

        for d in missed_doses:
            owner, p, profile = people.get(d["user_id"]), prefs.get(d["user_id"]), profiles.get(d["user_id"])
            if not (owner and p and profile):
                continue
            med = meds.get(d["medication_id"])
            if p.email_enabled and p.missed_dose_alerts:
                created += self._create(now, "missed_dose", owner, "self", profile, d, med)
            if p.notify_caretakers_of_missed_doses:
                for r in rels:
                    member = people.get(r["member_user_id"])
                    mp = prefs.get(r["member_user_id"])
                    if (r["elderly_user_id"] != d["user_id"] or member is None or mp is None
                            or bool(r.get("is_demo")) != bool(d.get("is_demo"))
                            or not (mp.email_enabled and mp.missed_dose_alerts)):
                        continue
                    created += self._create(now, "missed_dose", member, r["role"], profile, d, med)

        for a in appointments:
            owner, p, profile = people.get(a["user_id"]), prefs.get(a["user_id"]), profiles.get(a["user_id"])
            if not (owner and p and profile and p.email_enabled and p.appointment_reminders):
                continue
            if now < a["scheduled_at"] - timedelta(minutes=p.appointment_reminder_minutes):
                continue
            created += self._create(now, "appointment_reminder", owner, "self", profile, a, None)
        return created

    def _top_up_schedules(self, profiles: dict, now: datetime) -> None:
        active = list(self.db[MEDICATIONS_COLLECTION].find({"status": "active"}))
        by_owner: dict[ObjectId, list[dict]] = {}
        for m in active:
            by_owner.setdefault(m["user_id"], []).append(m)
        for owner, owned in by_owner.items():
            profile = profiles.get(owner)
            if profile is not None:
                self.med_service.ensure_schedule(Scope(owner, profile, False), now, owned)

    # ---- content -------------------------------------------------------------------------------

    def _create(self, now: datetime, kind: str, recipient: dict, role: str, profile: dict, item: dict,
                med: dict | None) -> int:
        tz = zone(profile.get("timezone"))
        is_appt = kind == "appointment_reminder"
        local_date = item["appointment_date"] if is_appt else item["local_date"]
        local_time = item["appointment_time"] if is_appt else item["local_time"]
        subject, body = self._render(kind, role, recipient["name"], profile["full_name"], local_date, local_time,
                                     str(tz.key), item.get("clinic_name"))
        doc = {
            "dedupe_key": f"{kind}:{item['_id']}:{item['scheduled_at'].isoformat()}:{recipient['_id']}",
            "kind": kind,
            "owner_user_id": item["user_id"],
            "profile_id": profile["_id"],
            "recipient_user_id": recipient["_id"],
            "recipient_role": role,
            "recipient_name": recipient["name"],
            "recipient_email": recipient["email"],
            "about_name": profile["full_name"],
            "related_type": "appointment" if is_appt else "dose",
            "related_id": item["_id"],
            "related_label": item["doctor_name"] if is_appt else (f"{med['name']} {med['dosage']}" if med else None),
            "event_at": item["scheduled_at"],
            "local_date": local_date,
            "local_time": local_time,
            "timezone": str(tz.key),
            "subject": subject,
            "body": body,
            "status": "pending",
            "attempts": 0,
            "next_attempt_at": now,
            "created_at": now,
            "sent_at": None,
            "failure_reason": None,
            "delivery_note": None,
            "is_demo": bool(item.get("is_demo")),
        }
        if self.notifications.create_if_absent(doc):
            logger.info("Notification queued: %s", kind)  # no names, addresses or medical detail
            return 1
        return 0

    def _render(self, kind: str, role: str, name: str, about: str, local_date: str, local_time: str, tz: str,
                place: str | None) -> tuple[str, str]:
        url = self.settings.app_base_url.rstrip("/")
        when = f"{local_time} on {_fmt_date(local_date)} ({tz.replace('_', ' ')} time)"
        sign = "\n\nElderCare Connect"
        if kind == "medication_reminder":
            return (f"Medicine reminder for {local_time}",
                    f"Hello {name},\n\nThis is a reminder that a medicine dose is due at {when}.\n\n"
                    f"When you have taken it, please record it in ElderCare Connect: {url}/medications{sign}")
        if kind == "missed_dose" and role == "self":
            return (f"Dose not yet recorded ({local_time})",
                    f"Hello {name},\n\nA medicine dose due at {when} has not been recorded yet.\n\n"
                    f"If you have taken it, please record it: {url}/medications{sign}")
        if kind == "missed_dose":
            return (f"{about} has not recorded a dose ({local_time})",
                    f"Hello {name},\n\n{about} has not recorded a medicine dose that was due at {when}.\n\n"
                    f"You may want to check in with them. Details: {url}/care{sign}")
        at = f" at {place}" if place else ""
        return (f"Appointment reminder: {_fmt_date(local_date)} at {local_time}",
                f"Hello {name},\n\nThis is a reminder of your appointment{at} at {when}.\n\n"
                f"Details: {url}/appointments{sign}")

    # ---- delivery ------------------------------------------------------------------------------

    def deliver_due(self, now: datetime) -> dict[str, int]:
        self.notifications.fail_exhausted(now)
        counts: dict[str, int] = {}
        for _ in range(DELIVERIES_PER_CYCLE):
            doc = self.notifications.claim_next(now)
            if doc is None:
                break
            status = self.deliver(doc, now)
            counts[status] = counts.get(status, 0) + 1
        return counts

    def deliver_one(self, notification_id: ObjectId, now: datetime) -> str | None:
        doc = self.notifications.claim(notification_id, now)
        return self.deliver(doc, now) if doc else None

    def deliver(self, doc: dict, now: datetime) -> str:
        """Deliver one CLAIMED notification and record the outcome. Returns the final status."""
        skip = self._no_longer_relevant(doc, now)
        if skip:
            return self._finish(doc, "skipped", note=skip)
        if doc.get("is_demo"):
            return self._finish(doc, "preview", note=PREVIEW_DEMO)
        if not self.settings.email_delivery_active or self.sender is None:
            return self._finish(doc, "preview", note=PREVIEW_NOT_CONFIGURED)
        try:
            self.sender.send(doc["recipient_email"], doc["subject"], doc["body"])
        except Exception as exc:  # DeliveryError carries a safe message; anything else is generic
            reason = str(exc) if isinstance(exc, DeliveryError) else "Unexpected delivery error."
            logger.warning("Notification delivery failed (attempt %s): %s", doc["attempts"], reason)
            if doc["attempts"] >= MAX_ATTEMPTS:
                return self._finish(doc, "failed", reason=reason)
            self.notifications.finish(doc["_id"], {
                "status": "pending", "failure_reason": reason, "next_attempt_at": now + RETRY_DELAY})
            return "retrying"
        return self._finish(doc, "sent", sent_at=now)

    def _finish(self, doc: dict, status: str, *, note: str | None = None, reason: str | None = None,
                sent_at: datetime | None = None) -> str:
        self.notifications.finish(doc["_id"], {
            "status": status, "delivery_note": note, "failure_reason": reason, "sent_at": sent_at})
        return status

    def _no_longer_relevant(self, doc: dict, now: datetime) -> str | None:
        kind = doc["kind"]
        if kind == "test":
            return None
        if doc["recipient_role"] != "self":
            rel = self.db[RELATIONSHIPS_COLLECTION].find_one({
                "elderly_user_id": doc["owner_user_id"], "member_user_id": doc["recipient_user_id"],
                "status": "active", "is_demo": doc.get("is_demo", False)})
            if rel is None:
                return "Not sent: this person no longer has access."
        if doc["related_type"] == "dose":
            dose = self.db[DOSES_COLLECTION].find_one({"_id": doc["related_id"]}, {"status": 1})
            if dose is None or dose["status"] != "pending":
                return "Not sent: the dose was already recorded or cancelled."
            if kind == "medication_reminder" and doc["event_at"] <= now:
                return "Not sent: the dose time had already passed."
        else:
            appt = self.db[APPOINTMENTS_COLLECTION].find_one({"_id": doc["related_id"]}, {"status": 1, "scheduled_at": 1})
            if appt is None or appt["status"] != "scheduled" or appt["scheduled_at"] != doc["event_at"]:
                return "Not sent: the appointment was changed, cancelled or completed."
            if appt["scheduled_at"] <= now:
                return "Not sent: the appointment time had already passed."
        return None

    # ---- test message --------------------------------------------------------------------------

    def queue_test(self, user: dict, now: datetime) -> ObjectId | None:
        doc = {
            "dedupe_key": f"test:{user['_id']}:{now.strftime('%Y%m%d%H%M')}",  # at most one per minute
            "kind": "test", "owner_user_id": user["_id"], "profile_id": None,
            "recipient_user_id": user["_id"], "recipient_role": "self", "recipient_name": user["name"],
            "recipient_email": user["email"], "about_name": None, "related_type": None, "related_id": None,
            "related_label": None, "event_at": None, "local_date": None, "local_time": None, "timezone": None,
            "subject": "ElderCare Connect test message",
            "body": f"Hello {user['name']},\n\nThis is a test message from ElderCare Connect. "
                    "If you received it, email notifications are working.\n\nElderCare Connect",
            "status": "pending", "attempts": 0, "next_attempt_at": now, "created_at": now, "sent_at": None,
            "failure_reason": None, "delivery_note": None, "is_demo": bool(user.get("is_demo")),
        }
        if not self.notifications.create_if_absent(doc):
            return None
        return doc["_id"]  # set by insert_one
