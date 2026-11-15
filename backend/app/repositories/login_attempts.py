"""Failed sign-in log used to throttle password guessing per email address.
Rows hold only a case-folded email and a timestamp, and expire via a TTL index."""

from datetime import datetime, timedelta

from pymongo.database import Database

from app.db.indexes import LOGIN_FAILURES_COLLECTION


class LoginAttemptRepository:
    def __init__(self, db: Database) -> None:
        self._col = db[LOGIN_FAILURES_COLLECTION]

    def count_recent(self, email: str, now: datetime, window: timedelta) -> int:
        return self._col.count_documents({"email": email.casefold(), "created_at": {"$gt": now - window}})

    def record(self, email: str, now: datetime) -> None:
        self._col.insert_one({"email": email.casefold(), "created_at": now})

    def clear(self, email: str) -> None:
        self._col.delete_many({"email": email.casefold()})
