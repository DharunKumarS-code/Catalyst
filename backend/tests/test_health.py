from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.mongodb import DbHealth, MongoDB, mongodb
from app.main import app


def _skip_startup_connect(monkeypatch, settings: Settings | None = None):
    """Replace the startup connection so tests never depend on a real database."""

    def fake_connect(_settings):
        mongodb.__init__()
        mongodb._settings = settings or Settings(_env_file=None, mongodb_uri=None)

    monkeypatch.setattr(mongodb, "connect", fake_connect)


def test_health_reports_not_configured_without_uri(monkeypatch):
    _skip_startup_connect(monkeypatch)
    with TestClient(app) as client:
        res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "degraded"
    assert body["database"]["status"] == "not_configured"
    assert body["app_name"]


def test_health_reports_ok_when_database_connected(monkeypatch):
    _skip_startup_connect(monkeypatch)
    monkeypatch.setattr(mongodb, "ping", lambda: DbHealth("connected", "eldercare_connect", "ok", 12.3))
    with TestClient(app) as client:
        res = client.get("/api/health")
    body = res.json()
    assert res.status_code == 200
    assert body["status"] == "ok"
    assert body["database"]["status"] == "connected"
    assert body["database"]["latency_ms"] == 12.3


def test_unreachable_database_is_reported_not_raised():
    db = MongoDB()
    db.connect(
        Settings(
            _env_file=None,
            mongodb_uri="mongodb://127.0.0.1:1/?directConnection=true",
            mongodb_timeout_ms=500,
        )
    )
    health = db.ping()
    db.close()
    assert health.status == "disconnected"
    assert "127.0.0.1" not in health.message


def test_invalid_uri_is_handled_gracefully():
    db = MongoDB()
    db.connect(Settings(_env_file=None, mongodb_uri="not-a-mongo-uri"))
    health = db.ping()
    assert health.status == "disconnected"
    assert "not-a-mongo-uri" not in health.message


def test_cors_allows_configured_frontend_origin(monkeypatch):
    _skip_startup_connect(monkeypatch)
    with TestClient(app) as client:
        res = client.options(
            "/api/health",
            headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
        )
    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == "http://localhost:5173"
