"""Application settings loaded from environment variables (and an optional .env file)."""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ElderCare Connect API"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    # SecretStr keeps the URI out of logs and reprs.
    mongodb_uri: SecretStr | None = None
    mongodb_db_name: str = "eldercare_connect"
    mongodb_timeout_ms: int = Field(default=5000, ge=500, le=60000)

    # --- Authentication (JWT) ---
    jwt_secret_key: SecretStr | None = None
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_issuer: str = "eldercare-connect"
    jwt_audience: str = "eldercare-connect-api"
    access_token_expire_minutes: int = Field(default=30, ge=5, le=1440)

    @field_validator("jwt_secret_key", mode="before")
    @classmethod
    def _validate_jwt_secret(cls, value: object) -> object:
        if isinstance(value, str):
            if not value.strip():
                return None
            if len(value) < MIN_JWT_SECRET_LENGTH:
                raise ValueError(f"JWT_SECRET_KEY must be at least {MIN_JWT_SECRET_LENGTH} characters.")
        return value

    @property
    def auth_configured(self) -> bool:
        return self.jwt_secret_key is not None

    # --- Invitations / linking ---
    invitation_expiry_hours: int = Field(default=72, ge=1, le=336)
    invitation_max_pending: int = Field(default=10, ge=1, le=100)
    redeem_max_failures: int = Field(default=5, ge=1, le=50)
    redeem_failure_window_minutes: int = Field(default=15, ge=1, le=1440)
    # Sign-in throttling, in three buckets per window (all return the same generic 429):
    # - one email from one IP: stops guessing without letting an attacker lock the real user out
    #   (the user signs in from a different IP);
    # - one IP across all emails: stops credential stuffing;
    # - one email across all IPs: a high backstop against distributed guessing.
    login_max_failures: int = Field(default=10, ge=3, le=100)
    login_ip_max_failures: int = Field(default=50, ge=5, le=10000)
    login_email_max_failures: int = Field(default=100, ge=10, le=10000)
    login_failure_window_minutes: int = Field(default=15, ge=1, le=1440)
    # Registrations allowed per IP per window.
    register_max_per_ip: int = Field(default=20, ge=1, le=10000)
    register_window_minutes: int = Field(default=60, ge=1, le=1440)
    # Header holding the real client IP when behind a proxy that overwrites it (e.g. CF-Connecting-IP
    # behind Cloudflare). Never use a header clients can set themselves.
    client_ip_header: str | None = None
    # Argon2 uses ~64 MiB per hash: cap concurrent hashes so a burst cannot exhaust memory.
    password_hash_concurrency: int = Field(default=4, ge=1, le=64)

    @field_validator("client_ip_header", mode="before")
    @classmethod
    def _blank_header_is_none(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @property
    def ip_limits_active(self) -> bool:
        """Per-IP limits need a trustworthy client IP. In production that means CLIENT_IP_HEADER
        must be set: behind a proxy every request may share the proxy's address, and a per-IP
        limit would then become a global lockout. Locally the socket address is the client."""
        return self.client_ip_header is not None or not self.is_production

    # Notification history is kept for this many days, then removed by a TTL index.
    notification_retention_days: int = Field(default=180, ge=7, le=3650)

    # --- Notifications (Phase 7) ---
    # Background scheduler: checks for due reminders/alerts every N seconds (no external queue).
    notifications_enabled: bool = True
    notification_interval_seconds: int = Field(default=60, ge=10, le=3600)
    missed_dose_grace_minutes: int = Field(default=60, ge=5, le=720)
    # "smtp" sends real email when SMTP_* is configured; "preview" never sends (safe local/demo mode).
    email_mode: Literal["smtp", "preview"] = "preview"
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str | None = None
    smtp_security: Literal["starttls", "ssl", "none"] = "starttls"
    smtp_timeout_seconds: int = Field(default=10, ge=1, le=60)
    # Link included in emails (never secrets). Defaults to the local frontend.
    app_base_url: str = "http://localhost:5173"

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)

    @property
    def email_delivery_active(self) -> bool:
        return self.email_mode == "smtp" and self.smtp_configured

    # Medication schedules: doses are generated this many days ahead (bounded horizon).
    dose_schedule_horizon_days: int = Field(default=7, ge=1, le=31)
    # A dose may be marked taken at most this many minutes before its scheduled time.
    dose_early_take_minutes: int = Field(default=120, ge=0, le=720)

    # --- Demo accounts ---
    # Off by default. In production a second, explicit flag is required.
    demo_accounts_enabled: bool = False
    demo_accounts_allow_production: bool = False

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == "production"

    @property
    def demo_accounts_active(self) -> bool:
        return self.demo_accounts_enabled and (not self.is_production or self.demo_accounts_allow_production)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [o.strip().rstrip("/") for o in value.split(",") if o.strip()]
        return value

    @field_validator("mongodb_uri", mode="before")
    @classmethod
    def _blank_uri_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def mongodb_configured(self) -> bool:
        return self.mongodb_uri is not None

    @model_validator(mode="after")
    def _production_guards(self) -> "Settings":
        # Fail fast on deployment mistakes instead of running with unsafe settings.
        if self.is_production:
            if "*" in self.cors_origins:
                raise ValueError("CORS_ORIGINS must list explicit origins in production (no '*').")
            if self.debug:
                raise ValueError("DEBUG must be false in production.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
