"""Role-scoped portal endpoints.

Phase 2 placeholders that demonstrate and enforce role-based access. Later phases
(medication management, care coordination) will add real data behind these areas.
"""

from fastapi import APIRouter, Depends

from app.api.deps import require_roles
from app.schemas.user import Role, UserPublic

router = APIRouter(prefix="/portal", tags=["portal"])


def _area(area: str, user: UserPublic, message: str) -> dict:
    # Demo users only ever receive sample content; real-data endpoints use allow_demo=False.
    return {"area": area, "role": user.role, "message": message, "demo": user.is_demo}


@router.get("/elderly")
def elderly_portal(user: UserPublic = Depends(require_roles(Role.ELDERLY))) -> dict:
    return _area("elderly", user, "Your personal care space. Reminders will appear here.")


@router.get("/caretaker")
def caretaker_portal(user: UserPublic = Depends(require_roles(Role.CARETAKER))) -> dict:
    return _area("caretaker", user, "Your caretaker workspace. Assigned care tasks will appear here.")


@router.get("/family")
def family_portal(user: UserPublic = Depends(require_roles(Role.FAMILY_MEMBER))) -> dict:
    return _area("family", user, "Your family overview. Updates about your loved one will appear here.")


@router.get("/care-team")
def care_team(user: UserPublic = Depends(require_roles(Role.CARETAKER, Role.FAMILY_MEMBER))) -> dict:
    return _area("care-team", user, "Shared space for caretakers and family members.")
