import re
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.schemas.profile import blank_to_none


class Frequency(str, Enum):
    ONCE_DAILY = "once_daily"
    TWICE_DAILY = "twice_daily"
    THREE_TIMES_DAILY = "three_times_daily"
    FOUR_TIMES_DAILY = "four_times_daily"


DOSES_PER_DAY = {
    Frequency.ONCE_DAILY: 1,
    Frequency.TWICE_DAILY: 2,
    Frequency.THREE_TIMES_DAILY: 3,
    Frequency.FOUR_TIMES_DAILY: 4,
}

TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
MAX_SCHEDULE_DAYS = 3650  # a single course may not exceed ~10 years

MedicationStatus = Literal["active", "discontinued"]
DoseStatus = Literal["pending", "taken", "missed", "cancelled"]

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
OptionalText500 = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None, BeforeValidator(blank_to_none)
]
OptionalText100 = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None, BeforeValidator(blank_to_none)
]


class MedicationIn(BaseModel):
    """Create/update body. Ownership comes from the verified token, never from the body."""

    model_config = ConfigDict(extra="forbid")

    name: ShortText
    dosage: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    frequency: Frequency
    times: list[str] = Field(min_length=1, max_length=4)
    start_date: date
    end_date: Annotated[date | None, BeforeValidator(blank_to_none)] = None
    instructions: OptionalText500 = None
    prescribing_doctor: OptionalText100 = None

    @field_validator("name")
    @classmethod
    def _name_has_letter(cls, value: str) -> str:
        if not re.search(r"[^\W\d_]", value):
            raise ValueError("Medication name must contain at least one letter.")
        return re.sub(r"\s+", " ", value)

    @field_validator("times")
    @classmethod
    def _valid_times(cls, value: list[str]) -> list[str]:
        cleaned = [t.strip() for t in value]
        for t in cleaned:
            if not TIME_PATTERN.match(t):
                raise ValueError("Times must use the 24-hour HH:MM format, for example 08:00.")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("Each scheduled time must be different.")
        return sorted(cleaned)

    @field_validator("start_date")
    @classmethod
    def _plausible_start(cls, value: date) -> date:
        today = datetime.now(timezone.utc).date()
        if value.year < 2000:
            raise ValueError("Enter a start date after the year 2000.")
        if value > today + timedelta(days=366):
            raise ValueError("The start date must be within the next year.")
        return value

    @model_validator(mode="after")
    def _consistent(self) -> "MedicationIn":
        expected = DOSES_PER_DAY[self.frequency]
        if len(self.times) != expected:
            raise ValueError(f"This frequency needs exactly {expected} scheduled time{'s' if expected > 1 else ''}.")
        if self.end_date is not None:
            if self.end_date < self.start_date:
                raise ValueError("The end date cannot be before the start date.")
            if (self.end_date - self.start_date).days > MAX_SCHEDULE_DAYS:
                raise ValueError("A course of medication cannot be longer than 10 years.")
        return self

    def to_document(self) -> dict:
        data = self.model_dump()
        data["frequency"] = self.frequency.value
        # Calendar dates are stored as ISO strings: they have no time zone.
        data["start_date"] = self.start_date.isoformat()
        data["end_date"] = self.end_date.isoformat() if self.end_date else None
        return data


SCHEDULE_FIELDS = ("frequency", "times", "start_date", "end_date")


class MedicationOut(BaseModel):
    id: str
    name: str
    dosage: str
    frequency: Frequency
    times: list[str]
    start_date: date
    end_date: date | None = None
    instructions: str | None = None
    prescribing_doctor: str | None = None
    status: MedicationStatus
    discontinued_at: datetime | None = None
    is_demo: bool = False  # demo sample data, labelled as such in the UI
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_document(cls, doc: dict) -> "MedicationOut":
        fields = {k: doc.get(k) for k in cls.model_fields if k != "id"}
        fields["is_demo"] = bool(doc.get("is_demo"))
        return cls(id=str(doc["_id"]), **fields)


class DoseOut(BaseModel):
    id: str
    medication_id: str
    medication_name: str
    dosage: str
    scheduled_at: datetime  # UTC
    local_date: str  # in the elderly user's time zone
    local_time: str
    status: DoseStatus
    status_changed_at: datetime | None = None
    taken_at: datetime | None = None
    is_due: bool = False  # scheduled time has passed
    can_mark_taken: bool = False
    can_mark_missed: bool = False


class DoseStatusUpdate(BaseModel):
    """`expected_status` is the status the client saw; the update only applies if it still
    matches, which makes double-submits and stale screens harmless."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["taken", "missed"]
    expected_status: Literal["pending", "taken", "missed"]


class TodaySchedule(BaseModel):
    date: str
    timezone: str
    doses: list[DoseOut]


class AdherencePeriod(BaseModel):
    start_date: str
    end_date: str
    total: int  # eligible doses: scheduled time has passed and not cancelled
    taken: int
    missed: int
    pending: int  # eligible but not yet recorded
    adherence_percent: float | None  # None when there were no eligible doses


class AdherenceDay(AdherencePeriod):
    pass


class AdherenceSummary(BaseModel):
    timezone: str
    today: AdherencePeriod
    week: AdherencePeriod
    days: list[AdherenceDay]
