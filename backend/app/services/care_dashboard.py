"""Read-only monitoring summary for caretakers and family members.

Authorization is the same as every /linked-profiles endpoint: only ACTIVE relationships of
the signed-in member, with matching demo flags, evaluated on this request. Data for all linked
profiles is loaded with a fixed number of batched queries (no per-profile query loop), and
adherence uses the shared eligibility rule and `period()` from the medication module.
"""

from datetime import datetime, timedelta

from bson import ObjectId

from app.repositories.appointments import AppointmentRepository
from app.repositories.profiles import ProfileRepository
from app.repositories.relationships import RelationshipRepository
from app.schemas.care import ActivityItem, CareDashboard, CareProfileSummary
from app.schemas.medication import AdherencePeriod
from app.schemas.user import UserPublic
from app.services.appointments import AppointmentService
from app.services.medications import MedicationService, Scope, member_scope_for, period

UPCOMING_APPOINTMENTS = 3
ACTIVITY_DAYS = 7
ACTIVITY_PER_PROFILE = 8


class CareDashboardService:
    def __init__(
        self,
        relationships: RelationshipRepository,
        profiles: ProfileRepository,
        medications: MedicationService,
        appointments: AppointmentRepository,
    ) -> None:
        self.relationships = relationships
        self.profiles = profiles
        self.medications = medications
        self.appointments = AppointmentService(appointments)

    def build(
        self, member_id: ObjectId, member_is_demo: bool, now: datetime, member: UserPublic | None = None
    ) -> CareDashboard:
        rels = self.relationships.list_active_for_member(member_id, is_demo=member_is_demo)
        found = self.profiles.get_many([r["profile_id"] for r in rels])
        linked = [
            (r, found[r["profile_id"]])
            for r in rels
            if r["profile_id"] in found and bool(found[r["profile_id"]].get("is_demo")) == member_is_demo
        ]
        if not linked:
            return CareDashboard(generated_at=now, profiles=[])

        # The same per-relationship rule as the dose endpoints: only a caretaker with the owner's grant may record.
        scopes = {
            p["user_id"]: member_scope_for(r, p, member_id, member.name)
            if member
            else Scope(owner_id=p["user_id"], profile=p, can_modify=False)
            for r, p in linked
        }
        owners = list(scopes)

        meds_all = self.medications.meds.list_for_users(owners)
        meds_by_id = {m["_id"]: m for m in meds_all}
        for owner, scope in scopes.items():  # pure planning; writes only when doses are missing
            active = [m for m in meds_all if m["user_id"] == owner and m["status"] == "active"]
            self.medications.ensure_schedule(scope, now, active)

        owner_days = [(owner, scope.today(now).isoformat()) for owner, scope in scopes.items()]
        doses_repo = self.medications.doses
        counts = doses_repo.counts_for_owner_days(owner_days, now)
        today_docs = doses_repo.for_owner_days(owner_days)
        upcoming = self.appointments.repo.upcoming_for_users(owners, now, UPCOMING_APPOINTMENTS)
        since = now - timedelta(days=ACTIVITY_DAYS)
        recorded = doses_repo.recently_recorded(owners, since, ACTIVITY_PER_PROFILE * len(owners))
        updated = self.appointments.repo.recently_updated(owners, since, ACTIVITY_PER_PROFILE * len(owners))

        summaries = []
        for rel, profile in linked:
            owner = profile["user_id"]
            scope = scopes[owner]
            day = scope.today(now).isoformat()
            doses = self.medications.dose_views(
                scope, [d for d in today_docs if d["user_id"] == owner], now, meds=meds_by_id
            )
            appts, appt_total = upcoming.get(owner, ([], 0))
            summaries.append(
                CareProfileSummary(
                    profile_id=str(profile["_id"]),
                    relationship_id=str(rel["_id"]),
                    role=rel["role"],
                    connected_at=rel["created_at"],
                    can_record_doses=scope.may_record,
                    full_name=profile["full_name"],
                    date_of_birth=profile.get("date_of_birth"),
                    phone=profile.get("phone"),
                    emergency_contact_name=profile["emergency_contact_name"],
                    emergency_contact_phone=profile["emergency_contact_phone"],
                    timezone=scope.timezone_name,
                    local_date=day,
                    is_demo=bool(profile.get("is_demo")),
                    active_medications=sum(1 for m in meds_all if m["user_id"] == owner and m["status"] == "active"),
                    today=AdherencePeriod(**period(day, day, [counts.get((owner, day), {})])),
                    today_doses=doses,
                    next_dose=next((d for d in doses if d.status == "pending" and not d.is_due), None),
                    upcoming_appointments=[self.appointments.view(scope, a, now) for a in appts],
                    upcoming_appointment_count=appt_total,
                    recent_activity=self._activity(owner, recorded, updated, meds_by_id),
                )
            )
        return CareDashboard(generated_at=now, profiles=summaries)

    @staticmethod
    def _activity(owner: ObjectId, recorded: list[dict], updated: list[dict], meds: dict) -> list[ActivityItem]:
        items = []
        for d in recorded:
            med = meds.get(d["medication_id"])
            if d["user_id"] != owner or med is None:
                continue
            items.append(
                ActivityItem(
                    kind=f"dose_{d['status']}",
                    at=d["status_changed_at"],
                    subject=f"{med['name']} {med['dosage']}",
                    local_date=d["local_date"],
                    local_time=d["local_time"],
                )
            )
        for a in updated:
            if a["user_id"] != owner:
                continue
            items.append(
                ActivityItem(
                    kind=f"appointment_{a['status']}",
                    at=a["status_changed_at"],
                    subject=a["doctor_name"],
                    local_date=a["appointment_date"],
                    local_time=a["appointment_time"],
                    place=a["clinic_name"],
                )
            )
        items.sort(key=lambda i: i.at, reverse=True)
        return items[:ACTIVITY_PER_PROFILE]
