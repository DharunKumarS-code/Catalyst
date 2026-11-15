"""MongoDB connection management using PyMongo.

A single MongoClient is created at application startup and reused. Connection
failures never crash the app; they are reported through `ping()` and the health endpoint.
Error messages returned to clients never include the URI, hosts or credentials.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Literal

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConfigurationError, OperationFailure, PyMongoError

from app.core.config import Settings
from app.db.indexes import ensure_indexes

logger = logging.getLogger(__name__)

DbStatus = Literal["connected", "disconnected", "not_configured"]


@dataclass(frozen=True)
class DbHealth:
    status: DbStatus
    name: str
    message: str
    latency_ms: float | None = None


class MongoDB:
    def __init__(self) -> None:
        self._client: MongoClient | None = None
        self._settings: Settings | None = None
        self._init_error: str | None = None
        self._indexes_ready = False

    def connect(self, settings: Settings) -> None:
        """Create the client and verify connectivity. Never raises."""
        self._settings = settings
        self._init_error = None

        if not settings.mongodb_configured:
            logger.warning("MONGODB_URI is not set; database features are disabled.")
            return

        try:
            self._client = MongoClient(
                settings.mongodb_uri.get_secret_value(),
                serverSelectionTimeoutMS=settings.mongodb_timeout_ms,
                connectTimeoutMS=settings.mongodb_timeout_ms,
                appname=settings.app_name,
                tz_aware=True,  # return UTC-aware datetimes so API timestamps carry "+00:00"
            )
        except (ConfigurationError, ValueError, TypeError) as exc:
            # Invalid URI format, unresolvable SRV record, etc. Log the type only, never the URI.
            self._init_error = "Invalid MongoDB configuration (check MONGODB_URI)."
            logger.error("MongoDB client initialisation failed: %s", type(exc).__name__)
            return

        health = self.ping()
        if health.status == "connected":
            logger.info("Connected to MongoDB database '%s' (%.1f ms).", health.name, health.latency_ms)
            self.ensure_indexes()
        else:
            logger.error("MongoDB is unreachable at startup: %s", health.message)

    def ensure_indexes(self) -> bool:
        """Create required indexes once per process. Returns True when indexes are in place."""
        if self._indexes_ready:
            return True
        try:
            ensure_indexes(self.db)
        except (PyMongoError, RuntimeError) as exc:
            logger.warning("Could not ensure MongoDB indexes: %s", type(exc).__name__)
            return False
        self._indexes_ready = True
        return True

    def close(self) -> None:
        self._indexes_ready = False
        if self._client is not None:
            self._client.close()
            self._client = None
            logger.info("MongoDB connection closed.")

    @property
    def db(self) -> Database:
        """Return the application database. Raises RuntimeError if not initialised."""
        if self._client is None or self._settings is None:
            raise RuntimeError("MongoDB client is not initialised.")
        return self._client[self._settings.mongodb_db_name]

    def ping(self) -> DbHealth:
        name = self._settings.mongodb_db_name if self._settings else ""

        if self._settings is None or not self._settings.mongodb_configured:
            return DbHealth("not_configured", name, "MONGODB_URI is not configured on the server.")
        if self._client is None:
            return DbHealth("disconnected", name, self._init_error or "MongoDB client is not initialised.")

        start = time.perf_counter()
        try:
            self._client[name].command("ping")
        except OperationFailure as exc:
            logger.warning("MongoDB ping rejected (code=%s).", exc.code)
            return DbHealth("disconnected", name, "Database rejected the request (check credentials and permissions).")
        except PyMongoError as exc:
            logger.warning("MongoDB ping failed: %s", type(exc).__name__)
            return DbHealth("disconnected", name, "Unable to reach the database server.")
        latency = round((time.perf_counter() - start) * 1000, 1)
        return DbHealth("connected", name, "Database connection is healthy.", latency)


mongodb = MongoDB()
