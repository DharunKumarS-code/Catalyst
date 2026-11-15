"""Notification history, preferences, system status and a test message.

Everything is keyed by the signed-in user: preferences can only be read/changed for yourself,
and history only contains notifications about you (elderly) or sent to you (anyone).
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pymongo.database import Database

from app.api.deps import get_auth_settings, get_current_user, get_db
from app.core.config import Settings
from app.core.time import utc_now
from app.db.ids import to_object_id
from app.repositories.notifications import NotificationRepository, PreferenceRepository
from app.repositories.users import UserRepository
from app.schemas.notification import (
    NotificationOut,
    NotificationPreferences,
    NotificationSystemStatus,
)
from app.schemas.user import Role, UserPublic
from app.services.email import SmtpSender
from app.services.notifications import NotificationEngine
from app.services.scheduler import scheduler

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _out(doc: dict, user_id) -> NotificationOut:
    return NotificationOut(
        id=str(doc["_id"]),
        **{k: doc.get(k) for k in NotificationOut.model_fields if k in doc and k not in ("id", "recipient_is_you")},
        recipient_is_you=doc["recipient_user_id"] == user_id,
    )


@router.get("", response_model=list[NotificationOut])
def notification_history(
    limit: int = Query(50, ge=1, le=200),
    user: UserPublic = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    uid = to_object_id(user.id)
    docs = NotificationRepository(db).history(uid, as_owner=user.role == Role.ELDERLY, is_demo=user.is_demo, limit=limit)
    return [_out(d, uid) for d in docs]


@router.get("/preferences", response_model=NotificationPreferences)
def get_preferences(user: UserPublic = Depends(get_current_user), db: Database = Depends(get_db)):
    return PreferenceRepository(db).get(to_object_id(user.id))


@router.put("/preferences", response_model=NotificationPreferences)
def update_preferences(
    body: NotificationPreferences, user: UserPublic = Depends(get_current_user), db: Database = Depends(get_db)
):
    # Always the caller's own preferences: there is no way to address another user's.
    return PreferenceRepository(db).save(to_object_id(user.id), body, utc_now())


@router.get("/status", response_model=NotificationSystemStatus)
def notification_status(
    user: UserPublic = Depends(get_current_user), settings: Settings = Depends(get_auth_settings)
):
    return NotificationSystemStatus(
        delivery="email" if settings.email_delivery_active else "preview",
        smtp_configured=settings.smtp_configured,
        scheduler_running=scheduler.running,
        check_interval_seconds=settings.notification_interval_seconds,
        missed_dose_grace_minutes=settings.missed_dose_grace_minutes,
        last_check_at=scheduler.last_run_at,
    )


@router.post("/test", response_model=NotificationOut, status_code=status.HTTP_202_ACCEPTED)
def send_test(
    background: BackgroundTasks,
    user: UserPublic = Depends(get_current_user),
    db: Database = Depends(get_db),
    settings: Settings = Depends(get_auth_settings),
):
    """Queue a test message to yourself. It is delivered after the response is sent, so the
    request never waits for the mail server."""
    uid = to_object_id(user.id)
    record = UserRepository(db).get_by_id(user.id)
    engine = NotificationEngine(db, settings, SmtpSender(settings) if settings.email_delivery_active else None)
    nid = engine.queue_test(record, utc_now())
    if nid is None:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "A test message was already sent this minute.")
    background.add_task(engine.deliver_one, nid, utc_now())
    return _out(NotificationRepository(db).get(nid), uid)
