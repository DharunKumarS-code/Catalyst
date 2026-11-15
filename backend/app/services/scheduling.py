"""Pure dose-schedule generation (no I/O, so it is easy to test across time zones and DST).

Scheduled times are wall-clock times in the elderly user's IANA time zone. Each one is
converted to a UTC instant for storage, so "08:00 in New York" is 13:00Z in winter and
12:00Z in summer. Generation is bounded: from the medication's start (never before
`schedule_from`) to the earlier of its end date and today + horizon.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

# Days that were never generated (e.g. the app was not opened) are back-filled at most this far.
MAX_BACKFILL_DAYS = 90


@dataclass(frozen=True)
class PlannedDose:
    scheduled_at: datetime  # UTC
    local_date: str  # YYYY-MM-DD in the user's zone
    local_time: str  # HH:MM in the user's zone


def local_midnight_utc(day: date, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, time(0, 0), tzinfo=tz).astimezone(timezone.utc)


def to_utc(day: date, hhmm: str, tz: ZoneInfo) -> datetime:
    hour, minute = (int(part) for part in hhmm.split(":"))
    # A wall time skipped by a DST jump (e.g. 02:30) resolves to the equivalent instant
    # just after the jump; an ambiguous one (clocks back) uses the first occurrence.
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz).astimezone(timezone.utc)


def plan_doses(med: dict, tz: ZoneInfo, now: datetime, horizon_days: int) -> tuple[list[PlannedDose], str | None]:
    """Doses still to generate for `med`, and the last local date covered (None = nothing to do)."""
    if med.get("status") != "active":
        return [], None

    today = now.astimezone(tz).date()
    schedule_from: datetime = med["schedule_from"]
    start = date.fromisoformat(med["start_date"])
    end = date.fromisoformat(med["end_date"]) if med.get("end_date") else None

    first = max(start, schedule_from.astimezone(tz).date(), today - timedelta(days=MAX_BACKFILL_DAYS))
    if med.get("scheduled_through"):
        first = max(first, date.fromisoformat(med["scheduled_through"]) + timedelta(days=1))
    last = today + timedelta(days=horizon_days)
    if end is not None:
        last = min(last, end)
    if first > last:
        return [], None

    planned: list[PlannedDose] = []
    day = first
    while day <= last:
        for hhmm in med["times"]:
            at = to_utc(day, hhmm, tz)
            if at >= schedule_from:
                planned.append(PlannedDose(at, day.isoformat(), hhmm))
        day += timedelta(days=1)
    return planned, last.isoformat()
