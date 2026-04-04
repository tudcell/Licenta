"""
Transaction routes blueprint.
Handles transaction creation, viewing, and analysis.
"""

import logging
from datetime import datetime, timezone
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from ..app_context import get_app_ctx
from ..rate_limit import rate_limit
from ..responses import api_success, api_error, get_pagination_params
from ..extensions import socketio
from src.blockchain.transaction import TransactionType

logger = logging.getLogger('blockchain_audit')

transaction_bp = Blueprint('transactions', __name__, url_prefix='/api')


@transaction_bp.route('/transactions', methods=['GET'])
@jwt_required()
def get_transactions():
    app_ctx = get_app_ctx()
    page, per_page = get_pagination_params()
    tx_type = request.args.get('type')
    sender = request.args.get('sender')
    tx_status = request.args.get('status')
    flagged = request.args.get('flagged')

    flagged_value = None
    if flagged is not None:
        flagged_value = flagged.lower() in ('1', 'true', 'yes')

    indexed_txs, total = app_ctx.metadata_store.search_transactions(
        sender=sender,
        tx_type=tx_type,
        status=tx_status,
        flagged=flagged_value,
        page=page,
        per_page=per_page
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
            'transactions': indexed_txs,
            'count': len(indexed_txs)
        },
        pagination=pagination
    )


@transaction_bp.route('/transaction/<transaction_id>', methods=['GET'])
@jwt_required()
def get_transaction(transaction_id):
    app_ctx = get_app_ctx()
    proof = app_ctx.blockchain.verify_transaction_proof(transaction_id)
    index_record = app_ctx.metadata_store.get_transaction_index(transaction_id)

    if proof:
        payload = dict(proof)
        if index_record:
            payload['index_record'] = index_record
        return api_success(data=payload)

    if index_record:
        return api_success(data={'index_record': index_record})

    return api_error("Transaction not found", 404, error_code="TX_NOT_FOUND")


@transaction_bp.route('/transaction', methods=['POST'])
@rate_limit(limit=120, window_seconds=60, scope='tx_create')
@jwt_required()
def create_transaction():
    app_ctx = get_app_ctx()
    data = request.get_json()
    if not data:
        return api_error("Transaction data missing", 400)

    required_fields = ['transaction_type', 'data']
    missing = [f for f in required_fields if f not in data]
    if missing:
        return api_error(
            f"Missing fields: {', '.join(missing)}",
            400,
            errors=[{'field': f, 'message': 'required field'} for f in missing],
            error_code="VALIDATION_ERROR"
        )

    try:
        tx_type = TransactionType(data['transaction_type'])
    except ValueError:
        valid_types = [t.value for t in TransactionType]
        return api_error(
            f"Invalid transaction type: {data['transaction_type']}",
            400,
            errors=[{'valid_types': valid_types}],
            error_code="INVALID_TX_TYPE"
        )

    username = get_jwt_identity()
    claims = get_jwt()
    user = app_ctx.metadata_store.get_user(username)
    if not user:
        return api_error("Authenticated user not found", 401, error_code="AUTH_FAILED")

    requested_wallet_name = data.get('wallet_name') or user.get('wallet_name') or username
    user_role = claims.get('role', user.get('role', 'viewer'))

    if user.get('wallet_name') and requested_wallet_name != user['wallet_name'] and user_role != 'admin':
        return api_error("Wallet does not belong to the authenticated user", 403, error_code="WALLET_FORBIDDEN")

    wallet = app_ctx.wallet_manager.get_wallet(requested_wallet_name)
    if wallet is None:
        wallet = app_ctx.wallet_manager.create_wallet(
            requested_wallet_name,
            metadata={'owner': username}
        )

    if not user.get('wallet_name'):
        app_ctx.metadata_store.assign_wallet_to_user(username, requested_wallet_name)
        user['wallet_name'] = requested_wallet_name

    tx_metadata: dict[str, object] = dict(data.get('metadata', {}))
    tx_metadata.setdefault('submitted_by', username)
    tx_metadata.setdefault('flagged', False)

    tx = wallet.create_and_sign_transaction(
        transaction_type=tx_type,
        data=data['data'],
        metadata=tx_metadata
    )

    report = app_ctx.analyzer.add_transaction(tx)

    if not report.signature_valid:
        app_ctx.metadata_store.index_transaction(
            tx,
            tx_status='REJECTED',
            is_flagged=True
        )
        app_ctx.metadata_store.save_alert(report)

        return api_error(
            "Transaction signature is invalid",
            400,
            data={
                'transaction': tx.to_dict(),
                'analysis': report.to_dict()
            },
            error_code="INVALID_SIGNATURE"
        )

    if not report.added_to_mempool:
        # This is the key mempool fix:
        # do NOT mark it as pending if the blockchain rejected it.
        # Most likely causes: duplicate transaction ID or duplicate submission.
        app_ctx.metadata_store.index_transaction(
            tx,
            tx_status='REJECTED',
            is_flagged=report.is_suspicious
        )

        if report.is_suspicious:
            app_ctx.metadata_store.save_alert(report)

        return api_error(
            "Transaction was not added to the mempool",
            409,
            data={
                'transaction': tx.to_dict(),
                'analysis': report.to_dict()
            },
            error_code="MEMPOOL_REJECTED"
        )

    tx_status = 'FLAGGED' if report.flagged_for_review else 'PENDING'
    app_ctx.metadata_store.index_transaction(
        tx,
        tx_status=tx_status,
        is_flagged=report.flagged_for_review
    )

    if report.is_suspicious:
        alert_id = app_ctx.metadata_store.save_alert(report)
        socketio.emit('anomaly_detected', {
            'alert_id': alert_id,
            'transaction_id': tx.transaction_id,
            'status': report.overall_status,
            'explanation': report.anomaly_result.explanation if report.anomaly_result else None,
            'score': float(report.anomaly_result.anomaly_score) if report.anomaly_result else None,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }, namespace='/alerts')

        logger.warning(
            "Suspicious transaction flagged and added to mempool: tx=%s status=%s",
            tx.transaction_id[:16],
            report.overall_status
        )

    return api_success(
        data={
            'transaction': tx.to_dict(),
            'analysis': report.to_dict()
        },
        message="Transaction created successfully",
        status_code=201
    )


@transaction_bp.route('/transaction/analyze/<transaction_id>', methods=['GET'])
@jwt_required()
def analyze_transaction(transaction_id):
    app_ctx = get_app_ctx()
    report = app_ctx.analyzer.analyze_transaction(transaction_id)
    if report:
        return api_success(data=report.to_dict())
    return api_error("Transaction not found", 404, error_code="TX_NOT_FOUND")