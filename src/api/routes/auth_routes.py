"""
Authentication routes blueprint.
Handles login, logout, token refresh, and user registration.
"""

import logging
from flask import Blueprint, request
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt
)

from ..app_context import get_app_ctx
from ..rate_limit import rate_limit
from ..responses import api_success, api_error
from src.service.exceptions import ServiceError

logger = logging.getLogger('blockchain_audit')

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/login', methods=['POST'])
@rate_limit(limit=20, window_seconds=60, scope='auth_login')
def login():
    app_ctx = get_app_ctx()
    data = request.get_json()
    if not data:
        return api_error("Authentication data missing", 400)

    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        return api_error("Username and password are required", 400)

    try:
        authenticated = app_ctx.auth_service.authenticate(username, password)
    except ServiceError as exc:
        return api_error(exc.message, exc.status_code, errors=exc.errors, error_code=exc.error_code, data=exc.data)

    additional_claims = {
        'role': authenticated.role,
        'wallet_name': authenticated.wallet_name
    }
    access_token = create_access_token(identity=username, additional_claims=additional_claims)
    refresh_token = create_refresh_token(identity=username, additional_claims=additional_claims)

    logger.info("User authenticated: %s (role: %s)", username, authenticated.role)

    return api_success(data={
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': {
            'username': username,
            'role': authenticated.role,
            'wallet_name': authenticated.wallet_name
        }
    }, message="Authentication successful")


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    app_ctx = get_app_ctx()
    identity = get_jwt_identity()
    user = app_ctx.metadata_store.get_user(identity)
    if not user:
        return api_error("User account no longer exists", 401, error_code="AUTH_FAILED")
    access_token = create_access_token(
        identity=identity,
        additional_claims={
            'role': user['role'],
            'wallet_name': user.get('wallet_name'),
        }
    )
    return api_success(data={'access_token': access_token}, message="Token refreshed")


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    app_ctx = get_app_ctx()
    jti = get_jwt()['jti']
    app_ctx.auth_service.revoke_token(jti)
    logger.info("User logged out: %s", get_jwt_identity())
    return api_success(message="Logout successful")


@auth_bp.route('/register', methods=['POST'])
@rate_limit(limit=30, window_seconds=60, scope='auth_register')
@jwt_required()
def register():
    app_ctx = get_app_ctx()
    claims = get_jwt()

    data = request.get_json()
    if not data:
        return api_error("Data missing", 400)

    username = data.get('username', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'viewer')

    try:
        created_user = app_ctx.auth_service.register_user(
            requester_role=claims.get('role', 'viewer'),
            username=username,
            password=password,
            role=role,
            wallet_name=data.get('wallet_name'),
        )
    except ServiceError as exc:
        return api_error(exc.message, exc.status_code, errors=exc.errors, error_code=exc.error_code, data=exc.data)

    logger.info("User created: %s (role: %s) by %s", username, role, get_jwt_identity())
    return api_success(
        data=created_user,
        message="User created successfully",
        status_code=201
    )


@auth_bp.route('/register-viewer', methods=['POST'])
@rate_limit(limit=20, window_seconds=60, scope='auth_register_viewer')
def register_viewer():
    app_ctx = get_app_ctx()

    data = request.get_json()
    if not data:
        return api_error("Data missing", 400)

    username = data.get('username', '').strip()
    password = data.get('password', '')

    try:
        created_user = app_ctx.auth_service.register_viewer(username=username, password=password)
    except ServiceError as exc:
        return api_error(exc.message, exc.status_code, errors=exc.errors, error_code=exc.error_code, data=exc.data)

    logger.info("Viewer user created: %s", username)
    return api_success(
        data=created_user,
        message="Viewer account created successfully",
        status_code=201
    )

