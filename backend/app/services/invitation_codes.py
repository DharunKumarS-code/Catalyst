"""Invitation code generation and hashing.

Codes are 16 characters from Crockford's Base32 alphabet (80 bits of entropy from
`secrets`), shown as XXXX-XXXX-XXXX-XXXX so they are easy to read aloud. Only the
SHA-256 hash is stored: with 80 random bits a fast hash is sufficient, and it allows
an indexed lookup (a salted slow hash would not).
"""

import hashlib
import re
import secrets

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford Base32: no I, L, O, U
CODE_LENGTH = 16
_AMBIGUOUS = str.maketrans({"O": "0", "I": "1", "L": "1"})


def generate_code() -> str:
    raw = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
    return "-".join(raw[i : i + 4] for i in range(0, CODE_LENGTH, 4))


def normalize_code(value: str) -> str | None:
    """Accept any case, spaces or dashes, and commonly confused letters. None if malformed."""
    cleaned = re.sub(r"[\s-]", "", value).upper().translate(_AMBIGUOUS)
    if len(cleaned) != CODE_LENGTH or any(c not in ALPHABET for c in cleaned):
        return None
    return cleaned


def hash_code(normalized: str) -> str:
    return hashlib.sha256(normalized.encode("ascii")).hexdigest()
