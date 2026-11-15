"""Data access for `invitations` and `redemption_failures`.

Only a SHA-256 hash of each invitation code is stored. Status transitions use
conditional single-document updates so concurrent redemptions cannot both succeed.
"""

from datetime import datetime, timedelta

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.database import Database

from app.db.indexes import INVITATIONS_COLLECTION, REDEMPTION_FAILURES_COLLECTION


class InvitationRepository:
    def __init__(self, db: Database) -> None:
        self._invitations = db[INVITATIONS_COLLECTION]

    def create(
        self,
        *,
        code_hash: str,
        profile_id: ObjectId,
        elderly_user_id: ObjectId,
        role: str,
        expires_at: datetime,
        now: datetime,
        is_demo: bool,
    ) -> dict:
        doc = {
            "code_hash": code_hash,
            "profile_id": profile_id,
            "elderly_user_id": elderly_user_id,
            "role": role,
            "status": "pending",
            "failed_attempts": 0,
            "is_demo": is_demo,
            "created_at": now,
            "expires_at": expires_at,
            "redeemed_at": None,
            "redeemed_by": None,
        }
        doc["_id"] = self._invitations.insert_one(doc).inserted_id
        return doc

    def get_by_hash(self, code_hash: str) -> dict | None:
        return self._invitations.find_one({"code_hash": code_hash})

    def list_for_owner(self, elderly_user_id: ObjectId, limit: int = 50) -> list[dict]:
        return list(
            self._invitations.find({"elderly_user_id": elderly_user_id}, {"code_hash": 0})
            .sort("created_at", -1)
            .limit(limit)
        )

    def count_open(self, elderly_user_id: ObjectId, now: datetime) -> int:
        return self._invitations.count_documents(
            {"elderly_user_id": elderly_user_id, "status": "pending", "expires_at": {"$gt": now}}
        )

    def consume(self, invitation_id: ObjectId, user_id: ObjectId, now: datetime) -> dict | None:
        """Atomically mark a pending, unexpired invitation as redeemed. None if it lost the race."""
        return self._invitations.find_one_and_update(
            {"_id": invitation_id, "status": "pending", "expires_at": {"$gt": now}},
            {"$set": {"status": "redeemed", "redeemed_at": now, "redeemed_by": user_id}},
            return_document=ReturnDocument.AFTER,
        )

    def release(self, invitation_id: ObjectId, user_id: ObjectId) -> None:
        """Undo `consume` when the relationship could not be created."""
        self._invitations.update_one(
            {"_id": invitation_id, "status": "redeemed", "redeemed_by": user_id},
            {"$set": {"status": "pending", "redeemed_at": None, "redeemed_by": None}},
        )

    def register_failed_attempt(self, invitation_id: ObjectId, lock_after: int) -> None:
        """Count a misuse (e.g. wrong role) and lock the invitation after too many."""
        doc = self._invitations.find_one_and_update(
            {"_id": invitation_id},
            {"$inc": {"failed_attempts": 1}},
            return_document=ReturnDocument.AFTER,
        )
        if doc and doc["failed_attempts"] >= lock_after:
            self._invitations.update_one({"_id": invitation_id, "status": "pending"}, {"$set": {"status": "locked"}})

    def revoke(self, invitation_id: ObjectId, elderly_user_id: ObjectId) -> bool:
        result = self._invitations.update_one(
            {"_id": invitation_id, "elderly_user_id": elderly_user_id, "status": "pending"},
            {"$set": {"status": "revoked"}},
        )
        return result.modified_count == 1


class RedemptionFailureRepository:
    """Per-user failed redemption log used for rate limiting (rows expire via TTL index)."""

    def __init__(self, db: Database) -> None:
        self._failures = db[REDEMPTION_FAILURES_COLLECTION]

    def count_recent(self, user_id: ObjectId, now: datetime, window: timedelta) -> int:
        return self._failures.count_documents({"user_id": user_id, "created_at": {"$gt": now - window}})

    def oldest_recent(self, user_id: ObjectId, now: datetime, window: timedelta) -> datetime | None:
        doc = self._failures.find_one(
            {"user_id": user_id, "created_at": {"$gt": now - window}}, sort=[("created_at", 1)]
        )
        return doc["created_at"] if doc else None

    def record(self, user_id: ObjectId, now: datetime, reason: str) -> None:
        self._failures.insert_one({"user_id": user_id, "created_at": now, "reason": reason})
