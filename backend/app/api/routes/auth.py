from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database

from app.api.deps import get_auth_settings, get_current_user, get_db, get_user_repository
from app.core.config import Settings, get_settings
from app.core.security import create_access_token, hash_password, password_needs_rehash, verify_password
from app.core.time import utc_now
from app.demo.accounts import DEMO_ACCOUNTS, is_reserved_demo_email
from app.repositories.login_attempts import LoginAttemptRepository
from app.repositories.users import EmailAlreadyRegisteredError, UserRepository
from app.schemas.user import DemoAccountInfo, LoginRequest, RegisterRequest, TokenResponse, UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])

INVALID_CREDENTIALS = "Invalid email or password."
TOO_MANY_ATTEMPTS = "Too many sign-in attempts. Please wait a few minutes and try again."


def _token_response(doc: dict, settings: Settings) -> TokenResponse:
    user = UserPublic.from_document(doc)
    token, expires_in = create_access_token(user.id, user.role.value, settings)
    return TokenResponse(access_token=token, expires_in=expires_in, user=user)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    settings: Settings = Depends(get_auth_settings),
    users: UserRepository = Depends(get_user_repository),
) -> TokenResponse:
    # Demo addresses are reserved so nobody can claim them with their own password.
    if is_reserved_demo_email(body.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    # The unique index is the real guard; a duplicate insert raises EmailAlreadyRegisteredError.
    try:
        doc = users.create(
            name=body.name,
            email=body.email,
            password_hash=hash_password(body.password),
            role=body.role,
        )
    except EmailAlreadyRegisteredError:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.") from None
    return _token_response(doc, settings)


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    settings: Settings = Depends(get_auth_settings),
    users: UserRepository = Depends(get_user_repository),
    db: Database = Depends(get_db),
) -> TokenResponse:
    # Throttle guessing per email (applies whether or not the account exists, so it reveals nothing).
    attempts, now = LoginAttemptRepository(db), utc_now()
    window = timedelta(minutes=settings.login_failure_window_minutes)
    if attempts.count_recent(body.email, now, window) >= settings.login_max_failures:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, TOO_MANY_ATTEMPTS)
    doc = users.get_by_email(body.email)
    # verify_password runs a full Argon2 check even when the user is missing (timing-safe).
    # Demo accounts have public passwords: they can sign in only while demo mode is active.
    if not verify_password(body.password, doc["password_hash"] if doc else None) or (
        doc.get("is_demo") and not settings.demo_accounts_active
    ):
        attempts.record(body.email, now)
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, INVALID_CREDENTIALS, headers={"WWW-Authenticate": "Bearer"}
        )
    attempts.clear(body.email)
    if password_needs_rehash(doc["password_hash"]):
        users.update_password_hash(doc["_id"], hash_password(body.password))
    return _token_response(doc, settings)


@router.get("/demo-accounts", response_model=list[DemoAccountInfo])
def demo_accounts(
    settings: Settings = Depends(get_settings),
    users: UserRepository = Depends(get_user_repository),
) -> list[DemoAccountInfo]:
    """Public demo credentials, only when demo accounts are enabled AND provisioned.
    Returns 404 when the feature is disabled so it is invisible in normal deployments."""
    if not settings.demo_accounts_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    provisioned = {u["email"] for u in users.find_demo_users([a.email for a in DEMO_ACCOUNTS])}
    return [
        DemoAccountInfo(role=a.role, email=a.email, password=a.password)
        for a in DEMO_ACCOUNTS
        if a.email in provisioned
    ]


@router.get("/me", response_model=UserPublic)
def me(user: UserPublic = Depends(get_current_user)) -> UserPublic:
    return user
