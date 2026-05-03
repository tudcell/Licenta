"""Password hashing and verification helpers shared across layers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

SCRYPT_N = 2 ** 14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 64
SCHEME_SCRYPT = "scrypt"
SCHEME_SHA256_LEGACY = "sha256"


def hash_password(password: str) -> str:
    """Hash a password with scrypt and a random salt."""
    salt = secrets.token_bytes(16)
    derived_key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    salt_b64 = base64.b64encode(salt).decode("ascii")
    key_b64 = base64.b64encode(derived_key).decode("ascii")
    return f"{SCHEME_SCRYPT}:{SCRYPT_N}:{SCRYPT_R}:{SCRYPT_P}:{salt_b64}:{key_b64}"


def needs_rehash(stored_hash: str) -> bool:
    """Return True when a stored password hash should be upgraded."""
    if not stored_hash:
        return True
    if not stored_hash.startswith(f"{SCHEME_SCRYPT}:"):
        return True
    try:
        _, n_str, r_str, p_str, *_ = stored_hash.split(":", 5)
        return (int(n_str), int(r_str), int(p_str)) != (SCRYPT_N, SCRYPT_R, SCRYPT_P)
    except (TypeError, ValueError):
        return True


def _verify_legacy_sha256(password: str, stored_hash: str) -> bool:
    try:
        salt, hashed = stored_hash.split(":", 1)
    except (ValueError, AttributeError):
        return False
    candidate = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return hmac.compare_digest(candidate, hashed)


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against scrypt or legacy SHA-256 hashes."""
    if not stored_hash:
        return False

    if stored_hash.startswith(f"{SCHEME_SCRYPT}:"):
        try:
            _, n_str, r_str, p_str, salt_b64, key_b64 = stored_hash.split(":", 5)
            salt = base64.b64decode(salt_b64.encode("ascii"))
            expected = base64.b64decode(key_b64.encode("ascii"))
            candidate = hashlib.scrypt(
                password.encode("utf-8"),
                salt=salt,
                n=int(n_str),
                r=int(r_str),
                p=int(p_str),
                dklen=len(expected),
            )
            return hmac.compare_digest(candidate, expected)
        except (TypeError, ValueError):
            return False

    return _verify_legacy_sha256(password, stored_hash)

