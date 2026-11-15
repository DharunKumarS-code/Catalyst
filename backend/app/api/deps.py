"""Reusable FastAPI dependencies: database access, authentication and role authorization."""

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pymongo.database import Database

from app.core.config import Settings, get_settings
from app.core.security import TokenError, decode_access_token
from app.db.mongodb import mongodb
from app.repositories.appointments import AppointmentRepository
from app.repositories.doses import DoseRepository
from app.repositories.invitations import InvitationRepository, RedemptionFailureRepository
from app.repositories.medications import MedicationRepository
from app.repositories.profiles import ProfileRepository
from app.repositories.relationships import RelationshipRepository
from app.repositories.users import UserRepository
from app.schemas.user import Role, UserPublic

# auto_error=False so we control the 401 response body and WWW-Authenticate header.
_bearer = HTTPBearer(auto_error=False, description="JWT access token from /api/auth/login")


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_db() -> Database:
    try:
        db = mongodb.db
    except RuntimeError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database is not available.") from None
    mongodb.ensure_indexes()  # no-op after first success; self-heals if DB was down at startup
    return db


def get_user_repository(db: Database = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


def get_profile_repository(db: Database = Depends(get_db)) -> ProfileRepository:
    return ProfileRepository(db)


def get_invitation_repository(db: Database = Depends(get_db)) -> InvitationRepository:
    return InvitationRepository(db)


def get_failure_repository(db: Database = Depends(get_db)) -> RedemptionFailureRepository:
    return RedemptionFailureRepository(db)


def get_relationship_repository(db: Database = Depends(get_db)) -> RelationshipRepository:
    return RelationshipRepository(db)


def get_medication_repository(db: Database = Depends(get_db)) -> MedicationRepository:
    return MedicationRepository(db)


def get_dose_repository(db: Database = Depends(get_db)) -> DoseRepository:
    return DoseRepository(db)


def get_appointment_repository(db: Database = Depends(get_db)) -> AppointmentRepository:
    return AppointmentRepository(db)


def client_ip(request: Request, settings: Settings = Depends(get_settings)) -> str | None:
    """The caller's IP for rate limiting, or None when it cannot be trusted (per-IP limits off).
    With CLIENT_IP_HEADER set (a header the proxy overwrites, e.g. CF-Connecting-IP), that
    header is used; otherwise the socket address."""
    if not settings.ip_limits_active:
        return None
    if settings.client_ip_header:
        value = request.headers.get(settings.client_ip_header, "").split(",")[0].strip()
        if value:
            return value[:64]
    return request.client.host if request.client else None


def get_auth_settings(settings: Settings = Depends(get_settings)) -> Settings:
    if not settings.auth_configured:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication is not configured on the server.")
    return settings


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_auth_settings),
    users: UserRepository = Depends(get_user_repository),
) -> UserPublic:
    """Identity comes only from a verified token; role is read from the database record,
    never from client input, so role changes take effect immediately."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Not authenticated.")
    try:
        payload = decode_access_token(credentials.credentials, settings)
    except TokenError as exc:
        raise _unauthorized(str(exc)) from None

    user = users.get_by_id(payload["sub"])
    if user is None or (user.get("is_demo") and not settings.demo_accounts_active):
        # Disabling demo mode immediately invalidates outstanding demo-account tokens.
        raise _unauthorized("Invalid authentication token.")
    return UserPublic.from_document(user)


DEMO_FORBIDDEN = "Demo accounts cannot access real user data."


def get_non_demo_user(user: UserPublic = Depends(get_current_user)) -> UserPublic:
    """Use on every endpoint that reads or changes real user data: demo accounts are refused."""
    if user.is_demo:
        raise HTTPException(status.HTTP_403_FORBIDDEN, DEMO_FORBIDDEN)
    return user


def require_roles(*allowed: Role, allow_demo: bool = True) -> Callable[..., UserPublic]:
    """Dependency factory: `Depends(require_roles(Role.CARETAKER, Role.FAMILY_MEMBER))`.

    Pass `allow_demo=False` for endpoints that expose real user data.
    """
    if not allowed:
        raise ValueError("require_roles() needs at least one role.")
    allowed_set = frozenset(allowed)

    def dependency(user: UserPublic = Depends(get_current_user)) -> UserPublic:
        if user.role not in allowed_set:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission to access this resource.")
        if user.is_demo and not allow_demo:
            raise HTTPException(status.HTTP_403_FORBIDDEN, DEMO_FORBIDDEN)
        return user

    return dependency
