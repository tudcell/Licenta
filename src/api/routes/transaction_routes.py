"""Transaction controller routes."""

import logging
from datetime import datetime, timezone
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from ..app_context import get_app_ctx
from ..rate_limit import rate_limit
from ..responses import api_success, api_error, get_pagination_params
from ..extensions import socketio
from src.domain import TransactionType

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

    indexed_txs, total = app_ctx.transaction_service.list_transactions(
        sender=sender, tx_type=tx_type, status=tx_status, flagged=flagged_value, page=page, per_page=per_page
    )

    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': max(1, (total + per_page - 1) // per_page),
        'has_next': page * per_page < total,
        'has_prev': page > 1,
    }

    return api_success(data={'transactions': indexed_txs, 'count': len(indexed_txs)}, pagination=pagination)


@transaction_bp.route('/transaction/<transaction_id>', methods=['GET'])
@jwt_required()
def get_transaction(transaction_id):
    app_ctx = get_app_ctx()
    proof, index_record = app_ctx.transaction_service.get_transaction_details(transaction_id, app_ctx.blockchain_repository)

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
        TransactionType(data['transaction_type'])
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
    payload, status = app_ctx.transaction_service.create_transaction(username, claims.get('role', 'viewer'), data)

    if status == 400:
        return api_error("Transaction signature is invalid", 400, data=payload, error_code='INVALID_SIGNATURE')
    if status == 401:
        return api_error("Authenticated user not found", 401, error_code='AUTH_FAILED')
    if status == 403:
        return api_error("Wallet does not belong to the authenticated user", 403, error_code='WALLET_FORBIDDEN')
    if status == 409:
        return api_error("Transaction was not added to the mempool", 409, data=payload, error_code='MEMPOOL_REJECTED')

    analysis = payload['analysis']
    if analysis.get('is_suspicious'):
        socketio.emit('anomaly_detected', {
            'alert_id': payload.get('alert_id'),
            'transaction_id': payload['transaction']['transaction_id'],
            'status': analysis.get('overall_status'),
            'explanation': (analysis.get('anomaly_result') or {}).get('explanation'),
            'score': (analysis.get('anomaly_result') or {}).get('anomaly_score'),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }, namespace='/alerts')

        logger.warning(
            "Suspicious transaction flagged and added to mempool: tx=%s status=%s",
            payload['transaction']['transaction_id'][:16],
            analysis.get('overall_status')
        )

    return api_success(data=payload, message="Transaction created successfully", status_code=201)


@transaction_bp.route('/transaction/analyze/<transaction_id>', methods=['GET'])
@jwt_required()
def analyze_transaction(transaction_id):
    app_ctx = get_app_ctx()
    report = app_ctx.transaction_service.analyze_transaction(transaction_id)
    if report:
        return api_success(data=report.to_dict())
    return api_error("Transaction not found", 404, error_code="TX_NOT_FOUND")
