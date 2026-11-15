"""Data access for `doses`. Each dose is one scheduled intake of one medication at one UTC
instant; the unique (medication_id, scheduled_at) index makes generation idempotent."""

from datetime import datetime

from bson import ObjectId
from pymongo import ReturnDocument, UpdateOne
from pymongo.database import Database
from pymongo.errors import BulkWriteError

from app.db.indexes import DOSES_COLLECTION

DUPLICATE_KEY = 11000


def eligible_filter(now: datetime) -> dict:
    """THE adherence eligibility rule, used by every adherence query: a dose counts if it is
    not cancelled and is either due by `now` or already recorded (taken a little early counts)."""
    return {
        "status": {"$in": ["pending", "taken", "missed"]},
        "$or": [{"scheduled_at": {"$lte": now}}, {"status": {"$in": ["taken", "missed"]}}],
    }


class DoseRepository:
    def __init__(self, db: Database) -> None:
        self._doses = db[DOSES_COLLECTION]

    def insert_missing(self, docs: list[dict]) -> int:
        """Insert doses that do not exist yet. Existing doses (and their statuses) are never touched."""
        if not docs:
            return 0
        ops = [
            UpdateOne(
                {"medication_id": d["medication_id"], "scheduled_at": d["scheduled_at"]},
                {"$setOnInsert": d},
                upsert=True,
            )
            for d in docs
        ]
        try:
            return self._doses.bulk_write(ops, ordered=False).upserted_count
        except BulkWriteError as exc:
            # Two concurrent generators may race to upsert the same dose; the unique index wins.
            if any(e.get("code") != DUPLICATE_KEY for e in exc.details.get("writeErrors", [])):
                raise
            return exc.details.get("nUpserted", 0)

    def get(self, dose_id: ObjectId, user_id: ObjectId) -> dict | None:
        return self._doses.find_one({"_id": dose_id, "user_id": user_id})

    def for_day(self, user_id: ObjectId, local_date: str) -> list[dict]:
        return list(
            self._doses.find({"user_id": user_id, "local_date": local_date, "status": {"$ne": "cancelled"}}).sort(
                "scheduled_at", 1
            )
        )

    def history(
        self, user_id: ObjectId, *, since: datetime, until: datetime, medication_id: ObjectId | None, limit: int
    ) -> list[dict]:
        # Same rule as adherence: doses due by `until`, plus any already recorded (taken early).
        query: dict = {"user_id": user_id, "scheduled_at": {"$gte": since}, **eligible_filter(until)}
        if medication_id is not None:
            query["medication_id"] = medication_id
        return list(self._doses.find(query).sort("scheduled_at", -1).limit(limit))

    def counts_by_day(
        self, user_id: ObjectId, local_dates: list[str], now: datetime, medication_id: ObjectId | None = None
    ) -> dict[str, dict[str, int]]:
        """{local_date: {status: count}} for ELIGIBLE doses: not cancelled, and either due by
        `now` or already recorded (a dose taken a little early counts straight away)."""
        match: dict = {"user_id": user_id, "local_date": {"$in": local_dates}, **eligible_filter(now)}
        if medication_id is not None:
            match["medication_id"] = medication_id
        out: dict[str, dict[str, int]] = {}
        for row in self._doses.aggregate(
            [{"$match": match}, {"$group": {"_id": {"d": "$local_date", "s": "$status"}, "n": {"$sum": 1}}}]
        ):
            out.setdefault(row["_id"]["d"], {})[row["_id"]["s"]] = row["n"]
        return out

    # ---- multi-owner reads for the care dashboard (one query each, never one per profile) ----

    def counts_for_owner_days(
        self, owner_days: list[tuple[ObjectId, str]], now: datetime
    ) -> dict[tuple[ObjectId, str], dict[str, int]]:
        """{(user_id, local_date): {status: count}} of eligible doses, for each owner's own local day."""
        if not owner_days:
            return {}
        match = {"$and": [{"$or": [{"user_id": u, "local_date": d} for u, d in owner_days]}, eligible_filter(now)]}
        out: dict[tuple[ObjectId, str], dict[str, int]] = {}
        for row in self._doses.aggregate(
            [{"$match": match},
             {"$group": {"_id": {"u": "$user_id", "d": "$local_date", "s": "$status"}, "n": {"$sum": 1}}}]
        ):
            out.setdefault((row["_id"]["u"], row["_id"]["d"]), {})[row["_id"]["s"]] = row["n"]
        return out

    def for_owner_days(self, owner_days: list[tuple[ObjectId, str]]) -> list[dict]:
        if not owner_days:
            return []
        query = {"$or": [{"user_id": u, "local_date": d} for u, d in owner_days], "status": {"$ne": "cancelled"}}
        return list(self._doses.find(query, {"history": 0}).sort("scheduled_at", 1))

    def recently_recorded(self, user_ids: list[ObjectId], since: datetime, limit: int) -> list[dict]:
        """Doses actually recorded (taken/missed) by their owner since `since`, newest first."""
        query = {"user_id": {"$in": user_ids}, "status": {"$in": ["taken", "missed"]}, "status_changed_at": {"$gte": since}}
        return list(self._doses.find(query, {"history": 0}).sort("status_changed_at", -1).limit(limit))

    def transition(
        self, dose_id: ObjectId, user_id: ObjectId, *, expected: str, new: str, now: datetime, by: ObjectId
    ) -> dict | None:
        """Atomic compare-and-set: applies only if the dose still has the status the client saw.
        A repeated or stale request matches nothing and changes nothing."""
        return self._doses.find_one_and_update(
            {"_id": dose_id, "user_id": user_id, "status": expected},
            {
                "$set": {"status": new, "status_changed_at": now, "taken_at": now if new == "taken" else None},
                "$push": {"history": {"from": expected, "to": new, "at": now, "by": by}},
            },
            return_document=ReturnDocument.AFTER,
        )

    def delete_future_pending(self, medication_id: ObjectId, after: datetime) -> int:
        return self._doses.delete_many(
            {"medication_id": medication_id, "status": "pending", "scheduled_at": {"$gt": after}}
        ).deleted_count

    def delete_pending_outside(self, medication_id: ObjectId, start_date: str, end_date: str | None) -> int:
        """Unrecorded doses that fall outside a (new) start/end date range. ISO dates sort as strings."""
        outside: list[dict] = [{"local_date": {"$lt": start_date}}]
        if end_date:
            outside.append({"local_date": {"$gt": end_date}})
        return self._doses.delete_many(
            {"medication_id": medication_id, "status": "pending", "$or": outside}
        ).deleted_count

    def delete_future_pending_for_user(self, user_id: ObjectId, after: datetime) -> int:
        return self._doses.delete_many(
            {"user_id": user_id, "status": "pending", "scheduled_at": {"$gt": after}}
        ).deleted_count

    def cancel_future_pending(self, medication_id: ObjectId, after: datetime, now: datetime) -> int:
        return self._doses.update_many(
            {"medication_id": medication_id, "status": "pending", "scheduled_at": {"$gt": after}},
            {
                "$set": {"status": "cancelled", "status_changed_at": now},
                "$push": {"history": {"from": "pending", "to": "cancelled", "at": now, "by": None}},
            },
        ).modified_count

    def delete_for_medication(self, medication_id: ObjectId) -> int:
        return self._doses.delete_many({"medication_id": medication_id}).deleted_count
