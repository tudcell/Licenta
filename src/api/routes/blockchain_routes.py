"""
Blockchain routes blueprint.
Handles blockchain viewing, stats, validation, and mining.
"""

import logging
from datetime import datetime, timezone
from flask import Blueprint, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from ..responses import api_success, api_error, paginate, get_pagination_params
from ..extensions import socketio

logger = logging.getLogger('blockchain_audit')

blockchain_bp = Blueprint('blockchain', __name__, url_prefix='/api')


def require_role(*roles):
    """Check if user has required role."""
    def check():
        claims = get_jwt()
        return claims.get('role', 'viewer') in roles
    return check


@blockchain_bp.route('/health')
def health():
    """Health check - public endpoint for monitoring."""
    return api_success(data={
        'status': 'healthy',
        'blockchain_height': len(current_app.blockchain),
        'mempool_size': len(current_app.blockchain.mempool),
        'detector_trained': current_app.analyzer.detector.is_fitted,
        'alerts_unresolved': current_app.metadata_store.get_alert_stats().get('unresolved', 0)
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
    page, per_page = get_pagination_params()
    blocks = [block.to_dict() for block in current_app.blockchain]

    paginated_blocks, pagination = paginate(blocks, page, per_page)

    return api_success(
        data={
            'chain': paginated_blocks,
            'height': len(current_app.blockchain),
            'is_valid': current_app.blockchain.validate_chain()[0]
        },
        pagination=pagination
    )


@blockchain_bp.route('/blockchain/stats', methods=['GET'])
@jwt_required()
def get_blockchain_stats():
    """Returns blockchain stats + metadata from SQLite."""
    stats = current_app.blockchain.get_statistics()
    alert_stats = current_app.metadata_store.get_alert_stats()
    stats['alerts'] = alert_stats
    return api_success(data=stats)


@blockchain_bp.route('/blockchain/validate', methods=['GET'])
@jwt_required()
def validate_blockchain():
    """Validates entire blockchain."""
    is_valid, error = current_app.blockchain.validate_chain()
    return api_success(data={
        'is_valid': is_valid,
        'error': error,
        'height': len(current_app.blockchain)
    })


@blockchain_bp.route('/block/<int:index>', methods=['GET'])
@jwt_required()
def get_block(index):
    """Returns a specific block by index."""
    block = current_app.blockchain.get_block(index)
    if block:
        return api_success(data=block.to_dict())
    return api_error("Block not found", 404, error_code="BLOCK_NOT_FOUND")


@blockchain_bp.route('/mine', methods=['POST'])
@jwt_required()
def mine_block():
    """
    Mines a new block with transactions from mempool.
    Requires admin or operator role.
    """
    # Check role
    claims = get_jwt()
    if claims.get('role') not in ('admin', 'operator'):
        return api_error("Access forbidden. Required: admin, operator", 403, error_code="FORBIDDEN")

    if not current_app.blockchain.mempool:
        return api_error("No transactions in mempool", 400,
                         error_code="EMPTY_MEMPOOL")

    result = current_app.analyzer.mine_and_analyze()
    if result:
        # Index transactions from new block in SQLite
        new_block = current_app.blockchain.get_block(result['block']['index'])
        if new_block:
            for tx in new_block.transactions:
                current_app.metadata_store.update_transaction_state(
                    tx.transaction_id,
                    block_index=new_block.index,
                    tx_status='FLAGGED' if tx.metadata.get('flagged') else 'MINED',
                    is_flagged=bool(tx.metadata.get('flagged'))
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
    page, per_page = get_pagination_params()
    mempool_txs = [tx.to_dict() for tx in current_app.blockchain.mempool]
    paginated, pagination = paginate(mempool_txs, page, per_page)

    return api_success(data={
        'transactions': paginated,
        'count': len(paginated),
        'total_mempool': len(mempool_txs)
    }, pagination=pagination)

