"""Configuration builders for the Flask app factory."""

from __future__ import annotations

import os
import secrets
from datetime import timedelta
from typing import Iterable, List, Tuple


def parse_cors_origins(raw_value: str) -> List[str]:
    if not raw_value:
        return ["http://localhost:5000"]
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _parse_legacy_keys(raw_value: str | None) -> Tuple[str, ...]:
    """Comma-separated previous keys for read-only fallback (key rotation)."""
    if not raw_value:
        return ()
    return tuple(item.strip() for item in raw_value.split(",") if item.strip())


def _resolve_jwt_secret(is_production: bool) -> str:
    secret = os.environ.get("JWT_SECRET_KEY")
    if is_production and not secret:
        raise RuntimeError("JWT_SECRET_KEY must be set in production")
    return secret or (
        "dev-insecure-change-me-please-set-jwt-secret-key" if not is_production else secrets.token_hex(32)
    )


def _resolve_wallet_encryption_key(is_production: bool) -> str:
    """Active key used to encrypt every saved wallet.

    Production must set this explicitly. The dev default deliberately
    matches the *original* dev default that came from `JWT_SECRET_KEY`
    before the two were separated, so dev installations with wallets
    persisted under that earlier code can still decrypt without any
    extra steps.
    """
    secret = os.environ.get("WALLET_ENCRYPTION_KEY")
    if is_production and not secret:
        raise RuntimeError("WALLET_ENCRYPTION_KEY must be set in production")
    return secret or "dev-insecure-change-me-please-set-jwt-secret-key"


def build_app_config(*, is_production: bool, override: Iterable[tuple] | dict | None = None) -> dict:
    config = {
        "APP_ENV": "production" if is_production else os.environ.get("APP_ENV", "development").lower(),
        "JWT_SECRET_KEY": _resolve_jwt_secret(is_production),
        "WALLET_ENCRYPTION_KEY": _resolve_wallet_encryption_key(is_production),
        "WALLET_ENCRYPTION_LEGACY_KEYS": _parse_legacy_keys(os.environ.get("WALLET_ENCRYPTION_LEGACY_KEYS")),
        "JWT_ACCESS_TOKEN_EXPIRES": timedelta(hours=1),
        "JWT_REFRESH_TOKEN_EXPIRES": timedelta(days=30),
        "JWT_TOKEN_LOCATION": ["headers"],
        "JWT_HEADER_NAME": "Authorization",
        "JWT_HEADER_TYPE": "Bearer",
        "MAX_CONTENT_LENGTH": 16 * 1024 * 1024,
    }
    if override:
        if isinstance(override, dict):
            config.update(override)
        else:
            config.update(dict(override))
    return config
