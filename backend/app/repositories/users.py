"""Data access for the `users` collection."""

from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.db.indexes import USERS_COLLECTION
from app.schemas.user import Role


class EmailAlreadyRegisteredError(Exception):
    pass


class UserRepository:
    def __init__(self, db: Database) -> None:
        self._users = db[USERS_COLLECTION]

    def get_by_email(self, email: str) -> dict | None:
        return self._users.find_one({"email": email})

    def get_by_id(self, user_id: str) -> dict | None:
        try:
            oid = ObjectId(user_id)
        except (InvalidId, TypeError):
            return None
        return self._users.find_one({"_id": oid})

    def create(self, *, name: str, email: str, password_hash: str, role: Role, is_demo: bool = False) -> dict:
        now = datetime.now(timezone.utc)
        doc = {
            "name": name,
            "email": email,
            "password_hash": password_hash,
            "role": role.value,
            "is_demo": is_demo,
            "created_at": now,
            "updated_at": now,
        }
        try:
            result = self._users.insert_one(doc)
        except DuplicateKeyError as exc:
            raise EmailAlreadyRegisteredError from exc
        doc["_id"] = result.inserted_id
        return doc

    def get_many(self, user_ids: list[ObjectId]) -> dict[ObjectId, dict]:
        """Batch lookup without password hashes."""
        cursor = self._users.find({"_id": {"$in": user_ids}}, {"password_hash": 0})
        return {u["_id"]: u for u in cursor}

    def find_demo_users(self, emails: list[str]) -> list[dict]:
        return list(self._users.find({"email": {"$in": emails}, "is_demo": True}, {"email": 1, "role": 1}))

    def update_password_hash(self, user_id: ObjectId, password_hash: str) -> None:
        self._users.update_one(
            {"_id": user_id},
            {"$set": {"password_hash": password_hash, "updated_at": datetime.now(timezone.utc)}},
        )
