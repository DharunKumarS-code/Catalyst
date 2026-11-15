from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.profile import ProfileOut
from app.schemas.user import Role

InvitableRole = Literal["caretaker", "family_member"]
InvitationStatus = Literal["pending", "redeemed", "revoked", "locked", "expired"]


class InvitationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: InvitableRole
    expires_in_hours: int | None = Field(default=None, ge=1, le=336)


class InvitationOut(BaseModel):
    """Never includes the code hash. `code` is only present in the creation response."""

    id: str
    role: InvitableRole
    status: InvitationStatus
    expires_at: datetime
    created_at: datetime
    redeemed_at: datetime | None = None

    @classmethod
    def from_document(cls, doc: dict, now: datetime) -> "InvitationOut":
        status = doc["status"]
        if status == "pending" and doc["expires_at"] <= now:
            status = "expired"
        return cls(
            id=str(doc["_id"]),
            role=doc["role"],
            status=status,
            expires_at=doc["expires_at"],
            created_at=doc["created_at"],
            redeemed_at=doc.get("redeemed_at"),
        )


class InvitationCreated(InvitationOut):
    code: str


class RedeemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=64)


class MemberOut(BaseModel):
    id: str
    name: str
    email: str
    role: Role


class ConnectionOut(BaseModel):
    """A relationship as seen by the elderly owner."""

    id: str
    role: Role
    member: MemberOut
    connected_at: datetime
    can_record_doses: bool = False  # caretakers only, granted by the elderly owner


class DosePermissionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_record_doses: bool


class LinkedProfileSummary(BaseModel):
    """A relationship as seen by a caretaker/family member."""

    relationship_id: str
    profile_id: str
    full_name: str
    role: Role  # the viewer's role in this relationship
    connected_at: datetime
    can_record_doses: bool = False


class LinkedProfileDetail(BaseModel):
    relationship_id: str
    role: Role
    connected_at: datetime
    can_record_doses: bool = False
    profile: ProfileOut


class RedeemResult(BaseModel):
    message: str
    linked: LinkedProfileSummary
