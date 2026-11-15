"""Data access for `notifications` (delivery queue + history) and `notification_preferences`."""

from datetime import datetime, timedelta

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.db.indexes import NOTIFICATION_PREFERENCES_COLLECTION, NOTIFICATIONS_COLLECTION
from app.schemas.notification import NotificationPreferences

MAX_ATTEMPTS = 3
LEASE = timedelta(minutes=5)  # a send interrupted by a crash/restart is retried after this


class NotificationRepository:
    def __init__(self, db: Database) -> None:
        self._n = db[NOTIFICATIONS_COLLECTION]

    def create_if_absent(self, doc: dict) -> bool:
        """Insert unless a notification with the same dedupe_key exists (unique index)."""
        try:
            self._n.insert_one(doc)
            return True
        except DuplicateKeyError:
            return False

    def get(self, notification_id: ObjectId) -> dict | None:
        return self._n.find_one({"_id": notification_id}, {"body": 0, "recipient_email": 0})

    def claim_next(self, now: datetime) -> dict | None:
        """Atomically take one due notification. Several workers/instances can run this
        concurrently: each document is claimed by exactly one."""
        return self._n.find_one_and_update(
            {
                "$or": [
                    {"status": "pending", "next_attempt_at": {"$lte": now}},
                    {"status": "sending", "claimed_until": {"$lte": now}},  # stale claim after a crash
                ],
                "attempts": {"$lt": MAX_ATTEMPTS},
            },
            {"$set": {"status": "sending", "claimed_until": now + LEASE}, "$inc": {"attempts": 1}},
            sort=[("next_attempt_at", 1)],
            return_document=ReturnDocument.AFTER,
        )

    def claim(self, notification_id: ObjectId, now: datetime) -> dict | None:
        return self._n.find_one_and_update(
            {"_id": notification_id, "status": "pending", "attempts": {"$lt": MAX_ATTEMPTS}},
            {"$set": {"status": "sending", "claimed_until": now + LEASE}, "$inc": {"attempts": 1}},
            return_document=ReturnDocument.AFTER,
        )

    def finish(self, notification_id: ObjectId, changes: dict) -> None:
        self._n.update_one({"_id": notification_id, "status": "sending"}, {"$set": changes})

    def fail_exhausted(self, now: datetime) -> None:
        """Stale claims that already used every attempt become failed instead of stuck."""
        self._n.update_many(
            {"status": "sending", "claimed_until": {"$lte": now}, "attempts": {"$gte": MAX_ATTEMPTS}},
            {"$set": {"status": "failed", "failure_reason": "Delivery was interrupted repeatedly."}},
        )

    def history(self, user_id: ObjectId, *, as_owner: bool, is_demo: bool, limit: int) -> list[dict]:
        """Owner: everything about them (any recipient). Others: only what they received."""
        field = "owner_user_id" if as_owner else "recipient_user_id"
        query = {"$or": [{field: user_id}, {"recipient_user_id": user_id}], "is_demo": is_demo}
        return list(self._n.find(query, {"body": 0, "recipient_email": 0}).sort("created_at", -1).limit(limit))


class PreferenceRepository:
    def __init__(self, db: Database) -> None:
        self._p = db[NOTIFICATION_PREFERENCES_COLLECTION]

    def get(self, user_id: ObjectId) -> NotificationPreferences:
        doc = self._p.find_one({"user_id": user_id}) or {}
        return NotificationPreferences(**{k: v for k, v in doc.items() if k in NotificationPreferences.model_fields})

    def get_many(self, user_ids: list[ObjectId]) -> dict[ObjectId, NotificationPreferences]:
        found = {d["user_id"]: d for d in self._p.find({"user_id": {"$in": user_ids}})}
        fields = NotificationPreferences.model_fields
        return {
            uid: NotificationPreferences(**{k: v for k, v in found.get(uid, {}).items() if k in fields})
            for uid in user_ids
        }

    def save(self, user_id: ObjectId, prefs: NotificationPreferences, now: datetime) -> NotificationPreferences:
        self._p.update_one(
            {"user_id": user_id},
            {"$set": {**prefs.model_dump(), "updated_at": now}, "$setOnInsert": {"user_id": user_id}},
            upsert=True,
        )
        return prefs
