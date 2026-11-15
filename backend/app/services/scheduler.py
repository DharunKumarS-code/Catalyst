"""Lightweight background scheduler: one daemon thread per process running the notification
cycle every NOTIFICATION_INTERVAL_SECONDS. No external queue.

Several processes (uvicorn workers, Cloud Run instances) may start the thread, but only the
holder of a short MongoDB lease (`scheduler_locks`) runs a cycle; the others stand by and take
over when the lease expires. Creation is also deduplicated by a unique index and delivery
claims are atomic, so even overlapping cycles cannot send a notification twice."""

import logging
import os
import socket
import threading
import uuid
from datetime import datetime, timedelta

from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.core.config import Settings
from app.core.time import utc_now
from app.db.indexes import SCHEDULER_LOCKS_COLLECTION
from app.db.mongodb import mongodb
from app.services.email import SmtpSender
from app.services.notifications import NotificationEngine

logger = logging.getLogger(__name__)

FIRST_RUN_DELAY_SECONDS = 5
LOCK_ID = "notifications"


def acquire_lease(db: Database, holder: str, now: datetime, ttl: timedelta) -> bool:
    """Take or renew the single scheduler lease. Atomic: an upsert that races with another
    holder hits the unique _id and fails, so at most one process holds an unexpired lease."""
    try:
        db[SCHEDULER_LOCKS_COLLECTION].find_one_and_update(
            {"_id": LOCK_ID, "$or": [{"holder": holder}, {"expires_at": {"$lte": now}}]},
            {"$set": {"holder": holder, "expires_at": now + ttl, "renewed_at": now}},
            upsert=True,
        )
        return True
    except DuplicateKeyError:
        return False


def lease_ttl(settings: Settings) -> timedelta:
    return timedelta(seconds=settings.notification_interval_seconds * 2 + 30)


class NotificationScheduler:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.last_run_at: datetime | None = None
        self.is_leader = False
        self.holder_id = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, settings: Settings) -> None:
        if not settings.notifications_enabled or self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, args=(settings,), name="notifications", daemon=True)
        self._thread.start()
        logger.info("Notification scheduler started (every %ss, delivery: %s).",
                    settings.notification_interval_seconds, "email" if settings.email_delivery_active else "preview")

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._thread = None

    def _loop(self, settings: Settings) -> None:
        sender = SmtpSender(settings) if settings.email_delivery_active else None
        wait = FIRST_RUN_DELAY_SECONDS
        while not self._stop.wait(wait):
            wait = settings.notification_interval_seconds
            try:
                mongodb.ensure_indexes()
                self.is_leader = acquire_lease(mongodb.db, self.holder_id, utc_now(), lease_ttl(settings))
                if not self.is_leader:
                    continue  # another process is running the cycles
                result = NotificationEngine(mongodb.db, settings, sender).run_cycle(utc_now())
                self.last_run_at = utc_now()
                if result.created or result.delivered:
                    logger.info("Notification cycle: %s queued, delivered %s", result.created, result.delivered)
            except Exception as exc:
                self.is_leader = False  # keep the loop alive (e.g. database briefly unavailable)
                logger.warning("Notification cycle failed: %s", type(exc).__name__)


scheduler = NotificationScheduler()
