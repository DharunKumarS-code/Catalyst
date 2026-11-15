from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class DatabaseStatus(BaseModel):
    status: Literal["connected", "disconnected", "not_configured"]
    name: str
    message: str
    latency_ms: float | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    app_name: str
    version: str
    environment: str
    timestamp: datetime
    database: DatabaseStatus
