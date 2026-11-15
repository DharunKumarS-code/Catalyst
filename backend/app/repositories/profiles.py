"""Data access for `elderly_profiles`. Every lookup is keyed by owner or by an id the
caller has already been authorized for; there is no "list all profiles" query."""

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.core.time import utc_now
from app.db.indexes import PROFILES_COLLECTION


class ProfileAlreadyExistsError(Exception):
    pass


class ProfileRepository:
    def __init__(self, db: Database) -> None:
        self._profiles = db[PROFILES_COLLECTION]

    def get_by_user(self, user_id: ObjectId) -> dict | None:
        return self._profiles.find_one({"user_id": user_id})

    def get_by_id(self, profile_id: ObjectId) -> dict | None:
        return self._profiles.find_one({"_id": profile_id})

    def get_many(self, profile_ids: list[ObjectId]) -> dict[ObjectId, dict]:
        return {p["_id"]: p for p in self._profiles.find({"_id": {"$in": profile_ids}})}

    def create(self, user_id: ObjectId, data: dict, *, is_demo: bool) -> dict:
        now = utc_now()
        doc = {**data, "user_id": user_id, "is_demo": is_demo, "created_at": now, "updated_at": now}
        try:
            result = self._profiles.insert_one(doc)
        except DuplicateKeyError as exc:
            raise ProfileAlreadyExistsError from exc
        doc["_id"] = result.inserted_id
        return doc

    def update(self, user_id: ObjectId, data: dict) -> dict | None:
        return self._profiles.find_one_and_update(
            {"user_id": user_id},
            {"$set": {**data, "updated_at": utc_now()}},
            return_document=ReturnDocument.AFTER,
        )
