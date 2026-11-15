import re
from datetime import UTC, date, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, StringConstraints, field_validator

from app.core.time import DEFAULT_TIMEZONE, is_valid_timezone
from app.schemas.user import Name

_PHONE_CHARS = re.compile(r"^\+?[0-9 ()\-.]+$")


def blank_to_none(value: object) -> object:
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _validate_phone(value: str) -> str:
    value = re.sub(r"\s+", " ", value.strip())
    digits = re.sub(r"\D", "", value)
    if not _PHONE_CHARS.match(value) or not 7 <= len(digits) <= 15:
        raise ValueError("Enter a valid phone number with 7 to 15 digits.")
    return value


Phone = Annotated[str, StringConstraints(max_length=30), AfterValidator(_validate_phone)]
OptionalPhone = Annotated[Phone | None, BeforeValidator(blank_to_none)]
Address = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None, BeforeValidator(blank_to_none)
]
Notes = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None, BeforeValidator(blank_to_none)
]


class ProfileIn(BaseModel):
    """Create/update body. The owner always comes from the verified token, never from the body."""

    model_config = ConfigDict(extra="forbid")

    full_name: Name
    date_of_birth: Annotated[date | None, BeforeValidator(blank_to_none)] = None
    phone: OptionalPhone = None
    address: Address = None
    emergency_contact_name: Name
    emergency_contact_phone: Phone
    notes: Notes = None
    # IANA zone used to schedule medication doses in the user's local time.
    timezone: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] = DEFAULT_TIMEZONE

    @field_validator("timezone")
    @classmethod
    def _valid_timezone(cls, value: str) -> str:
        if not is_valid_timezone(value):
            raise ValueError("Choose a valid time zone, for example Europe/London.")
        return value

    @field_validator("full_name", "emergency_contact_name")
    @classmethod
    def _has_letter(cls, value: str) -> str:
        if not re.search(r"[^\W\d_]", value):
            raise ValueError("Name must contain at least one letter.")
        return re.sub(r"\s+", " ", value)

    @field_validator("date_of_birth")
    @classmethod
    def _plausible_dob(cls, value: date | None) -> date | None:
        if value is None:
            return value
        if value > datetime.now(UTC).date():
            raise ValueError("Date of birth cannot be in the future.")
        if value.year < 1900:
            raise ValueError("Enter a date of birth after 1900.")
        return value

    def to_document(self) -> dict:
        data = self.model_dump()
        # Stored as ISO "YYYY-MM-DD": a calendar date has no time zone.
        data["date_of_birth"] = self.date_of_birth.isoformat() if self.date_of_birth else None
        return data


class ProfileOut(BaseModel):
    id: str
    full_name: str
    date_of_birth: date | None = None
    phone: str | None = None
    address: str | None = None
    emergency_contact_name: str
    emergency_contact_phone: str
    notes: str | None = None
    timezone: str = DEFAULT_TIMEZONE
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_document(cls, doc: dict) -> "ProfileOut":
        fields = {k: doc.get(k) for k in cls.model_fields if k != "id"}
        fields["timezone"] = doc.get("timezone") or DEFAULT_TIMEZONE  # profiles created before Phase 4
        return cls(id=str(doc["_id"]), **fields)
