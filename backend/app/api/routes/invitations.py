from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import (
    get_failure_repository,
    get_invitation_repository,
    get_profile_repository,
    get_relationship_repository,
    require_roles,
)
from app.core.config import Settings, get_settings
from app.core.time import utc_now
from app.db.ids import to_object_id
from app.repositories.invitations import InvitationRepository, RedemptionFailureRepository
from app.repositories.profiles import ProfileRepository
from app.repositories.relationships import RelationshipRepository
from app.schemas.linking import (
    InvitationCreate,
    InvitationCreated,
    InvitationOut,
    LinkedProfileSummary,
    RedeemRequest,
    RedeemResult,
)
from app.schemas.user import Role, UserPublic
from app.services.invitation_codes import generate_code, hash_code, normalize_code
from app.services.linking import RedeemContext, redeem_invitation

router = APIRouter(prefix="/invitations", tags=["invitations"])

elderly_user = require_roles(Role.ELDERLY)
member_user = require_roles(Role.CARETAKER, Role.FAMILY_MEMBER)


@router.post("", response_model=InvitationCreated, status_code=status.HTTP_201_CREATED)
def create_invitation(
    body: InvitationCreate,
    user: UserPublic = Depends(elderly_user),
    settings: Settings = Depends(get_settings),
    profiles: ProfileRepository = Depends(get_profile_repository),
    invitations: InvitationRepository = Depends(get_invitation_repository),
) -> InvitationCreated:
    user_id = user.oid
    profile = profiles.get_by_user(user_id)
    if profile is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Please create your profile before inviting people.")

    now = utc_now()
    if invitations.count_open(user_id, now) >= settings.invitation_max_pending:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"You already have {settings.invitation_max_pending} open invitations. Cancel one before creating another.",
        )

    code = generate_code()
    hours = body.expires_in_hours or settings.invitation_expiry_hours
    doc = invitations.create(
        code_hash=hash_code(normalize_code(code)),
        profile_id=profile["_id"],
        elderly_user_id=user_id,
        role=body.role,
        expires_at=now + timedelta(hours=hours),
        now=now,
        is_demo=user.is_demo,
    )
    # The plaintext code is returned exactly once and never stored.
    return InvitationCreated(**InvitationOut.from_document(doc, now).model_dump(), code=code)


@router.get("", response_model=list[InvitationOut])
def list_invitations(
    user: UserPublic = Depends(elderly_user),
    invitations: InvitationRepository = Depends(get_invitation_repository),
) -> list[InvitationOut]:
    now = utc_now()
    return [InvitationOut.from_document(d, now) for d in invitations.list_for_owner(user.oid)]


@router.delete("/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_invitation(
    invitation_id: str,
    user: UserPublic = Depends(elderly_user),
    invitations: InvitationRepository = Depends(get_invitation_repository),
) -> Response:
    oid = to_object_id(invitation_id)
    if oid is None or not invitations.revoke(oid, user.oid):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No open invitation found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/redeem", response_model=RedeemResult, status_code=status.HTTP_201_CREATED)
def redeem(
    body: RedeemRequest,
    user: UserPublic = Depends(member_user),
    settings: Settings = Depends(get_settings),
    invitations: InvitationRepository = Depends(get_invitation_repository),
    failures: RedemptionFailureRepository = Depends(get_failure_repository),
    relationships: RelationshipRepository = Depends(get_relationship_repository),
    profiles: ProfileRepository = Depends(get_profile_repository),
) -> RedeemResult:
    ctx = RedeemContext(invitations, failures, relationships, profiles, settings)
    rel, profile = redeem_invitation(body.code, user, ctx, utc_now())
    return RedeemResult(
        message=f"You are now connected to {profile['full_name']}.",
        linked=LinkedProfileSummary(
            relationship_id=str(rel["_id"]),
            profile_id=str(profile["_id"]),
            full_name=profile["full_name"],
            role=rel["role"],
            connected_at=rel["created_at"],
        ),
    )
