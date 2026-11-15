"""Medication management, dose tracking and adherence.

Owner routes (elderly user):      /medications, /doses/*, /adherence
Member routes (read-only):        /linked-profiles/{profile_id}/medications, .../doses/*, .../adherence
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.medication_access import get_medication_service, member_scope, owner_scope
from app.core.time import utc_now
from app.db.ids import to_object_id
from app.schemas.medication import (
    AdherenceSummary,
    DoseOut,
    DoseStatusUpdate,
    MedicationIn,
    MedicationOut,
    MedicationOverview,
    TodaySchedule,
)
from app.services.medications import DoseRuleError, MedicationService, Scope

router = APIRouter(tags=["medications"])

MED_NOT_FOUND = "Medication not found."
StatusFilter = Literal["active", "discontinued"] | None


def _med_id(medication_id: str):
    oid = to_object_id(medication_id)
    if oid is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, MED_NOT_FOUND)
    return oid


def _optional_med_id(medication_id: str | None):
    return None if medication_id is None else _med_id(medication_id)


# ---- shared read handlers (owner and member) ------------------------------------------------


def _list(scope: Scope, service: MedicationService, status_filter: StatusFilter) -> list[MedicationOut]:
    return [MedicationOut.from_document(m) for m in service.meds.list_for_user(scope.owner_id, status=status_filter)]


def _get(scope: Scope, service: MedicationService, medication_id: str) -> MedicationOut:
    med = service.meds.get(_med_id(medication_id), scope.owner_id)
    if med is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, MED_NOT_FOUND)
    return MedicationOut.from_document(med)


def _today(scope: Scope, service: MedicationService) -> TodaySchedule:
    day, doses = service.today(scope, utc_now())
    return TodaySchedule(date=day, timezone=scope.timezone_name, doses=doses)


def _overview(scope: Scope, service: MedicationService) -> MedicationOverview:
    day, doses, adherence, meds = service.overview(scope, utc_now())
    return MedicationOverview(
        today=TodaySchedule(date=day, timezone=scope.timezone_name, doses=doses),
        adherence=adherence,
        medications=[MedicationOut.from_document(m) for m in meds],
    )


def _history(scope: Scope, service: MedicationService, days: int, medication_id: str | None, limit: int):
    return service.history(scope, utc_now(), days=days, medication_id=_optional_med_id(medication_id), limit=limit)


HistoryDays = Query(7, ge=1, le=90, description="Number of local days to include, ending today.")
HistoryLimit = Query(200, ge=1, le=500)


# ---- owner: medications --------------------------------------------------------------------


@router.get("/medications", response_model=list[MedicationOut])
def list_medications(
    status_filter: StatusFilter = Query(None, alias="status"),
    scope: Scope = Depends(owner_scope),
    service: MedicationService = Depends(get_medication_service),
):
    return _list(scope, service, status_filter)


@router.post("/medications", response_model=MedicationOut, status_code=status.HTTP_201_CREATED)
def create_medication(
    body: MedicationIn,
    scope: Scope = Depends(owner_scope),
    service: MedicationService = Depends(get_medication_service),
):
    return MedicationOut.from_document(service.create(scope, body.to_document(), utc_now()))


# Declared before /medications/{medication_id} so "overview" is not taken as an id.
@router.get("/medications/overview", response_model=MedicationOverview)
def medication_overview(
    scope: Scope = Depends(owner_scope), service: MedicationService = Depends(get_medication_service)
):
    """Today's doses, adherence and medications in one request (the three separate endpoints remain)."""
    return _overview(scope, service)


@router.get("/medications/{medication_id}", response_model=MedicationOut)
def get_medication(
    medication_id: str,
    scope: Scope = Depends(owner_scope),
    service: MedicationService = Depends(get_medication_service),
):
    return _get(scope, service, medication_id)


@router.put("/medications/{medication_id}", response_model=MedicationOut)
def update_medication(
    medication_id: str,
    body: MedicationIn,
    scope: Scope = Depends(owner_scope),
    service: MedicationService = Depends(get_medication_service),
):
    med = service.meds.get(_med_id(medication_id), scope.owner_id)
    if med is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, MED_NOT_FOUND)
    if med["status"] != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "A discontinued medication cannot be edited.")
    updated = service.update(scope, med, body.to_document(), utc_now())
    if updated is None:  # discontinued or deleted concurrently
        raise HTTPException(status.HTTP_409_CONFLICT, "This medication changed. Refresh and try again.")
    return MedicationOut.from_document(updated)


@router.post("/medications/{medication_id}/discontinue", response_model=MedicationOut)
def discontinue_medication(
    medication_id: str,
    scope: Scope = Depends(owner_scope),
    service: MedicationService = Depends(get_medication_service),
):
    oid = _med_id(medication_id)
    med = service.discontinue(scope, oid, utc_now())
    if med is None:
        if service.meds.get(oid, scope.owner_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, MED_NOT_FOUND)
        raise HTTPException(status.HTTP_409_CONFLICT, "This medication is already discontinued.")
    return MedicationOut.from_document(med)


@router.delete("/medications/{medication_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_medication(
    medication_id: str,
    scope: Scope = Depends(owner_scope),
    service: MedicationService = Depends(get_medication_service),
) -> Response:
    if not service.delete(scope, _med_id(medication_id)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, MED_NOT_FOUND)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- owner: doses and adherence ------------------------------------------------------------


@router.get("/doses/today", response_model=TodaySchedule)
def today_schedule(scope: Scope = Depends(owner_scope), service: MedicationService = Depends(get_medication_service)):
    return _today(scope, service)


@router.get("/doses/history", response_model=list[DoseOut])
def dose_history(
    days: int = HistoryDays,
    medication_id: str | None = None,
    limit: int = HistoryLimit,
    scope: Scope = Depends(owner_scope),
    service: MedicationService = Depends(get_medication_service),
):
    return _history(scope, service, days, medication_id, limit)


@router.patch("/doses/{dose_id}/status", response_model=DoseOut)
def update_dose_status(
    dose_id: str,
    body: DoseStatusUpdate,
    scope: Scope = Depends(owner_scope),
    service: MedicationService = Depends(get_medication_service),
):
    oid = to_object_id(dose_id)
    if oid is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dose not found.")
    try:
        return service.set_status(scope, oid, new=body.status, expected=body.expected_status, now=utc_now())
    except DoseRuleError as exc:
        raise HTTPException(exc.status_code, str(exc)) from None


@router.get("/adherence", response_model=AdherenceSummary)
def adherence(
    medication_id: str | None = None,
    scope: Scope = Depends(owner_scope),
    service: MedicationService = Depends(get_medication_service),
):
    return service.adherence(scope, utc_now(), _optional_med_id(medication_id))


# ---- members: views of a linked profile (read-only, except doses a caretaker is allowed to record) ----

LINKED = "/linked-profiles/{profile_id}"


@router.get(LINKED + "/medications", response_model=list[MedicationOut])
def linked_medications(
    status_filter: StatusFilter = Query(None, alias="status"),
    scope: Scope = Depends(member_scope),
    service: MedicationService = Depends(get_medication_service),
):
    return _list(scope, service, status_filter)


@router.get(LINKED + "/medications/overview", response_model=MedicationOverview)
def linked_medication_overview(
    scope: Scope = Depends(member_scope), service: MedicationService = Depends(get_medication_service)
):
    return _overview(scope, service)


@router.get(LINKED + "/medications/{medication_id}", response_model=MedicationOut)
def linked_medication(
    medication_id: str,
    scope: Scope = Depends(member_scope),
    service: MedicationService = Depends(get_medication_service),
):
    return _get(scope, service, medication_id)


@router.get(LINKED + "/doses/today", response_model=TodaySchedule)
def linked_today(scope: Scope = Depends(member_scope), service: MedicationService = Depends(get_medication_service)):
    return _today(scope, service)


@router.get(LINKED + "/doses/history", response_model=list[DoseOut])
def linked_history(
    days: int = HistoryDays,
    medication_id: str | None = None,
    limit: int = HistoryLimit,
    scope: Scope = Depends(member_scope),
    service: MedicationService = Depends(get_medication_service),
):
    return _history(scope, service, days, medication_id, limit)


@router.get(LINKED + "/adherence", response_model=AdherenceSummary)
def linked_adherence(
    medication_id: str | None = None,
    scope: Scope = Depends(member_scope),
    service: MedicationService = Depends(get_medication_service),
):
    return service.adherence(scope, utc_now(), _optional_med_id(medication_id))


@router.patch(LINKED + "/doses/{dose_id}/status", response_model=DoseOut)
def linked_update_dose_status(
    dose_id: str,
    body: DoseStatusUpdate,
    scope: Scope = Depends(member_scope),
    service: MedicationService = Depends(get_medication_service),
):
    """A caretaker records a dose they gave. Allowed only while the elderly owner's grant is set
    on the active relationship (403 otherwise); the change is attributed to the caretaker."""
    return update_dose_status(dose_id, body, scope, service)
