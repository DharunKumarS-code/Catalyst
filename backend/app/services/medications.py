"""Medication, dose and adherence business rules shared by the owner and member routes."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from bson import ObjectId

from app.core.time import zone
from app.repositories.doses import DoseRepository
from app.repositories.medications import MedicationRepository
from app.schemas.medication import SCHEDULE_FIELDS, AdherenceDay, AdherencePeriod, AdherenceSummary, DoseOut
from app.services.scheduling import local_midnight_utc, plan_doses

WEEK_DAYS = 7


class DoseRuleError(Exception):
    """A requested status change that the rules do not allow. `status_code` is the HTTP code."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class Scope:
    """Whose medication data a request works on, resolved and authorized by the route."""

    owner_id: ObjectId  # the elderly user's id
    profile: dict
    can_modify: bool  # medication changes: True only for the owner
    # Recording doses: the owner always; a caretaker only when the owner has granted it on an
    # ACTIVE relationship (re-read on every request). Family members never.
    can_record: bool | None = None  # None = same as can_modify
    actor_id: ObjectId | None = None  # who is acting (defaults to the owner)
    actor_name: str | None = None
    actor_role: str = "elderly"

    @property
    def may_record(self) -> bool:
        return self.can_modify if self.can_record is None else self.can_record

    @property
    def tz(self) -> ZoneInfo:
        return zone(self.profile.get("timezone"))

    @property
    def timezone_name(self) -> str:
        return str(self.tz.key)

    def today(self, now: datetime) -> date:
        return now.astimezone(self.tz).date()


def member_scope_for(rel: dict, profile: dict, actor_id: ObjectId, actor_name: str) -> Scope:
    """Scope for a caretaker/family member on an ACTIVE relationship loaded on this request.
    Members never change medications. A caretaker may record doses only while the elderly
    owner's grant is set on that relationship; family members never can."""
    may_record = rel["role"] == "caretaker" and bool(rel.get("can_record_doses"))
    return Scope(
        owner_id=profile["user_id"],
        profile=profile,
        can_modify=False,
        can_record=may_record,
        actor_id=actor_id,
        actor_name=actor_name,
        actor_role=rel["role"],
    )


class MedicationService:
    def __init__(self, meds: MedicationRepository, doses: DoseRepository, *, horizon_days: int, early_minutes: int):
        self.meds = meds
        self.doses = doses
        self.horizon_days = horizon_days
        self.early = timedelta(minutes=early_minutes)

    # ---- schedule generation -------------------------------------------------------------

    def ensure_schedule(self, scope: Scope, now: datetime, medications: list[dict] | None = None) -> None:
        """Generate any missing doses for the owner's active medications up to the horizon.
        Idempotent: existing doses are never modified, the unique index blocks duplicates."""
        if medications is None:
            medications = self.meds.list_for_user(scope.owner_id, status="active")
        for med in medications:
            planned, through = plan_doses(med, scope.tz, now, self.horizon_days)
            if through is None:
                continue
            self.doses.insert_missing(
                [
                    {
                        "medication_id": med["_id"],
                        "user_id": med["user_id"],
                        "profile_id": med["profile_id"],
                        "is_demo": bool(med.get("is_demo")),
                        "scheduled_at": p.scheduled_at,
                        "local_date": p.local_date,
                        "local_time": p.local_time,
                        "status": "pending",
                        "status_changed_at": None,
                        "taken_at": None,
                        "history": [],
                        "created_at": now,
                    }
                    for p in planned
                ]
            )
            self.meds.mark_scheduled_through(med["_id"], through)

    def initial_schedule_from(self, scope: Scope, now: datetime) -> datetime:
        # Include all of today's doses, so a morning dose already taken can still be recorded.
        return local_midnight_utc(scope.today(now), scope.tz)

    # ---- medication changes ---------------------------------------------------------------

    def create(self, scope: Scope, data: dict, now: datetime, *, schedule_from: datetime | None = None) -> dict:
        med = self.meds.create(
            user_id=scope.owner_id,
            profile_id=scope.profile["_id"],
            data=data,
            is_demo=bool(scope.profile.get("is_demo")),
            schedule_from=schedule_from or self.initial_schedule_from(scope, now),
        )
        self.ensure_schedule(scope, now, [med])
        return med

    def update(self, scope: Scope, med: dict, data: dict, now: datetime) -> dict | None:
        schedule_changed = any(med.get(f) != data.get(f) for f in SCHEDULE_FIELDS)
        updated = self.meds.update(
            med["_id"], scope.owner_id, data, reset_schedule_from=now if schedule_changed else None
        )
        if updated is not None and schedule_changed:
            # Recorded doses (taken/missed) and doses already due are kept as history;
            # upcoming unrecorded doses are rebuilt from the new schedule.
            self.doses.delete_future_pending(med["_id"], now)
            self.doses.delete_pending_outside(med["_id"], updated["start_date"], updated.get("end_date"))
            self.ensure_schedule(scope, now, [updated])
        return updated

    def discontinue(self, scope: Scope, med_id: ObjectId, now: datetime) -> dict | None:
        med = self.meds.discontinue(med_id, scope.owner_id, now)
        if med is not None:
            self.doses.cancel_future_pending(med_id, now, now)
        return med

    def delete(self, scope: Scope, med_id: ObjectId) -> bool:
        if not self.meds.delete(med_id, scope.owner_id):
            return False
        self.doses.delete_for_medication(med_id)
        return True

    def timezone_changed(self, owner_id: ObjectId, now: datetime) -> None:
        """Upcoming unrecorded doses are rebuilt in the new zone on the next read."""
        self.doses.delete_future_pending_for_user(owner_id, now)
        self.meds.reset_schedules(owner_id, now)

    # ---- doses ---------------------------------------------------------------------------------

    def dose_views(self, scope: Scope, docs: list[dict], now: datetime, meds: dict | None = None) -> list[DoseOut]:
        """`meds` ({_id: medication}) may be passed in by callers that already loaded them."""
        if meds is None:
            meds = self.meds.get_many(scope.owner_id, list({d["medication_id"] for d in docs}))
        out = []
        for d in docs:
            med = meds.get(d["medication_id"])
            if med is None:  # medication removed concurrently
                continue
            status = d["status"]
            out.append(
                DoseOut(
                    id=str(d["_id"]),
                    medication_id=str(d["medication_id"]),
                    medication_name=med["name"],
                    dosage=med["dosage"],
                    scheduled_at=d["scheduled_at"],
                    local_date=d["local_date"],
                    local_time=d["local_time"],
                    status=status,
                    status_changed_at=d.get("status_changed_at"),
                    taken_at=d.get("taken_at"),
                    is_due=now >= d["scheduled_at"],
                    can_mark_taken=scope.may_record
                    and status != "taken"
                    and status != "cancelled"
                    and now >= d["scheduled_at"] - self.early,
                    can_mark_missed=scope.may_record and status in ("pending", "taken") and now >= d["scheduled_at"],
                    recorded_by_name=d.get("status_changed_by_name"),
                    recorded_by_role=d.get("status_changed_by_role"),
                )
            )
        return out

    def today(self, scope: Scope, now: datetime) -> tuple[str, list[DoseOut]]:
        self.ensure_schedule(scope, now)
        day = scope.today(now).isoformat()
        return day, self.dose_views(scope, self.doses.for_day(scope.owner_id, day), now)

    def history(
        self, scope: Scope, now: datetime, *, days: int, medication_id: ObjectId | None, limit: int
    ) -> list[DoseOut]:
        self.ensure_schedule(scope, now)
        since = local_midnight_utc(scope.today(now) - timedelta(days=days - 1), scope.tz)
        docs = self.doses.history(scope.owner_id, since=since, until=now, medication_id=medication_id, limit=limit)
        return self.dose_views(scope, docs, now)

    def set_status(self, scope: Scope, dose_id: ObjectId, *, new: str, expected: str, now: datetime) -> DoseOut:
        if not scope.may_record:
            raise DoseRuleError("You do not have permission to record doses for this person.", 403)
        dose = self.doses.get(dose_id, scope.owner_id)
        if dose is None:
            raise DoseRuleError("Dose not found.", 404)
        if dose["status"] == "cancelled":
            raise DoseRuleError("This dose was cancelled because the medication was stopped.", 409)
        if dose["status"] != expected:
            raise DoseRuleError("This dose was already updated. Refresh to see its current status.", 409)
        if new == expected:
            raise DoseRuleError(f"This dose is already marked as {new}.", 409)
        if new == "taken" and now < dose["scheduled_at"] - self.early:
            raise DoseRuleError("It is too early to mark this dose as taken.", 422)
        if new == "missed" and now < dose["scheduled_at"]:
            raise DoseRuleError("A dose cannot be marked as missed before its scheduled time.", 422)

        updated = self.doses.transition(
            dose_id,
            scope.owner_id,
            expected=expected,
            new=new,
            now=now,
            by=scope.actor_id or scope.owner_id,
            by_name=scope.actor_name,
            by_role=scope.actor_role,
        )
        if updated is None:  # lost a race with another update
            raise DoseRuleError("This dose was already updated. Refresh to see its current status.", 409)
        views = self.dose_views(scope, [updated], now)
        if not views:
            raise DoseRuleError("Dose not found.", 404)
        return views[0]

    # ---- adherence -------------------------------------------------------------------------

    def adherence(self, scope: Scope, now: datetime, medication_id: ObjectId | None = None) -> AdherenceSummary:
        self.ensure_schedule(scope, now)
        return self._adherence_summary(scope, now, medication_id)

    def overview(self, scope: Scope, now: datetime) -> tuple[str, list[DoseOut], AdherenceSummary, list[dict]]:
        """Today's doses, adherence and all medications in one pass: the medications are read once
        and reused for schedule top-up and dose labels, instead of three separate requests."""
        meds = self.meds.list_for_user(scope.owner_id)
        self.ensure_schedule(scope, now, [m for m in meds if m["status"] == "active"])
        day = scope.today(now).isoformat()
        doses = self.dose_views(scope, self.doses.for_day(scope.owner_id, day), now, meds={m["_id"]: m for m in meds})
        return day, doses, self._adherence_summary(scope, now, None), meds

    def _adherence_summary(self, scope: Scope, now: datetime, medication_id: ObjectId | None) -> AdherenceSummary:
        today = scope.today(now)
        dates = [(today - timedelta(days=i)).isoformat() for i in range(WEEK_DAYS - 1, -1, -1)]
        counts = self.doses.counts_by_day(scope.owner_id, dates, now, medication_id)
        days = [AdherenceDay(**period(d, d, [counts.get(d, {})])) for d in dates]
        return AdherenceSummary(
            timezone=scope.timezone_name,
            today=AdherencePeriod(**period(dates[-1], dates[-1], [counts.get(dates[-1], {})])),
            week=AdherencePeriod(**period(dates[0], dates[-1], [counts.get(d, {}) for d in dates])),
            days=days,
        )


def adherence_percent(taken: int, eligible: int) -> float | None:
    """taken / eligible x 100, or None when nothing was due (never divides by zero)."""
    if eligible <= 0:
        return None
    return round(taken / eligible * 100, 1)


def period(start: str, end: str, day_counts: list[dict[str, int]]) -> dict:
    taken = sum(c.get("taken", 0) for c in day_counts)
    missed = sum(c.get("missed", 0) for c in day_counts)
    pending = sum(c.get("pending", 0) for c in day_counts)
    total = taken + missed + pending
    return {
        "start_date": start,
        "end_date": end,
        "total": total,
        "taken": taken,
        "missed": missed,
        "pending": pending,
        "adherence_percent": adherence_percent(taken, total),
    }
