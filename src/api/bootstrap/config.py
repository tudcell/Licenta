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


def build_app_config(*, is_production: bool, override: Iterable[tuple] | dict | None = None) -> dict:
    jwt_secret = os.environ.get("JWT_SECRET_KEY")
    if is_production and not jwt_secret:
        raise RuntimeError("JWT_SECRET_KEY must be set in production")
    jwt_secret = jwt_secret or (
        "dev-insecure-change-me-please-set-jwt-secret-key" if not is_production else secrets.token_hex(32)
    )
    config = {
        "APP_ENV": "production" if is_production else os.environ.get("APP_ENV", "development").lower(),
        "JWT_SECRET_KEY": jwt_secret,
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
