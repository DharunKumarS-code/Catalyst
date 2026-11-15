import re
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, StringConstraints, field_validator

from app.schemas.medication import TIME_PATTERN
from app.schemas.profile import blank_to_none

AppointmentStatus = Literal["scheduled", "completed", "cancelled"]
MAX_YEARS_AHEAD = 5


# Optional trimmed strings: blank input becomes None. Explicit aliases so type checkers accept them.
Optional50 = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)] | None, BeforeValidator(blank_to_none)
]
Optional100 = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None, BeforeValidator(blank_to_none)
]
Optional300 = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None, BeforeValidator(blank_to_none)
]
Optional500 = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None, BeforeValidator(blank_to_none)
]
Optional1000 = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None, BeforeValidator(blank_to_none)
]

Required100 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Required150 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]


class AppointmentIn(BaseModel):
    """Create/update body. The owner always comes from the verified token, never from the body.
    Date and time are wall-clock values in the elderly user's profile time zone."""

    model_config = ConfigDict(extra="forbid")

    doctor_name: Required100
    specialization: Optional100 = None
    clinic_name: Required150
    clinic_address: Optional300 = None
    appointment_date: date
    appointment_time: str
    appointment_type: Optional50 = None
    reason: Optional500 = None
    notes: Optional1000 = None

    @field_validator("doctor_name", "clinic_name")
    @classmethod
    def _has_letter(cls, value: str) -> str:
        if not re.search(r"[^\W\d_]", value):
            raise ValueError("Must contain at least one letter.")
        return re.sub(r"\s+", " ", value)

    @field_validator("appointment_time")
    @classmethod
    def _valid_time(cls, value: str) -> str:
        value = value.strip()
        if not TIME_PATTERN.match(value):
            raise ValueError("Enter the time in 24-hour HH:MM format, for example 09:30.")
        return value

    @field_validator("appointment_date")
    @classmethod
    def _plausible_date(cls, value: date) -> date:
        if value.year < 2000:
            raise ValueError("Enter a date after the year 2000.")
        if value > datetime.now(UTC).date() + timedelta(days=366 * MAX_YEARS_AHEAD):
            raise ValueError(f"The appointment must be within the next {MAX_YEARS_AHEAD} years.")
        return value

    def fields(self) -> dict:
        data = self.model_dump(exclude={"appointment_date", "appointment_time"})
        data["doctor_key"] = self.doctor_name.casefold()  # case-insensitive duplicate detection
        return data


class AppointmentOut(BaseModel):
    id: str
    doctor_name: str
    specialization: str | None = None
    clinic_name: str
    clinic_address: str | None = None
    appointment_date: str  # local date in `timezone`
    appointment_time: str  # local HH:MM in `timezone`
    timezone: str
    scheduled_at: datetime  # UTC
    appointment_type: str | None = None
    reason: str | None = None
    notes: str | None = None
    status: AppointmentStatus
    status_changed_at: datetime | None = None
    is_past: bool
    is_demo: bool = False
    can_edit: bool = False
    can_cancel: bool = False
    can_complete: bool = False
    created_at: datetime
    updated_at: datetime
