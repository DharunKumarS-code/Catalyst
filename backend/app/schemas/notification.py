from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

NotificationKind = Literal["medication_reminder", "missed_dose", "appointment_reminder", "test"]
# pending -> sending -> sent | failed | preview (not emailed) | skipped (no longer relevant)
NotificationStatus = Literal["pending", "sending", "sent", "failed", "preview", "skipped"]


class NotificationPreferences(BaseModel):
    """Per-user settings, always keyed by the signed-in user: nobody can edit another user's.
    Caretakers/family use `email_enabled` and `missed_dose_alerts`; the timing settings are
    the elderly user's own and drive their reminders."""

    model_config = ConfigDict(extra="forbid")

    email_enabled: bool = True
    medication_reminders: bool = True
    medication_reminder_minutes: int = Field(default=15, ge=5, le=120)
    missed_dose_alerts: bool = True
    notify_caretakers_of_missed_doses: bool = True
    appointment_reminders: bool = True
    appointment_reminder_minutes: int = Field(default=1440, ge=15, le=10080)


class NotificationOut(BaseModel):
    id: str
    kind: NotificationKind
    status: NotificationStatus
    subject: str
    recipient_name: str
    recipient_role: str  # "self", "caretaker" or "family_member"
    recipient_is_you: bool
    about_name: str | None = None  # whose medicine/appointment it concerns
    related_label: str | None = None  # shown in the app only, never put in emails
    event_at: datetime | None = None
    local_date: str | None = None
    local_time: str | None = None
    timezone: str | None = None
    created_at: datetime
    sent_at: datetime | None = None
    attempts: int
    failure_reason: str | None = None
    delivery_note: str | None = None


class UnreadCount(BaseModel):
    unread: int  # capped at UNREAD_CAP; the UI shows "99+"
    seen_at: datetime | None = None  # when the history was last opened; newer items are "new"


class NotificationSystemStatus(BaseModel):
    """Safe to show anyone signed in: no hosts, usernames or secrets."""

    delivery: Literal["email", "preview"]
    smtp_configured: bool
    scheduler_running: bool
    check_interval_seconds: int
    missed_dose_grace_minutes: int
    last_check_at: datetime | None = None
