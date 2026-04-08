"""Blockchain controller routes."""

import logging
from datetime import datetime, timezone
from flask import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from ..app_context import get_app_ctx
from ..rate_limit import rate_limit
from ..responses import api_success, api_error, paginate, get_pagination_params
from ..extensions import socketio

logger = logging.getLogger('blockchain_audit')

blockchain_bp = Blueprint('blockchain', __name__, url_prefix='/api')


@blockchain_bp.route('/health')
def health():
    app_ctx = get_app_ctx()
    return api_success(data=app_ctx.blockchain_service.get_health())


@blockchain_bp.route('/blockchain', methods=['GET'])
@jwt_required()
def get_blockchain():
    app_ctx = get_app_ctx()
    page, per_page = get_pagination_params()
    chain_data = app_ctx.blockchain_service.get_chain()
    paginated_blocks, pagination = paginate(chain_data['chain'], page, per_page)
    return api_success(data={'chain': paginated_blocks, 'height': chain_data['height'], 'is_valid': chain_data['is_valid']}, pagination=pagination)


@blockchain_bp.route('/blockchain/stats', methods=['GET'])
@jwt_required()
def get_blockchain_stats():
    app_ctx = get_app_ctx()
    return api_success(data=app_ctx.blockchain_service.get_stats())


@blockchain_bp.route('/blockchain/validate', methods=['GET'])
@jwt_required()
def validate_blockchain():
    app_ctx = get_app_ctx()
    return api_success(data=app_ctx.blockchain_service.validate())


@blockchain_bp.route('/block/<int:index>', methods=['GET'])
@jwt_required()
def get_block(index):
    app_ctx = get_app_ctx()
    block = app_ctx.blockchain_repository.get_block(index)
    if block:
        return api_success(data=block.to_dict())
    return api_error("Block not found", 404, error_code="BLOCK_NOT_FOUND")


@blockchain_bp.route('/mine', methods=['POST'])
@rate_limit(limit=20, window_seconds=60, scope='mine_block')
@jwt_required()
def mine_block():
    app_ctx = get_app_ctx()
    claims = get_jwt()
    if claims.get('role') not in ('admin', 'operator'):
        return api_error("Access forbidden. Required: admin, operator", 403, error_code="FORBIDDEN")

    if not app_ctx.blockchain_repository.get_mempool_transactions():
        return api_error("No transactions in mempool", 400, error_code="EMPTY_MEMPOOL")

    result = app_ctx.blockchain_service.mine_block()
    if not result:
        return api_error("Could not mine block", 500, error_code="MINE_FAILED")

    socketio.emit('block_mined', {
        'block_index': result['block']['index'],
        'transaction_count': result['block'].get('transaction_count', 0),
        'anomalies_found': result['anomalies_found'],
        'timestamp': datetime.now(timezone.utc).isoformat()
    }, namespace='/alerts')

    logger.info("Block #%d mined with %d transactions, %d anomalies by %s",
                result['block']['index'],
                result['block'].get('transaction_count', 0),
                result['anomalies_found'],
                get_jwt_identity())

    return api_success(
        data={'block': result['block'], 'anomalies_found': result['anomalies_found']},
        message=f"Block #{result['block']['index']} mined successfully"
    )


@blockchain_bp.route('/mempool', methods=['GET'])
@jwt_required()
def get_mempool():
    app_ctx = get_app_ctx()
    page, per_page = get_pagination_params()
    mempool_txs = [tx.to_dict() for tx in app_ctx.blockchain_repository.get_mempool_transactions()]
    paginated, pagination = paginate(mempool_txs, page, per_page)
    return api_success(data={'transactions': paginated, 'count': len(paginated), 'total_mempool': len(mempool_txs)}, pagination=pagination)
