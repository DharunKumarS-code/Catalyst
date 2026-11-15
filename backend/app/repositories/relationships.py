"""Data access for `relationships` (elderly profile <-> caretaker/family member)."""

from datetime import datetime

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.db.indexes import RELATIONSHIPS_COLLECTION


class RelationshipExistsError(Exception):
    pass


class RelationshipRepository:
    def __init__(self, db: Database) -> None:
        self._rels = db[RELATIONSHIPS_COLLECTION]

    def active_exists(self, profile_id: ObjectId, member_user_id: ObjectId) -> bool:
        return (
            self._rels.count_documents(
                {"profile_id": profile_id, "member_user_id": member_user_id, "status": "active"}, limit=1
            )
            == 1
        )

    def create(
        self,
        *,
        profile_id: ObjectId,
        elderly_user_id: ObjectId,
        member_user_id: ObjectId,
        role: str,
        invitation_id: ObjectId | None,
        now: datetime,
        is_demo: bool,
    ) -> dict:
        doc = {
            "profile_id": profile_id,
            "elderly_user_id": elderly_user_id,
            "member_user_id": member_user_id,
            "role": role,
            "status": "active",
            "invitation_id": invitation_id,
            "is_demo": is_demo,
            "created_at": now,
            "revoked_at": None,
            # Off by default: only the elderly owner can allow a caretaker to record doses.
            "can_record_doses": False,
        }
        try:
            doc["_id"] = self._rels.insert_one(doc).inserted_id
        except DuplicateKeyError as exc:  # partial unique index on active (profile, member)
            raise RelationshipExistsError from exc
        return doc

    def list_active_for_elderly(self, elderly_user_id: ObjectId) -> list[dict]:
        return list(self._rels.find({"elderly_user_id": elderly_user_id, "status": "active"}).sort("created_at", 1))

    def list_active_for_member(self, member_user_id: ObjectId, *, is_demo: bool) -> list[dict]:
        return list(
            self._rels.find({"member_user_id": member_user_id, "status": "active", "is_demo": is_demo}).sort(
                "created_at", 1
            )
        )

    def get_active_for_member(self, profile_id: ObjectId, member_user_id: ObjectId, *, is_demo: bool) -> dict | None:
        """The authorization check for a member viewing a profile; evaluated on every request."""
        return self._rels.find_one(
            {"profile_id": profile_id, "member_user_id": member_user_id, "status": "active", "is_demo": is_demo}
        )

    def set_dose_permission(
        self, relationship_id: ObjectId, elderly_user_id: ObjectId, allowed: bool, now: datetime
    ) -> dict | None:
        """Owner-only, active caretaker links only. Returns the updated relationship or None."""
        return self._rels.find_one_and_update(
            {"_id": relationship_id, "elderly_user_id": elderly_user_id, "status": "active", "role": "caretaker"},
            {"$set": {"can_record_doses": allowed, "permission_changed_at": now}},
            return_document=ReturnDocument.AFTER,
        )

    def get_active_for_elderly(self, relationship_id: ObjectId, elderly_user_id: ObjectId) -> dict | None:
        return self._rels.find_one({"_id": relationship_id, "elderly_user_id": elderly_user_id, "status": "active"})

    def revoke(self, relationship_id: ObjectId, elderly_user_id: ObjectId, now: datetime) -> bool:
        result = self._rels.update_one(
            {"_id": relationship_id, "elderly_user_id": elderly_user_id, "status": "active"},
            {"$set": {"status": "revoked", "revoked_at": now, "revoked_by": elderly_user_id}},
        )
        return result.modified_count == 1

    # ---- reminder engine ----

    def active_for_elderly_users(self, elderly_user_ids: list[ObjectId]) -> list[dict]:
        if not elderly_user_ids:
            return []
        return list(self._rels.find({"elderly_user_id": {"$in": elderly_user_ids}, "status": "active"}))

    def link_is_active(self, elderly_user_id: ObjectId, member_user_id: ObjectId, *, is_demo: bool) -> bool:
        """Re-checked right before a caretaker/family alert is sent."""
        return (
            self._rels.count_documents(
                {
                    "elderly_user_id": elderly_user_id,
                    "member_user_id": member_user_id,
                    "status": "active",
                    "is_demo": is_demo,
                },
                limit=1,
            )
            == 1
        )
