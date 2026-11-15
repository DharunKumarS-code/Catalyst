"""Idempotent demo-account provisioning.

- Creates a demo account only if its email is not yet registered.
- Never modifies an existing account (passwords are never overwritten).
- Runs only when explicitly invoked (CLI), never on application startup.
"""

import logging
from enum import Enum

from app.core.config import Settings
from app.core.security import hash_password
from app.demo.accounts import DEMO_ACCOUNTS
from app.repositories.users import EmailAlreadyRegisteredError, UserRepository
from app.schemas.user import RegisterRequest

logger = logging.getLogger(__name__)


class DemoProvisioningDisabledError(RuntimeError):
    pass


class ProvisionStatus(str, Enum):
    CREATED = "created"
    EXISTS = "already_exists"
    CONFLICT = "skipped_non_demo_account"  # email held by a real account: left untouched


def demo_disabled_reason(settings: Settings) -> str | None:
    """None when demo accounts are active, otherwise a human-readable reason."""
    if settings.demo_accounts_active:
        return None
    if not settings.demo_accounts_enabled:
        return "Demo provisioning is disabled: DEMO_ACCOUNTS_ENABLED is not true."
    return "Demo provisioning is disabled in production unless DEMO_ACCOUNTS_ALLOW_PRODUCTION=true."


def provision_demo_accounts(users: UserRepository, settings: Settings) -> dict[str, ProvisionStatus]:
    reason = demo_disabled_reason(settings)
    if reason:
        raise DemoProvisioningDisabledError(reason)

    results: dict[str, ProvisionStatus] = {}
    for account in DEMO_ACCOUNTS:
        # Run definitions through the same validation as public registration.
        req = RegisterRequest(name=account.name, email=account.email, password=account.password, role=account.role)

        existing = users.get_by_email(req.email)
        if existing is not None:
            status = ProvisionStatus.EXISTS if existing.get("is_demo") else ProvisionStatus.CONFLICT
        else:
            try:
                users.create(
                    name=req.name,
                    email=req.email,
                    password_hash=hash_password(req.password),
                    role=req.role,
                    is_demo=True,
                )
                status = ProvisionStatus.CREATED
            except EmailAlreadyRegisteredError:  # created concurrently
                status = ProvisionStatus.EXISTS
        results[req.email] = status
        logger.info("Demo account %s: %s", req.email, status.value)
    return results
