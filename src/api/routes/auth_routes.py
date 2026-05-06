"""Authentication routes blueprint."""

import logging

from flask import Blueprint, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)

from src.domain.errors import AuthError, ValidationError

from ..app_context import get_app_ctx
from ..rate_limit import rate_limit
from ..responses import api_success

logger = logging.getLogger("blockchain_audit")

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _read_credentials() -> tuple[str, str]:
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        raise ValidationError("Username and password are required")
    return username, password


@auth_bp.route("/login", methods=["POST"])
@rate_limit(limit=20, window_seconds=60, scope="auth_login")
def login():
    app_ctx = get_app_ctx()
    username, password = _read_credentials()
    authenticated = app_ctx.auth_service.authenticate(username, password)

    additional_claims = {"role": authenticated.role, "wallet_name": authenticated.wallet_name}
    access_token = create_access_token(identity=username, additional_claims=additional_claims)
    refresh_token = create_refresh_token(identity=username, additional_claims=additional_claims)

    logger.info("User authenticated: %s (role: %s)", username, authenticated.role)
    return api_success(
        data={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "username": username,
                "role": authenticated.role,
                "wallet_name": authenticated.wallet_name,
            },
        },
        message="Authentication successful",
    )


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    app_ctx = get_app_ctx()
    identity = get_jwt_identity()
    user = app_ctx.auth_service.get_user(identity)
    if not user:
        raise AuthError("User account no longer exists")
    access_token = create_access_token(
        identity=identity,
        additional_claims={"role": user["role"], "wallet_name": user.get("wallet_name")},
    )
    return api_success(data={"access_token": access_token}, message="Token refreshed")


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    app_ctx = get_app_ctx()
    app_ctx.auth_service.revoke_token(get_jwt()["jti"])
    logger.info("User logged out: %s", get_jwt_identity())
    return api_success(message="Logout successful")


@auth_bp.route("/register", methods=["POST"])
@rate_limit(limit=30, window_seconds=60, scope="auth_register")
@jwt_required()
def register():
    app_ctx = get_app_ctx()
    claims = get_jwt()
    data = request.get_json(silent=True) or {}

    created_user = app_ctx.auth_service.register_user(
        requester_role=claims.get("role", "viewer"),
        username=(data.get("username") or "").strip(),
        password=data.get("password") or "",
        role=data.get("role", "viewer"),
        wallet_name=data.get("wallet_name"),
    )
    logger.info("User created: %s (role: %s) by %s", created_user["username"], created_user["role"], get_jwt_identity())
    return api_success(data=created_user, message="User created successfully", status_code=201)


@auth_bp.route("/register-viewer", methods=["POST"])
@rate_limit(limit=20, window_seconds=60, scope="auth_register_viewer")
def register_viewer():
    app_ctx = get_app_ctx()
    data = request.get_json(silent=True) or {}
    created_user = app_ctx.auth_service.register_viewer(
        username=(data.get("username") or "").strip(),
        password=data.get("password") or "",
    )
    logger.info("Viewer user created: %s", created_user["username"])
    return api_success(data=created_user, message="Viewer account created successfully", status_code=201)
