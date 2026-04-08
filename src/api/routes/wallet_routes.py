"""Wallet controller routes."""

import logging
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from ..app_context import get_app_ctx
from ..responses import api_success, api_error, paginate, get_pagination_params

logger = logging.getLogger('blockchain_audit')

wallet_bp = Blueprint('wallets', __name__, url_prefix='/api')


@wallet_bp.route('/wallets', methods=['GET'])
@jwt_required()
def get_wallets():
    app_ctx = get_app_ctx()
    page, per_page = get_pagination_params()
    claims = get_jwt()
    username = get_jwt_identity()

    wallets = app_ctx.wallet_service.list_wallets_for_user(username=username, role=claims.get('role', 'viewer'))
    paginated, pagination = paginate(wallets, page, per_page)
    return api_success(data={'wallets': paginated, 'count': len(paginated)}, pagination=pagination)


@wallet_bp.route('/wallet', methods=['POST'])
@jwt_required()
def create_wallet():
    app_ctx = get_app_ctx()
    data = request.get_json()
    if not data or 'name' not in data:
        return api_error("Field 'name' is required", 400)

    name = data['name'].strip()
    if not name or len(name) < 2:
        return api_error("Wallet name must have at least 2 characters", 400)

    username = get_jwt_identity()
    claims = get_jwt()
    requested_owner = data.get('assign_to_user') or username

    try:
        wallet, error = app_ctx.wallet_service.create_wallet(
            name=name,
            requested_owner=requested_owner,
            created_by=username,
            creator_role=claims.get('role', 'viewer')
        )
    except ValueError as e:
        return api_error(str(e), 409, error_code='WALLET_EXISTS')

    if error == 'AUTH_FAILED':
        return api_error("Authenticated user not found", 401, error_code="AUTH_FAILED")
    if error == 'FORBIDDEN':
        return api_error("Only admins can assign wallets to other users", 403, error_code="FORBIDDEN")
    if error == 'USER_NOT_FOUND':
        return api_error(f"User '{requested_owner}' not found", 404, error_code="USER_NOT_FOUND")
    if error == 'WALLET_ALREADY_ASSIGNED':
        return api_error("User already has an assigned wallet", 409, error_code="WALLET_ALREADY_ASSIGNED")

    logger.info("Wallet created: %s assigned_to=%s by=%s", name, requested_owner, username)
    return api_success(
        data={'wallet': wallet.to_dict(include_private_key=False), 'assigned_to': requested_owner},
        message=f"Wallet '{name}' created successfully",
        status_code=201
    )


@wallet_bp.route('/wallet/<name>', methods=['GET'])
@jwt_required()
def get_wallet(name):
    app_ctx = get_app_ctx()
    username = get_jwt_identity()
    claims = get_jwt()
    detail, status = app_ctx.wallet_service.get_wallet_details(name, username, claims.get('role', 'viewer'))
    if status != 200:
        if detail['error'] == 'WALLET_NOT_FOUND':
            return api_error(f"Wallet '{name}' not found", 404, error_code='WALLET_NOT_FOUND')
        return api_error("Access forbidden to this wallet", 403, error_code='FORBIDDEN')

    page, per_page = get_pagination_params()
    indexed_txs, total = app_ctx.metadata_repository.search_transactions(
        sender=detail['wallet']['address'], page=page, per_page=per_page
    )
    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': max(1, (total + per_page - 1) // per_page),
        'has_next': page * per_page < total,
        'has_prev': page > 1,
    }

    return api_success(
        data={
            'wallet': detail['wallet'],
            'transactions': indexed_txs,
            'transaction_count': total
        },
        pagination=pagination
    )
