from fastapi import APIRouter

from app.api.routes import (
    appointments,
    auth,
    care,
    health,
    invitations,
    medications,
    notifications,
    portal,
    profiles,
    relationships,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(portal.router)
api_router.include_router(profiles.router)
api_router.include_router(invitations.router)
api_router.include_router(relationships.router)
api_router.include_router(medications.router)
api_router.include_router(appointments.router)
api_router.include_router(care.router)
api_router.include_router(notifications.router)
