"""Data access for `medications`. Every query is scoped by the owning elderly user's id."""

from datetime import datetime

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.database import Database

from app.core.time import utc_now
from app.db.indexes import MEDICATIONS_COLLECTION


class MedicationRepository:
    def __init__(self, db: Database) -> None:
        self._meds = db[MEDICATIONS_COLLECTION]

    def create(
        self, *, user_id: ObjectId, profile_id: ObjectId, data: dict, is_demo: bool, schedule_from: datetime
    ) -> dict:
        now = utc_now()
        doc = {
            **data,
            "user_id": user_id,
            "profile_id": profile_id,
            "is_demo": is_demo,
            "status": "active",
            "discontinued_at": None,
            # Doses are generated only at/after this instant and up to `scheduled_through` (local date).
            "schedule_from": schedule_from,
            "scheduled_through": None,
            "created_at": now,
            "updated_at": now,
        }
        doc["_id"] = self._meds.insert_one(doc).inserted_id
        return doc

    def get(self, medication_id: ObjectId, user_id: ObjectId) -> dict | None:
        return self._meds.find_one({"_id": medication_id, "user_id": user_id})

    def list_for_user(self, user_id: ObjectId, *, status: str | None = None) -> list[dict]:
        query: dict = {"user_id": user_id}
        if status:
            query["status"] = status
        return list(self._meds.find(query).sort([("status", 1), ("name", 1)]))

    def list_for_users(self, user_ids: list[ObjectId]) -> list[dict]:
        return list(self._meds.find({"user_id": {"$in": user_ids}}))

    def get_many(self, user_id: ObjectId, ids: list[ObjectId]) -> dict[ObjectId, dict]:
        return {m["_id"]: m for m in self._meds.find({"user_id": user_id, "_id": {"$in": ids}})}

    def update(self, medication_id: ObjectId, user_id: ObjectId, data: dict, *, reset_schedule_from: datetime | None):
        changes = {**data, "updated_at": utc_now()}
        if reset_schedule_from is not None:
            changes.update(schedule_from=reset_schedule_from, scheduled_through=None)
        return self._meds.find_one_and_update(
            {"_id": medication_id, "user_id": user_id, "status": "active"},
            {"$set": changes},
            return_document=ReturnDocument.AFTER,
        )

    def discontinue(self, medication_id: ObjectId, user_id: ObjectId, now: datetime) -> dict | None:
        return self._meds.find_one_and_update(
            {"_id": medication_id, "user_id": user_id, "status": "active"},
            {"$set": {"status": "discontinued", "discontinued_at": now, "updated_at": now}},
            return_document=ReturnDocument.AFTER,
        )

    def delete(self, medication_id: ObjectId, user_id: ObjectId) -> bool:
        return self._meds.delete_one({"_id": medication_id, "user_id": user_id}).deleted_count == 1

    def mark_scheduled_through(self, medication_id: ObjectId, local_date: str) -> None:
        # $max keeps concurrent generators from moving the watermark backwards.
        self._meds.update_one({"_id": medication_id}, {"$max": {"scheduled_through": local_date}})

    def reset_schedules(self, user_id: ObjectId, schedule_from: datetime) -> None:
        """Used when the owner's time zone changes: active schedules regenerate from now."""
        self._meds.update_many(
            {"user_id": user_id, "status": "active"},
            {"$set": {"schedule_from": schedule_from, "scheduled_through": None}},
        )
