"""
Blockchain routes blueprint.
Handles blockchain viewing, stats, validation, and mining.
"""

import logging
from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from ..app_context import get_app_ctx
from ..rate_limit import rate_limit
from ..responses import api_success, api_error, get_pagination_params
from ..extensions import socketio
from src.service.exceptions import ServiceError

logger = logging.getLogger('blockchain_audit')

blockchain_bp = Blueprint('blockchain', __name__, url_prefix='/api')


@blockchain_bp.route('/health')
def health():
    """Health check - public endpoint for monitoring."""
    app_ctx = get_app_ctx()
    return api_success(data=app_ctx.blockchain_service.health())


@blockchain_bp.route('/blockchain', methods=['GET'])
@jwt_required()
def get_blockchain():
    """
    Returns paginated blockchain.

    Query params:
        page (int): Current page (default 1)
        per_page (int): Blocks per page (default 20, max 100)
    """
    app_ctx = get_app_ctx()
    page, per_page = get_pagination_params()
    data, pagination = app_ctx.blockchain_service.get_blockchain(page=page, per_page=per_page)
    return api_success(data=data, pagination=pagination)


@blockchain_bp.route('/blockchain/stats', methods=['GET'])
@jwt_required()
def get_blockchain_stats():
    """Returns blockchain stats + metadata from SQLite."""
    app_ctx = get_app_ctx()
    return api_success(data=app_ctx.blockchain_service.get_stats())


@blockchain_bp.route('/blockchain/validate', methods=['GET'])
@jwt_required()
def validate_blockchain():
    """Validates entire blockchain."""
    app_ctx = get_app_ctx()
    return api_success(data=app_ctx.blockchain_service.validate())


@blockchain_bp.route('/block/<int:index>', methods=['GET'])
@jwt_required()
def get_block(index):
    """Returns a specific block by index."""
    app_ctx = get_app_ctx()
    try:
        return api_success(data=app_ctx.blockchain_service.get_block(index))
    except ServiceError as exc:
        return api_error(exc.message, exc.status_code, errors=exc.errors, error_code=exc.error_code, data=exc.data)


@blockchain_bp.route('/mine', methods=['POST'])
@rate_limit(limit=20, window_seconds=60, scope='mine_block')
@jwt_required()
def mine_block():
    """
    Mines a new block with transactions from mempool.
    Requires admin or operator role.
    """
    app_ctx = get_app_ctx()
    try:
        result = app_ctx.blockchain_service.mine_block(get_jwt().get('role', 'viewer'))
    except ServiceError as exc:
        return api_error(exc.message, exc.status_code, errors=exc.errors, error_code=exc.error_code, data=exc.data)

    socketio.emit('block_mined', result['event'], namespace='/alerts')

    logger.info(
        "Block #%d mined with %d transactions, %d anomalies by %s",
        result['block']['index'],
        result['block'].get('transaction_count', 0),
        result['anomalies_found'],
        get_jwt_identity(),
    )

    return api_success(
        data={
            'block': result['block'],
            'anomalies_found': result['anomalies_found']
        },
        message=f"Block #{result['block']['index']} mined successfully"
    )


@blockchain_bp.route('/mempool', methods=['GET'])
@jwt_required()
def get_mempool():
    """Returns paginated pending transactions from mempool."""
    app_ctx = get_app_ctx()
    page, per_page = get_pagination_params()
    data, pagination = app_ctx.blockchain_service.get_mempool(page=page, per_page=per_page)
    return api_success(data=data, pagination=pagination)

