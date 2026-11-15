"""Data access for `appointments`. Every query is scoped by the owning elderly user's id."""

from datetime import datetime

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.db.indexes import APPOINTMENTS_COLLECTION


class DuplicateAppointmentError(Exception):
    pass


class AppointmentRepository:
    def __init__(self, db: Database) -> None:
        self._appts = db[APPOINTMENTS_COLLECTION]

    def create(self, doc: dict) -> dict:
        try:
            doc["_id"] = self._appts.insert_one(doc).inserted_id
        except DuplicateKeyError as exc:  # same doctor, same instant, still scheduled
            raise DuplicateAppointmentError from exc
        return doc

    def get(self, appointment_id: ObjectId, user_id: ObjectId) -> dict | None:
        return self._appts.find_one({"_id": appointment_id, "user_id": user_id})

    def upcoming(self, user_id: ObjectId, now: datetime, limit: int) -> list[dict]:
        query = {"user_id": user_id, "status": "scheduled", "scheduled_at": {"$gte": now}}
        return list(self._appts.find(query).sort("scheduled_at", 1).limit(limit))

    def history(self, user_id: ObjectId, now: datetime, limit: int) -> list[dict]:
        """Past appointments plus anything completed or cancelled, newest first."""
        query = {"user_id": user_id, "$or": [{"scheduled_at": {"$lt": now}}, {"status": {"$ne": "scheduled"}}]}
        return list(self._appts.find(query).sort("scheduled_at", -1).limit(limit))

    def update_scheduled(self, appointment_id: ObjectId, user_id: ObjectId, changes: dict) -> dict | None:
        """Edit only while still scheduled (atomic: a concurrent cancel wins cleanly)."""
        try:
            return self._appts.find_one_and_update(
                {"_id": appointment_id, "user_id": user_id, "status": "scheduled"},
                {"$set": changes},
                return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError as exc:
            raise DuplicateAppointmentError from exc

    def transition(
        self, appointment_id: ObjectId, user_id: ObjectId, *, new: str, now: datetime, extra: dict | None = None
    ) -> dict | None:
        """Atomic scheduled -> completed/cancelled. Repeats match nothing and change nothing."""
        query = {"_id": appointment_id, "user_id": user_id, "status": "scheduled", **(extra or {})}
        return self._appts.find_one_and_update(
            query,
            {
                "$set": {"status": new, "status_changed_at": now, "updated_at": now},
                "$push": {"history": {"from": "scheduled", "to": new, "at": now}},
            },
            return_document=ReturnDocument.AFTER,
        )

    def upcoming_for_users(
        self, user_ids: list[ObjectId], now: datetime, per_user: int
    ) -> dict[ObjectId, tuple[list[dict], int]]:
        """The next `per_user` scheduled appointments of each owner, in one aggregation."""
        pipeline = [
            {"$match": {"user_id": {"$in": user_ids}, "status": "scheduled", "scheduled_at": {"$gte": now}}},
            {"$sort": {"scheduled_at": 1}},
            {"$group": {"_id": "$user_id", "items": {"$push": "$$ROOT"}, "total": {"$sum": 1}}},
            {"$project": {"items": {"$slice": ["$items", per_user]}, "total": 1}},
        ]
        return {row["_id"]: (row["items"], row["total"]) for row in self._appts.aggregate(pipeline)}

    def recently_updated(self, user_ids: list[ObjectId], since: datetime, limit: int) -> list[dict]:
        """Appointments completed or cancelled since `since`, newest change first."""
        query = {"user_id": {"$in": user_ids}, "status": {"$ne": "scheduled"}, "status_changed_at": {"$gte": since}}
        return list(self._appts.find(query).sort("status_changed_at", -1).limit(limit))

    def count(self, user_id: ObjectId) -> int:
        return self._appts.count_documents({"user_id": user_id})
