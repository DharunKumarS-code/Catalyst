"""Appointment rules shared by the owner and member routes."""

from datetime import date, datetime

from bson import ObjectId

from app.repositories.appointments import AppointmentRepository
from app.schemas.appointment import AppointmentIn, AppointmentOut
from app.services.medications import Scope
from app.services.scheduling import to_utc


class AppointmentRuleError(Exception):
    """`field` (when set) is the body field the message belongs to, for inline form errors."""

    def __init__(self, message: str, status_code: int, field: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.field = field


def resolve_instant(day: date, hhmm: str, scope: Scope) -> datetime:
    """Local wall-clock time in the profile's zone -> UTC. Times skipped by a daylight-saving
    jump do not exist, so they are rejected rather than silently moved."""
    at = to_utc(day, hhmm, scope.tz)
    local = at.astimezone(scope.tz)
    if (local.date(), local.strftime("%H:%M")) != (day, hhmm):
        raise AppointmentRuleError(
            "This time does not exist on that day in your time zone (the clocks change). Choose another time.",
            422,
            "appointment_time",
        )
    return at


class AppointmentService:
    def __init__(self, repo: AppointmentRepository) -> None:
        self.repo = repo

    def view(self, scope: Scope, doc: dict, now: datetime) -> AppointmentOut:
        scheduled = doc["status"] == "scheduled"
        is_past = doc["scheduled_at"] <= now
        return AppointmentOut(
            id=str(doc["_id"]),
            **{k: doc.get(k) for k in AppointmentOut.model_fields if k in doc and k not in ("id", "is_demo")},
            is_past=is_past,
            is_demo=bool(doc.get("is_demo")),
            can_edit=scope.can_modify and scheduled and not is_past,
            can_cancel=scope.can_modify and scheduled,
            can_complete=scope.can_modify and scheduled and is_past,
        )

    def _timing(self, body: AppointmentIn, scope: Scope, now: datetime) -> dict:
        at = resolve_instant(body.appointment_date, body.appointment_time, scope)
        if at <= now:
            raise AppointmentRuleError("Choose a date and time in the future.", 422, "appointment_date")
        return {
            "appointment_date": body.appointment_date.isoformat(),
            "appointment_time": body.appointment_time,
            "timezone": scope.timezone_name,
            "scheduled_at": at,
        }

    def create(self, scope: Scope, body: AppointmentIn, now: datetime) -> dict:
        doc = {
            **body.fields(),
            **self._timing(body, scope, now),
            "user_id": scope.owner_id,
            "profile_id": scope.profile["_id"],
            "is_demo": bool(scope.profile.get("is_demo")),
            "status": "scheduled",
            "status_changed_at": None,
            "history": [],
            "created_at": now,
            "updated_at": now,
        }
        return self.repo.create(doc)

    def update(self, scope: Scope, appointment_id: ObjectId, body: AppointmentIn, now: datetime) -> dict:
        current = self._get(scope, appointment_id)
        if current["status"] != "scheduled":
            raise AppointmentRuleError(f"A {current['status']} appointment cannot be edited.", 409)
        if current["scheduled_at"] <= now:
            raise AppointmentRuleError("This appointment has already happened. Mark it completed or cancelled.", 409)
        changes = {**body.fields(), **self._timing(body, scope, now), "updated_at": now}
        updated = self.repo.update_scheduled(appointment_id, scope.owner_id, changes)
        if updated is None:
            raise AppointmentRuleError("This appointment changed. Refresh and try again.", 409)
        return updated

    def cancel(self, scope: Scope, appointment_id: ObjectId, now: datetime) -> dict:
        updated = self.repo.transition(appointment_id, scope.owner_id, new="cancelled", now=now)
        if updated is None:
            current = self._get(scope, appointment_id)
            raise AppointmentRuleError(f"This appointment is already {current['status']}.", 409)
        return updated

    def complete(self, scope: Scope, appointment_id: ObjectId, now: datetime) -> dict:
        updated = self.repo.transition(
            appointment_id, scope.owner_id, new="completed", now=now, extra={"scheduled_at": {"$lte": now}}
        )
        if updated is None:
            current = self._get(scope, appointment_id)
            if current["status"] != "scheduled":
                raise AppointmentRuleError(f"This appointment is already {current['status']}.", 409)
            raise AppointmentRuleError("An appointment can only be marked completed after its time.", 422)
        return updated

    def _get(self, scope: Scope, appointment_id: ObjectId) -> dict:
        doc = self.repo.get(appointment_id, scope.owner_id)
        if doc is None:
            raise AppointmentRuleError("Appointment not found.", 404)
        return doc
