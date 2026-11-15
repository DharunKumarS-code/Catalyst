"""Idempotent demo sample data: a demo elderly profile, sample medications, and links from
the demo caretaker/family member to that profile.

Everything here belongs to `is_demo` accounts and is stored with `is_demo=True`, so it is
invisible to real users (and real data is invisible to demo users). Existing demo data is
never modified: each item is created only if it is missing.
"""

from datetime import datetime, timedelta

from pymongo.database import Database

from app.core.time import DEFAULT_TIMEZONE, utc_now
from app.demo.accounts import DEMO_ACCOUNTS
from app.repositories.appointments import AppointmentRepository
from app.repositories.doses import DoseRepository
from app.repositories.medications import MedicationRepository
from app.repositories.profiles import ProfileAlreadyExistsError, ProfileRepository
from app.repositories.relationships import RelationshipExistsError, RelationshipRepository
from app.repositories.users import UserRepository
from app.schemas.appointment import AppointmentIn
from app.schemas.medication import MedicationIn
from app.schemas.profile import ProfileIn
from app.schemas.user import Role
from app.services.appointments import AppointmentService
from app.services.medications import MedicationService, Scope
from app.services.scheduling import local_midnight_utc

SAMPLE_NOTE = "Demo sample data, not real medical advice."

DEMO_PROFILE = ProfileIn(
    full_name="Demo Elderly User",
    emergency_contact_name="Demo Family Member",
    emergency_contact_phone="+44 20 7946 0000",
    notes="Sample profile for demonstrations. Not a real person.",
    timezone=DEFAULT_TIMEZONE,
)


def _sample_medications(start: str) -> list[MedicationIn]:
    common = {"start_date": start, "prescribing_doctor": "Dr. Demo (sample)"}
    return [
        MedicationIn(
            name="Vitamin D (sample)",
            dosage="1000 IU",
            frequency="once_daily",
            times=["09:00"],
            instructions=f"Take with breakfast. {SAMPLE_NOTE}",
            **common,
        ),
        MedicationIn(
            name="Metformin (sample)",
            dosage="500 mg",
            frequency="twice_daily",
            times=["08:00", "20:00"],
            instructions=f"Take with food. {SAMPLE_NOTE}",
            **common,
        ),
        MedicationIn(
            name="Amlodipine (sample)",
            dosage="5 mg",
            frequency="once_daily",
            times=["21:00"],
            instructions=SAMPLE_NOTE,
            **common,
        ),
    ]


def provision_demo_sample_data(
    db: Database, *, horizon_days: int, early_minutes: int, now: datetime | None = None
) -> dict[str, str]:
    now = now or utc_now()
    users = UserRepository(db)
    profiles = ProfileRepository(db)
    relationships = RelationshipRepository(db)
    results: dict[str, str] = {}

    accounts = {a.role: users.get_by_email(a.email) for a in DEMO_ACCOUNTS}
    elderly = accounts.get(Role.ELDERLY)
    if elderly is None or not elderly.get("is_demo"):
        return {"sample_data": "skipped (demo elderly account missing)"}

    profile = profiles.get_by_user(elderly["_id"])
    if profile is None:
        try:
            profile = profiles.create(elderly["_id"], DEMO_PROFILE.to_document(), is_demo=True)
            results["demo profile"] = "created"
        except ProfileAlreadyExistsError:
            profile = profiles.get_by_user(elderly["_id"])
            results["demo profile"] = "already_exists"
    else:
        results["demo profile"] = "already_exists"

    service = MedicationService(
        MedicationRepository(db), DoseRepository(db), horizon_days=horizon_days, early_minutes=early_minutes
    )
    scope = Scope(owner_id=elderly["_id"], profile=profile, can_modify=True)
    if service.meds.list_for_user(elderly["_id"]):
        results["sample medications"] = "already_exist"
    else:
        # Courses start yesterday so the adherence summary has a little history to show.
        yesterday = scope.today(now) - timedelta(days=1)
        since = local_midnight_utc(yesterday, scope.tz)
        for med in _sample_medications(yesterday.isoformat()):
            service.create(scope, med.to_document(), now, schedule_from=since)
        past = service.doses.for_day(elderly["_id"], yesterday.isoformat())
        for i, dose in enumerate(past):  # yesterday: all taken except the last dose, missed
            service.doses.transition(
                dose["_id"],
                elderly["_id"],
                expected="pending",
                new="missed" if i == len(past) - 1 else "taken",
                now=dose["scheduled_at"] + timedelta(minutes=10),
                by=elderly["_id"],
            )
        results["sample medications"] = "created"

    appointments = AppointmentService(AppointmentRepository(db))
    if appointments.repo.count(elderly["_id"]):
        results["sample appointments"] = "already_exist"
    else:
        _create_sample_appointments(appointments, scope, now)
        results["sample appointments"] = "created"

    for role in (Role.CARETAKER, Role.FAMILY_MEMBER):
        member = accounts.get(role)
        if member is None or not member.get("is_demo"):
            continue
        key = f"demo link ({role.value})"
        if relationships.active_exists(profile["_id"], member["_id"]):
            results[key] = "already_exists"
            continue
        try:
            relationships.create(
                profile_id=profile["_id"],
                elderly_user_id=elderly["_id"],
                member_user_id=member["_id"],
                role=role.value,
                invitation_id=None,
                now=now,
                is_demo=True,
            )
            results[key] = "created"
        except RelationshipExistsError:
            results[key] = "already_exists"
    return results


def _create_sample_appointments(service: AppointmentService, scope: Scope, now: datetime) -> None:
    today = scope.today(now)

    def appt(days: int, time: str, **fields) -> AppointmentIn:
        return AppointmentIn(
            appointment_date=today + timedelta(days=days), appointment_time=time, notes=SAMPLE_NOTE, **fields
        )

    service.create(
        scope,
        appt(
            3,
            "10:30",
            doctor_name="Dr. Asha Rao (sample)",
            specialization="Cardiology",
            clinic_name="Sample Heart Clinic",
            clinic_address="1 Demo Street, Sampletown",
            appointment_type="Check-up",
            reason="Blood pressure review",
        ),
        now,
    )
    service.create(
        scope,
        appt(
            12,
            "14:00",
            doctor_name="Dr. Ben Lee (sample)",
            specialization="Ophthalmology",
            clinic_name="Sample Eye Hospital",
            appointment_type="Eye test",
            reason="Annual eye examination",
        ),
        now,
    )
    # A past visit, recorded as completed, so the history is not empty.
    booked = now - timedelta(days=14)
    past = service.create(
        scope,
        appt(
            -7,
            "09:00",
            doctor_name="Dr. Chen Patel (sample)",
            specialization="General practice",
            clinic_name="Sample Family Practice",
            appointment_type="Follow-up",
            reason="Medication review",
        ),
        booked,
    )
    service.repo.transition(past["_id"], scope.owner_id, new="completed", now=now)
