"""Failed sign-in log used to throttle password guessing.
Rows hold only a case-folded email, the client IP and a timestamp, and expire via a TTL index."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from pymongo.database import Database

from app.db.indexes import LOGIN_FAILURES_COLLECTION


@dataclass(frozen=True)
class FailureCounts:
    pair: int  # this email from this IP
    ip: int  # this IP, any email
    email: int  # this email, any IP


class LoginAttemptRepository:
    def __init__(self, db: Database) -> None:
        self._col = db[LOGIN_FAILURES_COLLECTION]

    def counts(self, email: str, ip: str | None, now: datetime, window: timedelta) -> FailureCounts:
        """All three buckets in one indexed round trip. `ip=None` means IP limits are off."""
        email = email.casefold()
        since = {"created_at": {"$gt": now - window}}
        facets: dict = {"email": [{"$match": {"email": email}}, {"$count": "n"}]}
        if ip is not None:
            facets["ip"] = [{"$match": {"ip": ip}}, {"$count": "n"}]
            facets["pair"] = [{"$match": {"email": email, "ip": ip}}, {"$count": "n"}]
        match = {"$or": [{"email": email}, {"ip": ip}]} if ip is not None else {"email": email}
        row: dict = next(self._col.aggregate([{"$match": {**match, **since}}, {"$facet": facets}]), {})

        def n(key: str) -> int:
            return row.get(key, [{}])[0].get("n", 0) if row.get(key) else 0

        email_count = n("email")
        # Without a trustworthy IP the pair bucket falls back to the email (the previous behaviour).
        return FailureCounts(pair=n("pair") if ip is not None else email_count, ip=n("ip"), email=email_count)

    def record(self, email: str, ip: str | None, now: datetime) -> None:
        self._col.insert_one({"email": email.casefold(), "ip": ip, "created_at": now})

    def clear(self, email: str, ip: str | None) -> None:
        """A successful sign-in clears only its own (email, IP) failures, so an attacker's
        failures from elsewhere still count towards the per-IP and per-email limits."""
        query: dict = {"email": email.casefold()}
        if ip is not None:
            query["ip"] = ip
        self._col.delete_many(query)


class RateLimitRepository:
    """Generic sliding-window counter (e.g. registrations per IP). Rows expire via TTL."""

    def __init__(self, db: Database, collection: str) -> None:
        self._col = db[collection]

    def hit(self, bucket: str, key: str, now: datetime, window: timedelta, limit: int) -> bool:
        """Record an attempt; return False if the limit for the window was already reached."""
        if self._col.count_documents({"bucket": bucket, "key": key, "created_at": {"$gt": now - window}}) >= limit:
            return False
        self._col.insert_one({"bucket": bucket, "key": key, "created_at": now})
        return True
