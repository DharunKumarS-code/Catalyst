"""Appointment management.

Owner routes (elderly user):  /appointments ...
Member routes (read-only):    /linked-profiles/{profile_id}/appointments ...
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_appointment_repository
from app.api.medication_access import member_scope, owner_scope
from app.core.time import utc_now
from app.db.ids import to_object_id
from app.repositories.appointments import AppointmentRepository, DuplicateAppointmentError
from app.schemas.appointment import AppointmentIn, AppointmentOut
from app.services.appointments import AppointmentRuleError, AppointmentService
from app.services.medications import Scope

router = APIRouter(tags=["appointments"])

NOT_FOUND = "Appointment not found."
DUPLICATE = "You already have an appointment with this doctor at this date and time."
View = Literal["upcoming", "history"]


def get_service(repo: AppointmentRepository = Depends(get_appointment_repository)) -> AppointmentService:
    return AppointmentService(repo)


def _oid(appointment_id: str):
    oid = to_object_id(appointment_id)
    if oid is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return oid


def _http(exc: AppointmentRuleError) -> HTTPException:
    if exc.field:  # same shape as validation errors, so the form can show it next to the field
        return HTTPException(exc.status_code, [{"loc": ["body", exc.field], "msg": str(exc), "type": "value_error"}])
    return HTTPException(exc.status_code, str(exc))


def _list(scope: Scope, service: AppointmentService, view: View, limit: int) -> list[AppointmentOut]:
    now = utc_now()
    docs = (service.repo.upcoming if view == "upcoming" else service.repo.history)(scope.owner_id, now, limit)
    return [service.view(scope, d, now) for d in docs]


def _get(scope: Scope, service: AppointmentService, appointment_id: str) -> AppointmentOut:
    doc = service.repo.get(_oid(appointment_id), scope.owner_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return service.view(scope, doc, utc_now())


ViewQuery = Query("upcoming", description="upcoming: scheduled and still ahead; history: everything else.")
LimitQuery = Query(100, ge=1, le=500)


# ---- owner -------------------------------------------------------------------------------


@router.get("/appointments", response_model=list[AppointmentOut])
def list_appointments(
    view: View = ViewQuery,
    limit: int = LimitQuery,
    scope: Scope = Depends(owner_scope),
    service: AppointmentService = Depends(get_service),
):
    return _list(scope, service, view, limit)


@router.post("/appointments", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
def create_appointment(
    body: AppointmentIn, scope: Scope = Depends(owner_scope), service: AppointmentService = Depends(get_service)
):
    now = utc_now()
    try:
        doc = service.create(scope, body, now)
    except AppointmentRuleError as exc:
        raise _http(exc) from None
    except DuplicateAppointmentError:
        raise HTTPException(status.HTTP_409_CONFLICT, DUPLICATE) from None
    return service.view(scope, doc, now)


@router.get("/appointments/{appointment_id}", response_model=AppointmentOut)
def get_appointment(
    appointment_id: str, scope: Scope = Depends(owner_scope), service: AppointmentService = Depends(get_service)
):
    return _get(scope, service, appointment_id)


@router.put("/appointments/{appointment_id}", response_model=AppointmentOut)
def update_appointment(
    appointment_id: str,
    body: AppointmentIn,
    scope: Scope = Depends(owner_scope),
    service: AppointmentService = Depends(get_service),
):
    now = utc_now()
    try:
        doc = service.update(scope, _oid(appointment_id), body, now)
    except AppointmentRuleError as exc:
        raise _http(exc) from None
    except DuplicateAppointmentError:
        raise HTTPException(status.HTTP_409_CONFLICT, DUPLICATE) from None
    return service.view(scope, doc, now)


@router.post("/appointments/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel_appointment(
    appointment_id: str, scope: Scope = Depends(owner_scope), service: AppointmentService = Depends(get_service)
):
    now = utc_now()
    try:
        return service.view(scope, service.cancel(scope, _oid(appointment_id), now), now)
    except AppointmentRuleError as exc:
        raise _http(exc) from None


@router.post("/appointments/{appointment_id}/complete", response_model=AppointmentOut)
def complete_appointment(
    appointment_id: str, scope: Scope = Depends(owner_scope), service: AppointmentService = Depends(get_service)
):
    now = utc_now()
    try:
        return service.view(scope, service.complete(scope, _oid(appointment_id), now), now)
    except AppointmentRuleError as exc:
        raise _http(exc) from None


# ---- members: read-only --------------------------------------------------------------------


@router.get("/linked-profiles/{profile_id}/appointments", response_model=list[AppointmentOut])
def linked_appointments(
    view: View = ViewQuery,
    limit: int = LimitQuery,
    scope: Scope = Depends(member_scope),
    service: AppointmentService = Depends(get_service),
):
    return _list(scope, service, view, limit)


@router.get("/linked-profiles/{profile_id}/appointments/{appointment_id}", response_model=AppointmentOut)
def linked_appointment(
    appointment_id: str, scope: Scope = Depends(member_scope), service: AppointmentService = Depends(get_service)
):
    return _get(scope, service, appointment_id)
