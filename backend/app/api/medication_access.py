"""Authorization scopes for medication and appointment data, evaluated on every request.

- Owner scope: the signed-in elderly user, working on their own medications.
- Member scope: a caretaker/family member with an ACTIVE relationship to the profile,
  read-only. Revoking the relationship removes access on the very next request.
"""

from fastapi import Depends, HTTPException, status

from app.api.deps import (
    get_auth_settings,
    get_dose_repository,
    get_medication_repository,
    get_profile_repository,
    get_relationship_repository,
    require_roles,
)
from app.core.config import Settings
from app.db.ids import to_object_id
from app.repositories.doses import DoseRepository
from app.repositories.medications import MedicationRepository
from app.repositories.profiles import ProfileRepository
from app.repositories.relationships import RelationshipRepository
from app.schemas.user import Role, UserPublic
from app.services.medications import MedicationService, Scope, member_scope_for

elderly_user = require_roles(Role.ELDERLY)
member_user = require_roles(Role.CARETAKER, Role.FAMILY_MEMBER)

PROFILE_REQUIRED = "Create your profile before managing medications or appointments."
PROFILE_NOT_FOUND = "Profile not found or you no longer have access to it."


def get_medication_service(
    settings: Settings = Depends(get_auth_settings),
    meds: MedicationRepository = Depends(get_medication_repository),
    doses: DoseRepository = Depends(get_dose_repository),
) -> MedicationService:
    return MedicationService(
        meds,
        doses,
        horizon_days=settings.dose_schedule_horizon_days,
        early_minutes=settings.dose_early_take_minutes,
    )


def owner_scope(
    user: UserPublic = Depends(elderly_user),
    profiles: ProfileRepository = Depends(get_profile_repository),
) -> Scope:
    owner_id = user.oid
    profile = profiles.get_by_user(owner_id)
    if profile is None:
        raise HTTPException(status.HTTP_409_CONFLICT, PROFILE_REQUIRED)
    return Scope(owner_id=owner_id, profile=profile, can_modify=True, actor_id=owner_id, actor_name=user.name)


def member_scope(
    profile_id: str,
    user: UserPublic = Depends(member_user),
    relationships: RelationshipRepository = Depends(get_relationship_repository),
    profiles: ProfileRepository = Depends(get_profile_repository),
) -> Scope:
    pid = to_object_id(profile_id)
    rel = pid and relationships.get_active_for_member(pid, user.oid, is_demo=user.is_demo)
    profile = profiles.get_by_id(pid) if rel else None
    # Same 404 whether missing, never linked, revoked, or demo/real mismatch: no existence oracle.
    if not rel or profile is None or bool(profile.get("is_demo")) != user.is_demo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, PROFILE_NOT_FOUND)
    return member_scope_for(rel, profile, user.oid, user.name)
