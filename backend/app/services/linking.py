"""Invitation redemption: validates a code and links a caretaker/family member to an
elderly profile.

Order of checks:
1. Per-user rate limit on failed attempts (429).
2. Code format (400, not counted: a malformed code cannot match anything).
3. Lookup by hash; unknown codes and codes from the other data partition (demo vs
   real) get the same generic message.
4. Status / expiry / role checks; a wrong-role attempt also counts against the
   invitation, which is locked after too many.
5. Existing active relationship -> 409 without consuming the invitation.
6. Atomic consume (pending -> redeemed), then insert the relationship; the partial
   unique index makes duplicate active links impossible even under races.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import HTTPException, status

from app.core.config import Settings
from app.repositories.invitations import InvitationRepository, RedemptionFailureRepository
from app.repositories.profiles import ProfileRepository
from app.repositories.relationships import RelationshipExistsError, RelationshipRepository
from app.schemas.user import ROLE_LABELS, UserPublic
from app.services.invitation_codes import hash_code, normalize_code

MSG_INVALID = "This invitation code is not valid. Please check the code and try again."
MSG_FORMAT = "Invitation codes have 16 letters and numbers, like ABCD-EFGH-JKMN-PQRS."
MSG_USED = "This invitation has already been used. Please ask for a new invitation."
MSG_NO_LONGER_VALID = "This invitation is no longer valid. Please ask for a new invitation."
MSG_EXPIRED = "This invitation has expired. Please ask for a new invitation."
MSG_ALREADY_LINKED = "You are already connected to this person."
MSG_TOO_MANY = "Too many unsuccessful attempts. Please wait {minutes} minutes and try again."


@dataclass
class RedeemContext:
    invitations: InvitationRepository
    failures: RedemptionFailureRepository
    relationships: RelationshipRepository
    profiles: ProfileRepository
    settings: Settings


def redeem_invitation(raw_code: str, user: UserPublic, ctx: RedeemContext, now: datetime) -> tuple[dict, dict]:
    """Returns (relationship, profile). Raises HTTPException with a user-facing message."""
    user_id = user.oid
    window = timedelta(minutes=ctx.settings.redeem_failure_window_minutes)

    if ctx.failures.count_recent(user_id, now, window) >= ctx.settings.redeem_max_failures:
        oldest = ctx.failures.oldest_recent(user_id, now, window) or now
        retry_after = max(1, int((oldest + window - now).total_seconds()))
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            MSG_TOO_MANY.format(minutes=max(1, -(-retry_after // 60))),
            headers={"Retry-After": str(retry_after)},
        )

    code = normalize_code(raw_code)
    if code is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, MSG_FORMAT)

    def fail(http_status: int, message: str, reason: str, invitation: dict | None = None) -> HTTPException:
        ctx.failures.record(user_id, now, reason)
        if invitation is not None:
            ctx.invitations.register_failed_attempt(invitation["_id"], ctx.settings.redeem_max_failures)
        return HTTPException(http_status, message)

    inv = ctx.invitations.get_by_hash(hash_code(code))
    # Demo and real data never mix: a cross-partition code behaves exactly like an unknown one.
    if inv is None or bool(inv.get("is_demo")) != user.is_demo:
        raise fail(status.HTTP_400_BAD_REQUEST, MSG_INVALID, "not_found")
    if inv["status"] == "redeemed":
        raise fail(status.HTTP_409_CONFLICT, MSG_USED, "used")
    if inv["status"] != "pending":  # revoked or locked
        raise fail(status.HTTP_400_BAD_REQUEST, MSG_NO_LONGER_VALID, inv["status"])
    if inv["expires_at"] <= now:
        raise fail(status.HTTP_410_GONE, MSG_EXPIRED, "expired")
    if inv["role"] != user.role.value:
        message = (
            f"This invitation is for a {ROLE_LABELS[inv['role']].lower()}, "
            f"but you are signed in as a {ROLE_LABELS[user.role.value].lower()}."
        )
        raise fail(status.HTTP_403_FORBIDDEN, message, "wrong_role", inv)

    profile = ctx.profiles.get_by_id(inv["profile_id"])
    if profile is None or bool(profile.get("is_demo")) != user.is_demo:
        raise fail(status.HTTP_400_BAD_REQUEST, MSG_NO_LONGER_VALID, "profile_missing")

    # Do not burn the invitation if the user is already linked.
    if ctx.relationships.active_exists(inv["profile_id"], user_id):
        raise HTTPException(status.HTTP_409_CONFLICT, MSG_ALREADY_LINKED)

    if ctx.invitations.consume(inv["_id"], user_id, now) is None:  # lost a race / just expired
        raise fail(status.HTTP_409_CONFLICT, MSG_USED, "race")

    try:
        relationship = ctx.relationships.create(
            profile_id=inv["profile_id"],
            elderly_user_id=inv["elderly_user_id"],
            member_user_id=user_id,
            role=inv["role"],
            invitation_id=inv["_id"],
            now=now,
            is_demo=user.is_demo,
        )
    except RelationshipExistsError:
        ctx.invitations.release(inv["_id"], user_id)
        raise HTTPException(status.HTTP_409_CONFLICT, MSG_ALREADY_LINKED) from None
    return relationship, profile
