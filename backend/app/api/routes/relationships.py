"""Relationship management.

- /relationships: the elderly owner lists and revokes their connections.
- /linked-profiles: caretakers/family members see only profiles they hold an ACTIVE
  relationship with. Access is re-checked on every request, so revocation is immediate.
"""


from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.core.time import utc_now
from app.api.deps import get_profile_repository, get_relationship_repository, get_user_repository, require_roles
from app.db.ids import to_object_id
from app.repositories.profiles import ProfileRepository
from app.repositories.relationships import RelationshipRepository
from app.repositories.users import UserRepository
from app.schemas.linking import ConnectionOut, LinkedProfileDetail, LinkedProfileSummary, MemberOut
from app.schemas.profile import ProfileOut
from app.schemas.user import Role, UserPublic

router = APIRouter(tags=["relationships"])

elderly_user = require_roles(Role.ELDERLY)
member_user = require_roles(Role.CARETAKER, Role.FAMILY_MEMBER)
PROFILE_NOT_FOUND = "Profile not found or you no longer have access to it."


@router.get("/relationships", response_model=list[ConnectionOut])
def list_connections(
    user: UserPublic = Depends(elderly_user),
    relationships: RelationshipRepository = Depends(get_relationship_repository),
    users: UserRepository = Depends(get_user_repository),
) -> list[ConnectionOut]:
    rels = relationships.list_active_for_elderly(to_object_id(user.id))
    members = users.get_many([r["member_user_id"] for r in rels])
    out = []
    for r in rels:
        m = members.get(r["member_user_id"])
        if m is None:  # member account deleted
            continue
        out.append(
            ConnectionOut(
                id=str(r["_id"]),
                role=r["role"],
                member=MemberOut(id=str(m["_id"]), name=m["name"], email=m["email"], role=m["role"]),
                connected_at=r["created_at"],
            )
        )
    return out


@router.delete("/relationships/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_connection(
    relationship_id: str,
    user: UserPublic = Depends(elderly_user),
    relationships: RelationshipRepository = Depends(get_relationship_repository),
) -> Response:
    oid = to_object_id(relationship_id)
    if oid is None or not relationships.revoke(oid, to_object_id(user.id), utc_now()):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Connection not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/linked-profiles", response_model=list[LinkedProfileSummary])
def list_linked_profiles(
    user: UserPublic = Depends(member_user),
    relationships: RelationshipRepository = Depends(get_relationship_repository),
    profiles: ProfileRepository = Depends(get_profile_repository),
) -> list[LinkedProfileSummary]:
    rels = relationships.list_active_for_member(to_object_id(user.id), is_demo=user.is_demo)
    found = profiles.get_many([r["profile_id"] for r in rels])
    return [
        LinkedProfileSummary(
            relationship_id=str(r["_id"]),
            profile_id=str(r["profile_id"]),
            full_name=found[r["profile_id"]]["full_name"],
            role=r["role"],
            connected_at=r["created_at"],
        )
        for r in rels
        if r["profile_id"] in found
    ]


@router.get("/linked-profiles/{profile_id}", response_model=LinkedProfileDetail)
def get_linked_profile(
    profile_id: str,
    user: UserPublic = Depends(member_user),
    relationships: RelationshipRepository = Depends(get_relationship_repository),
    profiles: ProfileRepository = Depends(get_profile_repository),
) -> LinkedProfileDetail:
    pid = to_object_id(profile_id)
    rel = pid and relationships.get_active_for_member(pid, to_object_id(user.id), is_demo=user.is_demo)
    profile = profiles.get_by_id(pid) if rel else None
    # Same 404 whether the profile is missing or not authorized: no existence oracle.
    if not rel or profile is None or bool(profile.get("is_demo")) != user.is_demo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, PROFILE_NOT_FOUND)
    return LinkedProfileDetail(
        relationship_id=str(rel["_id"]),
        role=rel["role"],
        connected_at=rel["created_at"],
        profile=ProfileOut.from_document(profile),
    )
