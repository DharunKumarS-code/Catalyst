from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.db.mongodb import mongodb
from app.schemas.health import DatabaseStatus, HealthResponse

router = APIRouter(tags=["health"])


# Sync handler: FastAPI runs it in a threadpool, so the blocking PyMongo ping
# does not block the event loop.
@router.get("/health", response_model=HealthResponse)
def health_check(settings: Settings = Depends(get_settings)) -> HealthResponse:
    db = mongodb.ping()
    return HealthResponse(
        status="ok" if db.status == "connected" else "degraded",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        timestamp=datetime.now(timezone.utc),
        database=DatabaseStatus(**asdict(db)),
    )
