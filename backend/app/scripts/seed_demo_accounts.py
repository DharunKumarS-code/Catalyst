"""Create the demo accounts and their sample data (idempotent).

Usage (from backend/, with DEMO_ACCOUNTS_ENABLED=true):
    python -m app.scripts.seed_demo_accounts

Exit codes: 0 success, 1 disabled by configuration, 2 database unavailable.
"""

import sys

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.mongodb import mongodb
from app.demo.sample_data import provision_demo_sample_data
from app.demo.provisioning import demo_disabled_reason, provision_demo_accounts
from app.repositories.users import UserRepository


def main() -> int:
    settings = get_settings()
    configure_logging(settings.debug)

    reason = demo_disabled_reason(settings)
    if reason:
        print(reason, file=sys.stderr)
        return 1

    mongodb.connect(settings)
    try:
        if mongodb.ping().status != "connected":
            print("Database is not reachable; no accounts were created.", file=sys.stderr)
            return 2
        mongodb.ensure_indexes()
        results = provision_demo_accounts(UserRepository(mongodb.db), settings)
        samples = provision_demo_sample_data(
            mongodb.db,
            horizon_days=settings.dose_schedule_horizon_days,
            early_minutes=settings.dose_early_take_minutes,
        )
    finally:
        mongodb.close()

    for email, status in results.items():
        print(f"{status.value:<26} {email}")
    for item, outcome in samples.items():
        print(f"{outcome:<26} {item}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
