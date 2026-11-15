"""ElderCare Connect API entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.security import HashingBusyError, configure_hashing
from app.db.mongodb import mongodb
from app.services.scheduler import scheduler

settings = get_settings()
configure_logging(settings.debug)
configure_hashing(settings.password_hash_concurrency)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    mongodb.connect(settings)
    scheduler.start(settings)  # background reminders; no-op when NOTIFICATIONS_ENABLED=false
    yield
    scheduler.stop()
    mongodb.close()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
    # Interactive API docs are a development aid; production does not advertise its API surface.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # Bearer tokens, not cookies: credentials mode is not needed, and only these headers are sent.
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    # FastAPI's default handler echoes the submitted value ("input"), which would send
    # passwords back in responses and logs. Return only location, message and type.
    errors = [{"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(HashingBusyError)
async def hashing_busy_handler(_: Request, __: HashingBusyError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": "The service is busy. Please try again in a moment."},
        headers={"Retry-After": "5"},
    )


@app.exception_handler(PyMongoError)
async def database_error_handler(request: Request, exc: PyMongoError) -> JSONResponse:
    logger.error("Database error on %s %s: %s", request.method, request.url.path, type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "Database is temporarily unavailable."})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


app.include_router(api_router)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    info = {"name": settings.app_name, "health": "/api/health"}
    if not settings.is_production:
        info["docs"] = "/docs"
    return info
