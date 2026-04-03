"""
Authentication utilities for password hashing and verification.
"""

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
    """
    Hash password with scrypt + random salt.

    Returns:
        Encoded hash in format "scrypt:n:r:p:salt_b64:key_b64"
    """
    salt = secrets.token_bytes(16)
    derived_key = hashlib.scrypt(
        password.encode('utf-8'),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    salt_b64 = base64.b64encode(salt).decode('ascii')
    key_b64 = base64.b64encode(derived_key).decode('ascii')
    return f"{SCHEME_SCRYPT}:{SCRYPT_N}:{SCRYPT_R}:{SCRYPT_P}:{salt_b64}:{key_b64}"


def _verify_legacy_sha256(password: str, stored_hash: str) -> bool:
    try:
        salt, hashed = stored_hash.split(':', 1)
        candidate = hashlib.sha256((salt + password).encode('utf-8')).hexdigest()
        return hmac.compare_digest(candidate, hashed)
    except (ValueError, AttributeError):
        return False


def verify_password(password: str, stored_hash: str) -> bool:
    """Verifies password against either scrypt or legacy SHA-256 hashes."""
    if not stored_hash:
        return False

    if stored_hash.startswith(f"{SCHEME_SCRYPT}:"):
        try:
            _, n_str, r_str, p_str, salt_b64, key_b64 = stored_hash.split(':', 5)
            salt = base64.b64decode(salt_b64.encode('ascii'))
            expected = base64.b64decode(key_b64.encode('ascii'))
            candidate = hashlib.scrypt(
                password.encode('utf-8'),
                salt=salt,
                n=int(n_str),
                r=int(r_str),
                p=int(p_str),
                dklen=len(expected),
            )
            return hmac.compare_digest(candidate, expected)
        except (ValueError, TypeError, hashlib.ScryptError):
            return False

    return _verify_legacy_sha256(password, stored_hash)
