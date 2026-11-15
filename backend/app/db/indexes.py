"""Index definitions. Creating an existing index is a no-op in MongoDB, so this is idempotent."""

from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database

USERS_COLLECTION = "users"
PROFILES_COLLECTION = "elderly_profiles"
INVITATIONS_COLLECTION = "invitations"
RELATIONSHIPS_COLLECTION = "relationships"
REDEMPTION_FAILURES_COLLECTION = "redemption_failures"
MEDICATIONS_COLLECTION = "medications"
DOSES_COLLECTION = "doses"
APPOINTMENTS_COLLECTION = "appointments"
NOTIFICATIONS_COLLECTION = "notifications"
NOTIFICATION_PREFERENCES_COLLECTION = "notification_preferences"
LOGIN_FAILURES_COLLECTION = "login_failures"
SCHEDULER_LOCKS_COLLECTION = "scheduler_locks"

# Expired invitations are kept for this long (audit trail), then removed by a TTL index.
INVITATION_RETENTION_SECONDS = 30 * 24 * 3600


def ensure_indexes(db: Database) -> None:
    # Unique email is the authoritative guard against duplicate registrations (race-safe).
    db[USERS_COLLECTION].create_index([("email", ASCENDING)], unique=True, name="uniq_email")

    # One profile per elderly user.
    db[PROFILES_COLLECTION].create_index([("user_id", ASCENDING)], unique=True, name="uniq_profile_user")

    invitations = db[INVITATIONS_COLLECTION]
    invitations.create_index([("code_hash", ASCENDING)], unique=True, name="uniq_code_hash")
    invitations.create_index(
        [("elderly_user_id", ASCENDING), ("created_at", DESCENDING)], name="invitations_by_owner"
    )
    invitations.create_index(
        [("expires_at", ASCENDING)], expireAfterSeconds=INVITATION_RETENTION_SECONDS, name="invitations_ttl"
    )

    relationships = db[RELATIONSHIPS_COLLECTION]
    # Race-safe guard: at most one ACTIVE relationship per (profile, member).
    relationships.create_index(
        [("profile_id", ASCENDING), ("member_user_id", ASCENDING)],
        unique=True,
        partialFilterExpression={"status": "active"},
        name="uniq_active_relationship",
    )
    relationships.create_index([("elderly_user_id", ASCENDING), ("status", ASCENDING)], name="rel_by_elderly")
    relationships.create_index([("member_user_id", ASCENDING), ("status", ASCENDING)], name="rel_by_member")

    failures = db[REDEMPTION_FAILURES_COLLECTION]
    failures.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)], name="failures_by_user")
    # Rate-limit records expire automatically (the window itself is enforced in queries).
    failures.create_index([("created_at", ASCENDING)], expireAfterSeconds=24 * 3600, name="failures_ttl")

    medications = db[MEDICATIONS_COLLECTION]
    medications.create_index(
        [("user_id", ASCENDING), ("status", ASCENDING), ("name", ASCENDING)], name="medications_by_owner"
    )

    doses = db[DOSES_COLLECTION]
    # Race-safe guard: one dose per medication per instant, so regenerating a schedule never duplicates.
    doses.create_index([("medication_id", ASCENDING), ("scheduled_at", ASCENDING)], unique=True, name="uniq_dose")
    doses.create_index([("user_id", ASCENDING), ("local_date", ASCENDING)], name="doses_by_owner_day")
    doses.create_index([("user_id", ASCENDING), ("scheduled_at", DESCENDING)], name="doses_by_owner_time")

    appointments = db[APPOINTMENTS_COLLECTION]
    appointments.create_index(
        [("user_id", ASCENDING), ("status", ASCENDING), ("scheduled_at", ASCENDING)], name="appointments_by_owner_status"
    )
    appointments.create_index([("user_id", ASCENDING), ("scheduled_at", DESCENDING)], name="appointments_by_owner_time")
    # Race-safe duplicate guard: one SCHEDULED appointment per owner, doctor and instant.
    appointments.create_index(
        [("user_id", ASCENDING), ("doctor_key", ASCENDING), ("scheduled_at", ASCENDING)],
        unique=True,
        partialFilterExpression={"status": "scheduled"},
        name="uniq_scheduled_appointment",
    )

    notifications = db[NOTIFICATIONS_COLLECTION]
    # Race- and restart-safe: each reminder/alert exists at most once per event and recipient.
    notifications.create_index([("dedupe_key", ASCENDING)], unique=True, name="uniq_notification")
    notifications.create_index([("status", ASCENDING), ("next_attempt_at", ASCENDING)], name="notifications_due")
    notifications.create_index([("owner_user_id", ASCENDING), ("created_at", DESCENDING)], name="notifications_by_owner")
    notifications.create_index(
        [("recipient_user_id", ASCENDING), ("created_at", DESCENDING)], name="notifications_by_recipient"
    )
    db[NOTIFICATION_PREFERENCES_COLLECTION].create_index([("user_id", ASCENDING)], unique=True, name="uniq_prefs_user")

    login_failures = db[LOGIN_FAILURES_COLLECTION]
    login_failures.create_index([("email", ASCENDING), ("created_at", DESCENDING)], name="login_failures_by_email")
    login_failures.create_index([("created_at", ASCENDING)], expireAfterSeconds=24 * 3600, name="login_failures_ttl")
