import re
from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128  # bounds hashing cost / prevents oversized-input abuse


class Role(str, Enum):
    ELDERLY = "elderly"
    CARETAKER = "caretaker"
    FAMILY_MEMBER = "family_member"


ROLE_LABELS = {
    Role.ELDERLY.value: "Elderly individual",
    Role.CARETAKER.value: "Caretaker",
    Role.FAMILY_MEMBER.value: "Family member",
}


def normalize_email(value: str) -> str:
    # EmailStr already validates syntax and lower-cases the domain; lower-casing the
    # local part as well makes uniqueness case-insensitive (Jane@X.com == jane@x.com).
    return value.strip().lower()


NormalizedEmail = Annotated[EmailStr, AfterValidator(normalize_email)]

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    email: NormalizedEmail
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    role: Role

    @field_validator("name")
    @classmethod
    def _name_has_letters(cls, value: str) -> str:
        if not re.search(r"[^\W\d_]", value):
            raise ValueError("Name must contain at least one letter.")
        return re.sub(r"\s+", " ", value)

    @field_validator("password")
    @classmethod
    def _password_strength(cls, value: str) -> str:
        missing = []
        if not re.search(r"[a-z]", value):
            missing.append("a lowercase letter")
        if not re.search(r"[A-Z]", value):
            missing.append("an uppercase letter")
        if not re.search(r"\d", value):
            missing.append("a number")
        if missing:
            raise ValueError("Password must include " + ", ".join(missing) + ".")
        if value.strip() != value:
            raise ValueError("Password must not start or end with whitespace.")
        return value


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: NormalizedEmail
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class UserPublic(BaseModel):
    """User fields safe to return to clients. Never includes the password hash."""

    id: str
    name: str
    email: str
    role: Role
    is_demo: bool = False
    created_at: datetime

    @classmethod
    def from_document(cls, doc: dict) -> "UserPublic":
        return cls(
            id=str(doc["_id"]),
            name=doc["name"],
            email=doc["email"],
            role=doc["role"],
            is_demo=bool(doc.get("is_demo", False)),
            created_at=doc["created_at"],
        )


class DemoAccountInfo(BaseModel):
    """Public demo credentials shown on the login page (sample data only)."""

    role: Role
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic
