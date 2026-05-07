"""Configuration builders for the Flask app factory."""

from __future__ import annotations

import os
import secrets
from datetime import timedelta
from typing import Iterable, List


def parse_cors_origins(raw_value: str) -> List[str]:
    if not raw_value:
        return ["http://localhost:5000"]
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _resolve_jwt_secret(is_production: bool) -> str:
    secret = os.environ.get("JWT_SECRET_KEY")
    if is_production and not secret:
        raise RuntimeError("JWT_SECRET_KEY must be set in production")
    return secret or (
        "dev-insecure-change-me-please-set-jwt-secret-key" if not is_production else secrets.token_hex(32)
    )


def _resolve_wallet_encryption_key(is_production: bool) -> str:
    """Wallet encryption key is independent of the JWT secret.

    In production it must be set explicitly. In development a stable
    per-process random key is generated so that wallets persisted in this
    run can still be decrypted within the same run.
    """
    secret = os.environ.get("WALLET_ENCRYPTION_KEY")
    if is_production and not secret:
        raise RuntimeError("WALLET_ENCRYPTION_KEY must be set in production")
    return secret or "dev-insecure-wallet-key-change-me-please"


def build_app_config(*, is_production: bool, override: Iterable[tuple] | dict | None = None) -> dict:
    config = {
        "APP_ENV": "production" if is_production else os.environ.get("APP_ENV", "development").lower(),
        "JWT_SECRET_KEY": _resolve_jwt_secret(is_production),
        "WALLET_ENCRYPTION_KEY": _resolve_wallet_encryption_key(is_production),
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
