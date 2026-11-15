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
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol

from bson import ObjectId
from pymongo.database import Database

from app.core.config import Settings
from app.core.time import zone
from app.repositories.appointments import AppointmentRepository
from app.repositories.doses import DoseRepository
from app.repositories.medications import MedicationRepository
from app.repositories.notifications import MAX_ATTEMPTS, NotificationRepository, PreferenceRepository
from app.repositories.profiles import ProfileRepository
from app.repositories.relationships import RelationshipRepository
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


@dataclass
class _Due:
    upcoming: list[dict]
    missed: list[dict]
    appointments: list[dict]

    def owners(self) -> set[ObjectId]:
        return {d["user_id"] for d in self.upcoming + self.missed} | {a["user_id"] for a in self.appointments}


@dataclass
class _Context:
    """Everything one generation pass needs, loaded once with batched queries."""

    now: datetime
    profiles: dict
    people: dict
    prefs: dict
    rels: list[dict]
    meds: dict

    def person(self, user_id: ObjectId) -> tuple:
        return self.people.get(user_id), self.prefs.get(user_id), self.profiles.get(user_id)


class NotificationEngine:
    def __init__(self, db: Database, settings: Settings, sender: Sender | None) -> None:
        self.db = db
        self.settings = settings
        self.sender = sender
        self.notifications = NotificationRepository(db)
        self.prefs = PreferenceRepository(db)
        self.users = UserRepository(db)
        self.profiles = ProfileRepository(db)
        self.relationships = RelationshipRepository(db)
        self.medications = MedicationRepository(db)
        self.doses = DoseRepository(db)
        self.appointments = AppointmentRepository(db)
        self.med_service = MedicationService(
            self.medications,
            self.doses,
            horizon_days=settings.dose_schedule_horizon_days,
            early_minutes=settings.dose_early_take_minutes,
        )

    # ---- cycle ---------------------------------------------------------------------------------

    def run_cycle(self, now: datetime) -> CycleResult:
        result = CycleResult()
        result.created = self.generate(now)
        result.delivered = self.deliver_due(now)
        return result

    def generate(self, now: datetime) -> int:
        """Queue every reminder/alert that is due now. Returns how many were new."""
        profiles = self._top_up_schedules(now)
        due = self._load_due(now)
        owners = due.owners()
        if not owners:
            return 0
        profiles.update(self.profiles.for_users([o for o in owners if o not in profiles]))
        rels = self.relationships.active_for_elderly_users(list(owners))
        people = self.users.get_many(list(owners | {r["member_user_id"] for r in rels}))
        meds = self.medications.labels(list({d["medication_id"] for d in due.upcoming + due.missed}))
        ctx = _Context(now, profiles, people, self.prefs.get_many(list(people)), rels, meds)

        docs = [
            *self._medication_reminders(ctx, due.upcoming),
            *self._missed_dose_alerts(ctx, due.missed),
            *self._appointment_reminders(ctx, due.appointments),
        ]
        created = self.notifications.create_many_if_absent(docs)
        if created:
            logger.info("Notifications queued: %s", created)  # no names, addresses or medical detail
        return created

    def _top_up_schedules(self, now: datetime) -> dict[ObjectId, dict]:
        """Generate missing doses, so reminders never depend on someone opening the app. Only
        medications whose generated doses end before the horizon are loaded. Returns the
        profiles it loaded, so they are not fetched twice."""
        # A user's local date is at most one day ahead of UTC, so this bound is safe for every zone.
        bound = (now.date() + timedelta(days=self.settings.dose_schedule_horizon_days + 1)).isoformat()
        by_owner: dict[ObjectId, list[dict]] = {}
        for m in self.medications.needing_top_up(bound):
            by_owner.setdefault(m["user_id"], []).append(m)
        profiles = self.profiles.for_users(list(by_owner))
        for owner, owned in by_owner.items():
            if owner in profiles:
                self.med_service.ensure_schedule(Scope(owner, profiles[owner], False), now, owned)
        return profiles

    def _load_due(self, now: datetime) -> "_Due":
        grace = timedelta(minutes=self.settings.missed_dose_grace_minutes)
        return _Due(
            upcoming=self.doses.pending_between(now, now + MAX_MED_REMINDER, include_start=False),
            missed=self.doses.pending_between(now - MISSED_LOOKBACK, now - grace, include_start=True),
            appointments=self.appointments.scheduled_between(now, now + MAX_APPT_REMINDER),
        )

    def _medication_reminders(self, ctx: "_Context", doses: list[dict]) -> Iterator[dict]:
        for d in doses:
            owner, p, profile = ctx.person(d["user_id"])
            if not (owner and p and profile and p.email_enabled and p.medication_reminders):
                continue
            if ctx.now >= d["scheduled_at"] - timedelta(minutes=p.medication_reminder_minutes):
                med = ctx.meds.get(d["medication_id"])
                yield self._build(ctx.now, "medication_reminder", owner, "self", profile, d, med)

    def _missed_dose_alerts(self, ctx: "_Context", doses: list[dict]) -> Iterator[dict]:
        for d in doses:
            owner, p, profile = ctx.person(d["user_id"])
            if not (owner and p and profile):
                continue
            med = ctx.meds.get(d["medication_id"])
            if p.email_enabled and p.missed_dose_alerts:
                yield self._build(ctx.now, "missed_dose", owner, "self", profile, d, med)
            if not p.notify_caretakers_of_missed_doses:
                continue
            for r in ctx.rels:
                member, mp = ctx.people.get(r["member_user_id"]), ctx.prefs.get(r["member_user_id"])
                if (
                    r["elderly_user_id"] != d["user_id"]
                    or member is None
                    or mp is None
                    or bool(r.get("is_demo")) != bool(d.get("is_demo"))
                    or not (mp.email_enabled and mp.missed_dose_alerts)
                ):
                    continue
                yield self._build(ctx.now, "missed_dose", member, r["role"], profile, d, med)

    def _appointment_reminders(self, ctx: "_Context", appointments: list[dict]) -> Iterator[dict]:
        for a in appointments:
            owner, p, profile = ctx.person(a["user_id"])
            if not (owner and p and profile and p.email_enabled and p.appointment_reminders):
                continue
            if ctx.now >= a["scheduled_at"] - timedelta(minutes=p.appointment_reminder_minutes):
                yield self._build(ctx.now, "appointment_reminder", owner, "self", profile, a, None)

    # ---- content -------------------------------------------------------------------------------

    def _build(
        self, now: datetime, kind: str, recipient: dict, role: str, profile: dict, item: dict, med: dict | None
    ) -> dict:
        tz = zone(profile.get("timezone"))
        is_appt = kind == "appointment_reminder"
        local_date = item["appointment_date"] if is_appt else item["local_date"]
        local_time = item["appointment_time"] if is_appt else item["local_time"]
        subject, body = self._render(
            kind,
            role,
            recipient["name"],
            profile["full_name"],
            local_date,
            local_time,
            str(tz.key),
            item.get("clinic_name"),
        )
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
        return doc

    def _render(
        self, kind: str, role: str, name: str, about: str, local_date: str, local_time: str, tz: str, place: str | None
    ) -> tuple[str, str]:
        url = self.settings.app_base_url.rstrip("/")
        when = f"{local_time} on {_fmt_date(local_date)} ({tz.replace('_', ' ')} time)"
        sign = "\n\nElderCare Connect"
        if kind == "medication_reminder":
            return (
                f"Medicine reminder for {local_time}",
                f"Hello {name},\n\nThis is a reminder that a medicine dose is due at {when}.\n\n"
                f"When you have taken it, please record it in ElderCare Connect: {url}/medications{sign}",
            )
        if kind == "missed_dose" and role == "self":
            return (
                f"Dose not yet recorded ({local_time})",
                f"Hello {name},\n\nA medicine dose due at {when} has not been recorded yet.\n\n"
                f"If you have taken it, please record it: {url}/medications{sign}",
            )
        if kind == "missed_dose":
            return (
                f"{about} has not recorded a dose ({local_time})",
                f"Hello {name},\n\n{about} has not recorded a medicine dose that was due at {when}.\n\n"
                f"You may want to check in with them. Details: {url}/care{sign}",
            )
        at = f" at {place}" if place else ""
        return (
            f"Appointment reminder: {_fmt_date(local_date)} at {local_time}",
            f"Hello {name},\n\nThis is a reminder of your appointment{at} at {when}.\n\n"
            f"Details: {url}/appointments{sign}",
        )

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
            self.notifications.finish(
                doc["_id"], {"status": "pending", "failure_reason": reason, "next_attempt_at": now + RETRY_DELAY}
            )
            return "retrying"
        return self._finish(doc, "sent", sent_at=now)

    def _finish(
        self,
        doc: dict,
        status: str,
        *,
        note: str | None = None,
        reason: str | None = None,
        sent_at: datetime | None = None,
    ) -> str:
        self.notifications.finish(
            doc["_id"],
            {"status": status, "delivery_note": note, "failure_reason": reason, "sent_at": sent_at},
            final=True,
        )
        return status

    def _no_longer_relevant(self, doc: dict, now: datetime) -> str | None:
        kind = doc["kind"]
        if kind == "test":
            return None
        if doc["recipient_role"] != "self" and not self.relationships.link_is_active(
            doc["owner_user_id"], doc["recipient_user_id"], is_demo=doc.get("is_demo", False)
        ):
            return "Not sent: this person no longer has access."
        if doc["related_type"] == "dose":
            if self.doses.status_of(doc["related_id"]) != "pending":
                return "Not sent: the dose was already recorded or cancelled."
            if kind == "medication_reminder" and doc["event_at"] <= now:
                return "Not sent: the dose time had already passed."
        else:
            appt = self.appointments.state_of(doc["related_id"])
            if appt is None or appt["status"] != "scheduled" or appt["scheduled_at"] != doc["event_at"]:
                return "Not sent: the appointment was changed, cancelled or completed."
            if appt["scheduled_at"] <= now:
                return "Not sent: the appointment time had already passed."
        return None

    # ---- test message --------------------------------------------------------------------------

    def queue_test(self, user: dict, now: datetime) -> ObjectId | None:
        doc = {
            "dedupe_key": f"test:{user['_id']}:{now.strftime('%Y%m%d%H%M')}",  # at most one per minute
            "kind": "test",
            "owner_user_id": user["_id"],
            "profile_id": None,
            "recipient_user_id": user["_id"],
            "recipient_role": "self",
            "recipient_name": user["name"],
            "recipient_email": user["email"],
            "about_name": None,
            "related_type": None,
            "related_id": None,
            "related_label": None,
            "event_at": None,
            "local_date": None,
            "local_time": None,
            "timezone": None,
            "subject": "ElderCare Connect test message",
            "body": f"Hello {user['name']},\n\nThis is a test message from ElderCare Connect. "
            "If you received it, email notifications are working.\n\nElderCare Connect",
            "status": "pending",
            "attempts": 0,
            "next_attempt_at": now,
            "created_at": now,
            "sent_at": None,
            "failure_reason": None,
            "delivery_note": None,
            "is_demo": bool(user.get("is_demo")),
        }
        if not self.notifications.create_if_absent(doc):
            return None
        return doc["_id"]  # set by insert_one
