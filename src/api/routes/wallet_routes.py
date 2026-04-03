"""
Wallet routes blueprint.
Handles wallet creation and viewing.
"""

import logging
from flask import Blueprint, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from ..responses import api_success, api_error, paginate, get_pagination_params

logger = logging.getLogger('blockchain_audit')

wallet_bp = Blueprint('wallets', __name__, url_prefix='/api')


@wallet_bp.route('/wallets', methods=['GET'])
@jwt_required()
def get_wallets():
    page, per_page = get_pagination_params()
    claims = get_jwt()
    username = get_jwt_identity()
    user = current_app.metadata_store.get_user(username)

    wallets = current_app.wallet_manager.list_wallets()
    if claims.get('role') != 'admin' and user and user.get('wallet_name'):
        wallets = [wallet for wallet in wallets if wallet['name'] == user['wallet_name']]

    paginated, pagination = paginate(wallets, page, per_page)
    return api_success(data={'wallets': paginated, 'count': len(paginated)}, pagination=pagination)


@wallet_bp.route('/wallet', methods=['POST'])
@jwt_required()
def create_wallet():
    data = request.get_json()
    if not data or 'name' not in data:
        return api_error("Field 'name' is required", 400)

    name = data['name'].strip()
    if not name or len(name) < 2:
        return api_error("Wallet name must have at least 2 characters", 400)

    username = get_jwt_identity()
    claims = get_jwt()
    user = current_app.metadata_store.get_user(username)
    if not user:
        return api_error("Authenticated user not found", 401, error_code="AUTH_FAILED")

    requested_owner = data.get('assign_to_user') or username
    if claims.get('role') != 'admin' and requested_owner != username:
        return api_error("Only admins can assign wallets to other users", 403, error_code="FORBIDDEN")

    if claims.get('role') != 'admin' and user.get('wallet_name') and user['wallet_name'] != name:
        return api_error("User already has an assigned wallet", 409, error_code="WALLET_ALREADY_ASSIGNED")

    try:
        wallet = current_app.wallet_manager.create_wallet(name, {'owner': requested_owner})
    except ValueError as e:
        return api_error(str(e), 409, error_code="WALLET_EXISTS")

    if not current_app.metadata_store.assign_wallet_to_user(requested_owner, name):
        return api_error(f"Could not assign wallet to user '{requested_owner}'", 404, error_code="USER_NOT_FOUND")

    logger.info("Wallet created: %s assigned_to=%s by=%s", name, requested_owner, username)
    return api_success(
        data={'wallet': wallet.to_dict(include_private_key=False), 'assigned_to': requested_owner},
        message=f"Wallet '{name}' created successfully",
        status_code=201
    )


@wallet_bp.route('/wallet/<name>', methods=['GET'])
@jwt_required()
def get_wallet(name):
    wallet = current_app.wallet_manager.get_wallet(name)
    if not wallet:
        return api_error(f"Wallet '{name}' not found", 404, error_code="WALLET_NOT_FOUND")

    username = get_jwt_identity()
    claims = get_jwt()
    user = current_app.metadata_store.get_user(username)
    if claims.get('role') != 'admin' and user and user.get('wallet_name') != name:
        return api_error("Access forbidden to this wallet", 403, error_code="FORBIDDEN")

    page, per_page = get_pagination_params()
    indexed_txs, total = current_app.metadata_store.search_transactions(sender=wallet.address, page=page, per_page=per_page)
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
            'wallet': wallet.to_dict(include_private_key=False),
            'transactions': indexed_txs,
            'transaction_count': total
        },
        pagination=pagination
    )
