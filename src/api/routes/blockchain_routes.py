"""
Blockchain routes blueprint.
Handles blockchain viewing, stats, validation, and mining.
"""

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
    """Health check - public endpoint for monitoring."""
    app_ctx = get_app_ctx()
    mempool_size = len(app_ctx.blockchain.get_mempool_transactions())
    return api_success(data={
        'status': 'healthy',
        'blockchain_height': len(app_ctx.blockchain),
        'mempool_size': mempool_size,
        'detector_trained': app_ctx.analyzer.detector.is_fitted,
        'alerts_unresolved': app_ctx.metadata_store.get_alert_stats().get('unresolved', 0)
    })


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
    blocks = [block.to_dict() for block in app_ctx.blockchain]

    paginated_blocks, pagination = paginate(blocks, page, per_page)

    return api_success(
        data={
            'chain': paginated_blocks,
            'height': len(app_ctx.blockchain),
            'is_valid': app_ctx.blockchain.validate_chain()[0]
        },
        pagination=pagination
    )


@blockchain_bp.route('/blockchain/stats', methods=['GET'])
@jwt_required()
def get_blockchain_stats():
    """Returns blockchain stats + metadata from SQLite."""
    app_ctx = get_app_ctx()
    stats = app_ctx.blockchain.get_statistics()
    alert_stats = app_ctx.metadata_store.get_alert_stats()
    stats['alerts'] = alert_stats
    return api_success(data=stats)


@blockchain_bp.route('/blockchain/validate', methods=['GET'])
@jwt_required()
def validate_blockchain():
    """Validates entire blockchain."""
    app_ctx = get_app_ctx()
    is_valid, error = app_ctx.blockchain.validate_chain()
    return api_success(data={
        'is_valid': is_valid,
        'error': error,
        'height': len(app_ctx.blockchain)
    })


@blockchain_bp.route('/block/<int:index>', methods=['GET'])
@jwt_required()
def get_block(index):
    """Returns a specific block by index."""
    app_ctx = get_app_ctx()
    block = app_ctx.blockchain.get_block(index)
    if block:
        return api_success(data=block.to_dict())
    return api_error("Block not found", 404, error_code="BLOCK_NOT_FOUND")


@blockchain_bp.route('/mine', methods=['POST'])
@rate_limit(limit=20, window_seconds=60, scope='mine_block')
@jwt_required()
def mine_block():
    """
    Mines a new block with transactions from mempool.
    Requires admin or operator role.
    """
    app_ctx = get_app_ctx()
    # Check role
    claims = get_jwt()
    if claims.get('role') not in ('admin', 'operator'):
        return api_error("Access forbidden. Required: admin, operator", 403, error_code="FORBIDDEN")

    if not app_ctx.blockchain.get_mempool_transactions():
        return api_error("No transactions in mempool", 400,
                         error_code="EMPTY_MEMPOOL")

    result = app_ctx.analyzer.mine_and_analyze()
    if result:
        # Index transactions from new block in SQLite
        new_block = app_ctx.blockchain.get_block(result['block']['index'])
        if new_block:
            for tx in new_block.transactions:
                index_record = app_ctx.metadata_store.get_transaction_index(tx.transaction_id) or {}
                is_flagged = bool(index_record.get('is_flagged', 0))
                app_ctx.metadata_store.update_transaction_state(
                    tx.transaction_id,
                    block_index=new_block.index,
                    tx_status='FLAGGED' if is_flagged else 'MINED',
                    is_flagged=is_flagged
                )

        # Emit WebSocket event to all connected clients
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
            data={
                'block': result['block'],
                'anomalies_found': result['anomalies_found']
            },
            message=f"Block #{result['block']['index']} mined successfully"
        )

    return api_error("Could not mine block", 500, error_code="MINE_FAILED")


@blockchain_bp.route('/mempool', methods=['GET'])
@jwt_required()
def get_mempool():
    """Returns paginated pending transactions from mempool."""
    app_ctx = get_app_ctx()
    page, per_page = get_pagination_params()
    mempool_txs = [tx.to_dict() for tx in app_ctx.blockchain.get_mempool_transactions()]
    paginated, pagination = paginate(mempool_txs, page, per_page)

    return api_success(data={
        'transactions': paginated,
        'count': len(paginated),
        'total_mempool': len(mempool_txs)
    }, pagination=pagination)

