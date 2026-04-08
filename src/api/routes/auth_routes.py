"""Authentication controller routes."""

import logging
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from ..app_context import get_app_ctx
from ..rate_limit import rate_limit
from ..responses import api_success, api_error

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

    auth_payload = app_ctx.auth_service.authenticate(username, password)
    if not auth_payload:
        return api_error("Invalid credentials", 401, error_code="AUTH_FAILED")

    logger.info("User authenticated: %s (role: %s)", username, auth_payload['user']['role'])
    return api_success(data=auth_payload, message="Authentication successful")


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    app_ctx = get_app_ctx()
    identity = get_jwt_identity()
    access_token = app_ctx.auth_service.refresh_access_token(identity)
    return api_success(data={'access_token': access_token}, message="Token refreshed")


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    app_ctx = get_app_ctx()
    jti = get_jwt()['jti']
    app_ctx.auth_service.logout(jti)
    logger.info("User logged out: %s", get_jwt_identity())
    return api_success(message="Logout successful")


@auth_bp.route('/register', methods=['POST'])
@rate_limit(limit=30, window_seconds=60, scope='auth_register')
@jwt_required()
def register():
    app_ctx = get_app_ctx()
    claims = get_jwt()
    if claims.get('role') != 'admin':
        return api_error("Access forbidden. Required: admin", 403, error_code="FORBIDDEN")

    data = request.get_json()
    if not data:
        return api_error("Data missing", 400)

    username = data.get('username', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'viewer')

    if not username or len(username) < 3:
        return api_error("Username must have at least 3 characters", 400)
    if not password or len(password) < 8:
        return api_error("Password must have at least 8 characters", 400)
    if role not in ('admin', 'operator', 'viewer'):
        return api_error("Invalid role. Options: admin, operator, viewer", 400)

    success = app_ctx.auth_service.register_user(username, password, role, data.get('wallet_name'))
    if not success:
        return api_error(f"User '{username}' already exists", 409, error_code="USER_EXISTS")

    logger.info("User created: %s (role: %s) by %s", username, role, get_jwt_identity())
    return api_success(
        data={'username': username, 'role': role, 'wallet_name': data.get('wallet_name')},
        message="User created successfully",
        status_code=201
    )
