"""JWT lifecycle callbacks (revocation, expiry, missing-token responses)."""

from __future__ import annotations

from flask import Flask
from flask_jwt_extended import JWTManager

from ..responses import api_error


def register_jwt_callbacks(app: Flask, jwt: JWTManager) -> None:
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(_jwt_header, jwt_payload):
        return app.metadata_store.is_token_revoked(jwt_payload["jti"])

    @jwt.expired_token_loader
    def expired_token_callback(_jwt_header, _jwt_payload):
        return api_error("Access token has expired", 401, error_code="TOKEN_EXPIRED")

    @jwt.invalid_token_loader
    def invalid_token_callback(_error):
        return api_error("Invalid token", 401, error_code="TOKEN_INVALID")

    @jwt.unauthorized_loader
    def missing_token_callback(_error):
        return api_error("Authentication required", 401, error_code="TOKEN_MISSING")
