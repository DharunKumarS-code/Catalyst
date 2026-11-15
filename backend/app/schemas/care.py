from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.appointment import AppointmentOut
from app.schemas.medication import AdherencePeriod, DoseOut

ActivityKind = Literal["dose_taken", "dose_missed", "appointment_completed", "appointment_cancelled"]


class ActivityItem(BaseModel):
    """A real recorded event: a dose status the elderly user recorded, or an appointment they
    marked completed/cancelled. Nothing here is inferred or generated."""

    kind: ActivityKind
    at: datetime  # when it was recorded (UTC)
    subject: str  # medication name + dosage, or doctor name
    local_date: str
    local_time: str
    place: str | None = None


class CareProfileSummary(BaseModel):
    profile_id: str
    relationship_id: str
    role: str  # how the viewer is connected: caretaker / family_member
    connected_at: datetime
    can_record_doses: bool = False  # the viewer may record doses for this person
    full_name: str
    date_of_birth: date | None = None
    phone: str | None = None
    emergency_contact_name: str
    emergency_contact_phone: str
    timezone: str
    local_date: str  # "today" in the elderly person's time zone
    is_demo: bool = False
    active_medications: int
    today: AdherencePeriod  # same rule as GET /api/adherence
    today_doses: list[DoseOut]
    next_dose: DoseOut | None = None
    upcoming_appointments: list[AppointmentOut]
    upcoming_appointment_count: int
    recent_activity: list[ActivityItem]


class CareDashboard(BaseModel):
    generated_at: datetime
    profiles: list[CareProfileSummary]
