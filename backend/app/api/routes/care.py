"""Caretaker / family monitoring dashboard (read-only).

One request returns a summary of every profile the member is ACTIVELY linked to, replacing
four requests per profile from the browser. It exposes nothing beyond what the existing
/linked-profiles/{id}/... endpoints already return to the same member.
"""

from fastapi import APIRouter, Depends

from app.api.deps import get_appointment_repository, get_profile_repository, get_relationship_repository
from app.api.medication_access import get_medication_service, member_user
from app.core.time import utc_now
from app.db.ids import to_object_id
from app.repositories.appointments import AppointmentRepository
from app.repositories.profiles import ProfileRepository
from app.repositories.relationships import RelationshipRepository
from app.schemas.care import CareDashboard
from app.schemas.user import UserPublic
from app.services.care_dashboard import CareDashboardService
from app.services.medications import MedicationService

router = APIRouter(tags=["care dashboard"])


@router.get("/care-dashboard", response_model=CareDashboard)
def care_dashboard(
    user: UserPublic = Depends(member_user),
    relationships: RelationshipRepository = Depends(get_relationship_repository),
    profiles: ProfileRepository = Depends(get_profile_repository),
    medications: MedicationService = Depends(get_medication_service),
    appointments: AppointmentRepository = Depends(get_appointment_repository),
) -> CareDashboard:
    service = CareDashboardService(relationships, profiles, medications, appointments)
    return service.build(to_object_id(user.id), user.is_demo, utc_now())
