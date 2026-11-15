"""Shared helpers for API tests."""

import itertools

PASSWORD = "SafePassword123"
_counter = itertools.count()

PROFILE = {
    "full_name": "Margaret Smith",
    "date_of_birth": "1941-03-12",
    "phone": "+44 20 7946 0958",
    "address": "12 Garden Lane, Springfield",
    "emergency_contact_name": "Tom Smith",
    "emergency_contact_phone": "07700 900123",
    "notes": "Prefers morning visits.",
}


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def new_user(client, role: str, name: str | None = None) -> dict:
    """Register a user; returns {'token', 'user', 'headers'}."""
    n = next(_counter)
    res = client.post(
        "/api/auth/register",
        json={
            "name": name or f"{role.title()} {n}",
            "email": f"{role}{n}@example.com",
            "password": PASSWORD,
            "role": role,
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    return {"token": body["access_token"], "user": body["user"], "headers": bearer(body["access_token"])}


def create_profile(client, elderly: dict, **overrides) -> dict:
    res = client.post("/api/profiles/me", json={**PROFILE, **overrides}, headers=elderly["headers"])
    assert res.status_code == 201, res.text
    return res.json()


def invite(client, elderly: dict, role: str) -> dict:
    res = client.post("/api/invitations", json={"role": role}, headers=elderly["headers"])
    assert res.status_code == 201, res.text
    return res.json()


def redeem(client, member: dict, code: str):
    return client.post("/api/invitations/redeem", json={"code": code}, headers=member["headers"])
