"""Elderly profile of the signed-in elderly user. The owner is always taken from the
verified token, so there is no way to address another user's profile here."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_profile_repository, require_roles
from app.api.medication_access import get_medication_service
from app.core.time import DEFAULT_TIMEZONE, utc_now
from app.db.ids import to_object_id
from app.repositories.profiles import ProfileAlreadyExistsError, ProfileRepository
from app.schemas.profile import ProfileIn, ProfileOut
from app.schemas.user import Role, UserPublic
from app.services.medications import MedicationService

router = APIRouter(prefix="/profiles", tags=["profiles"])

elderly_user = require_roles(Role.ELDERLY)
NOT_FOUND = "You have not created your profile yet."


@router.get("/me", response_model=ProfileOut)
def get_my_profile(
    user: UserPublic = Depends(elderly_user),
    profiles: ProfileRepository = Depends(get_profile_repository),
) -> ProfileOut:
    doc = profiles.get_by_user(to_object_id(user.id))
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return ProfileOut.from_document(doc)


@router.post("/me", response_model=ProfileOut, status_code=status.HTTP_201_CREATED)
def create_my_profile(
    body: ProfileIn,
    user: UserPublic = Depends(elderly_user),
    profiles: ProfileRepository = Depends(get_profile_repository),
) -> ProfileOut:
    try:
        doc = profiles.create(to_object_id(user.id), body.to_document(), is_demo=user.is_demo)
    except ProfileAlreadyExistsError:
        raise HTTPException(status.HTTP_409_CONFLICT, "You already have a profile. Update it instead.") from None
    return ProfileOut.from_document(doc)


@router.put("/me", response_model=ProfileOut)
def update_my_profile(
    body: ProfileIn,
    user: UserPublic = Depends(elderly_user),
    profiles: ProfileRepository = Depends(get_profile_repository),
    medications: MedicationService = Depends(get_medication_service),
) -> ProfileOut:
    owner_id = to_object_id(user.id)
    before = profiles.get_by_user(owner_id)
    doc = profiles.update(owner_id, body.to_document())
    if doc is None or before is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    if (before.get("timezone") or DEFAULT_TIMEZONE) != doc["timezone"]:
        medications.timezone_changed(owner_id, utc_now())
    return ProfileOut.from_document(doc)
