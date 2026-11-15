"""Notification history, preferences, system status and a test message.

Everything is keyed by the signed-in user: preferences can only be read/changed for yourself,
and history only contains notifications about you (elderly) or sent to you (anyone).
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from pymongo.database import Database

from app.api.deps import get_auth_settings, get_current_user, get_db
from app.core.config import Settings
from app.core.time import utc_now
from app.repositories.notifications import NotificationRepository, PreferenceRepository
from app.repositories.users import UserRepository
from app.schemas.notification import (
    NotificationOut,
    NotificationPreferences,
    NotificationSystemStatus,
    UnreadCount,
)
from app.schemas.user import Role, UserPublic
from app.services.email import SmtpSender
from app.services.notifications import NotificationEngine
from app.services.scheduler import scheduler

router = APIRouter(prefix="/notifications", tags=["notifications"])
UNREAD_CAP = 99


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
    uid = user.oid
    docs = NotificationRepository(db).history(
        uid, as_owner=user.role == Role.ELDERLY, is_demo=user.is_demo, limit=limit
    )
    return [_out(d, uid) for d in docs]


@router.get("/unread-count", response_model=UnreadCount)
def unread_count(user: UserPublic = Depends(get_current_user), db: Database = Depends(get_db)):
    """Notifications visible to the caller that are newer than when they last opened the history.
    The frontend asks on navigation (never by polling), so it does not keep a sleeping server awake."""
    uid = user.oid
    seen = UserRepository(db).notifications_seen_at(uid)
    count = NotificationRepository(db).count_since(
        uid, as_owner=user.role == Role.ELDERLY, is_demo=user.is_demo, since=seen, cap=UNREAD_CAP
    )
    return UnreadCount(unread=count, seen_at=seen)


@router.post("/seen", status_code=status.HTTP_204_NO_CONTENT)
def mark_seen(user: UserPublic = Depends(get_current_user), db: Database = Depends(get_db)) -> Response:
    UserRepository(db).mark_notifications_seen(user.oid, utc_now())
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/preferences", response_model=NotificationPreferences)
def get_preferences(user: UserPublic = Depends(get_current_user), db: Database = Depends(get_db)):
    return PreferenceRepository(db).get(user.oid)


@router.put("/preferences", response_model=NotificationPreferences)
def update_preferences(
    body: NotificationPreferences, user: UserPublic = Depends(get_current_user), db: Database = Depends(get_db)
):
    # Always the caller's own preferences: there is no way to address another user's.
    return PreferenceRepository(db).save(user.oid, body, utc_now())


@router.get("/status", response_model=NotificationSystemStatus)
def notification_status(user: UserPublic = Depends(get_current_user), settings: Settings = Depends(get_auth_settings)):
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
    uid = user.oid
    record = UserRepository(db).get_by_id(user.id)
    engine = NotificationEngine(db, settings, SmtpSender(settings) if settings.email_delivery_active else None)
    nid = engine.queue_test(record, utc_now())
    if nid is None:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "A test message was already sent this minute.")
    background.add_task(engine.deliver_one, nid, utc_now())
    return _out(NotificationRepository(db).get(nid), uid)
