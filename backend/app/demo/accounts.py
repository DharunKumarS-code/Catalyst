"""Demo account definitions (sample data only).

These credentials are intentionally public: they are shown on the login page when
demo accounts are enabled. Demo users are flagged `is_demo` in the database and
must never be granted access to real user data (see `app.api.deps`).
"""

from dataclasses import dataclass

from app.schemas.user import Role


@dataclass(frozen=True)
class DemoAccount:
    role: Role
    name: str
    email: str
    password: str


DEMO_ACCOUNTS: tuple[DemoAccount, ...] = (
    DemoAccount(Role.ELDERLY, "Demo Elderly User", "elderly.demo@eldercare.com", "ElderDemo2026!"),
    DemoAccount(Role.CARETAKER, "Demo Caretaker", "caretaker.demo@eldercare.com", "CareDemo2026!"),
    DemoAccount(Role.FAMILY_MEMBER, "Demo Family Member", "family.demo@eldercare.com", "FamilyDemo2026!"),
)

DEMO_EMAILS: frozenset[str] = frozenset(a.email for a in DEMO_ACCOUNTS)


def is_reserved_demo_email(email: str) -> bool:
    return email.strip().lower() in DEMO_EMAILS
