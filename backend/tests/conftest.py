"""Shared fixtures. Auth tests run against a throwaway database on a local MongoDB
(TEST_MONGODB_URI, default mongodb://127.0.0.1:27017) and are skipped if it is unreachable.
They never touch the database configured in .env."""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from app.core.config import Settings, get_settings
from app.db.mongodb import MongoDB, mongodb
from app.main import app
from app.services.scheduler import scheduler

TEST_MONGODB_URI = os.getenv("TEST_MONGODB_URI", "mongodb://127.0.0.1:27017")
TEST_SECRET = "test-secret-key-that-is-long-enough-0123456789"


def _mongo_available() -> bool:
    try:
        client = MongoClient(TEST_MONGODB_URI, serverSelectionTimeoutMS=1000)
        client.admin.command("ping")
        client.close()
        return True
    except PyMongoError:
        return False


@pytest.fixture
def auth_settings() -> Settings:
    return Settings(
        _env_file=None,
        mongodb_uri=TEST_MONGODB_URI,
        mongodb_db_name=f"eldercare_test_{uuid.uuid4().hex[:12]}",
        mongodb_timeout_ms=2000,
        jwt_secret_key=TEST_SECRET,
        access_token_expire_minutes=30,
    )


@pytest.fixture
def client(auth_settings, monkeypatch):
    if not _mongo_available():
        pytest.skip(f"MongoDB not reachable at {TEST_MONGODB_URI}")

    real_connect = MongoDB.connect
    # The app's lifespan passes the .env settings; substitute the isolated test settings.
    monkeypatch.setattr(mongodb, "connect", lambda _s: real_connect(mongodb, auth_settings))
    # Tests drive notification cycles explicitly; never start the background thread.
    monkeypatch.setattr(scheduler, "start", lambda _s: None)
    app.dependency_overrides[get_settings] = lambda: auth_settings
    try:
        with TestClient(app) as c:
            yield c
            mongodb._client.drop_database(auth_settings.mongodb_db_name)
    finally:
        app.dependency_overrides.clear()
