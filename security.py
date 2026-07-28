"""
Small helper module for password hashing.

Passwords must never be stored in plain text. This uses PBKDF2-HMAC-SHA256
with a random per-password salt (both from Python's standard library, so
no extra dependency like bcrypt is needed to run the app).

The stored value has the form "<salt_hex>$<hash_hex>" so verify_password()
can re-derive the hash with the same salt and compare it safely.
"""

import hashlib
import hmac
import secrets

_ITERATIONS = 200_000


def hash_password(plain_password):
    """Hash a plain-text password for storage in the database."""
    salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        plain_password.encode("utf-8"),
        bytes.fromhex(salt),
        _ITERATIONS,
    )
    return f"{salt}${derived.hex()}"


def verify_password(plain_password, password_hash):
    """Check a plain-text password against a stored hash."""
    try:
        salt, expected_hex = password_hash.split("$", 1)
    except (ValueError, AttributeError):
        return False

    derived = hashlib.pbkdf2_hmac(
        "sha256",
        plain_password.encode("utf-8"),
        bytes.fromhex(salt),
        _ITERATIONS,
    )
    return hmac.compare_digest(derived.hex(), expected_hex)
