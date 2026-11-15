from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "UTC"


def utc_now() -> datetime:
    """Current UTC time truncated to milliseconds, MongoDB's storage precision, so values
    returned right after a write equal the values read back later."""
    now = datetime.now(UTC)
    return now.replace(microsecond=now.microsecond // 1000 * 1000)


def is_valid_timezone(name: str) -> bool:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):  # unknown, malformed, or a directory like "America"
        return False
    return True


def zone(name: str | None) -> ZoneInfo:
    """ZoneInfo for a stored zone name, falling back to UTC for missing/invalid values."""
    if name and is_valid_timezone(name):
        return ZoneInfo(name)
    return ZoneInfo(DEFAULT_TIMEZONE)
