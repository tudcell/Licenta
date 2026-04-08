"""
Transaction routes blueprint.
Handles transaction creation, viewing, and analysis.
"""

import logging
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from ..app_context import get_app_ctx
from ..rate_limit import rate_limit
from ..responses import api_success, api_error, get_pagination_params
from ..extensions import socketio
from src.domain.entities.transaction import TransactionType
from src.service.exceptions import ServiceError

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
    proof = app_ctx.blockchain_repository.verify_transaction_proof(transaction_id)
    index_record = app_ctx.metadata_repository.get_transaction_index(transaction_id)

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
    try:
        result = app_ctx.transaction_service.create_transaction(
            username=username,
            user_role=claims.get('role', 'viewer'),
            transaction_type=tx_type,
            transaction_data=data['data'],
            wallet_name=data.get('wallet_name'),
            metadata=data.get('metadata'),
        )
    except ServiceError as exc:
        return api_error(exc.message, exc.status_code, errors=exc.errors, error_code=exc.error_code, data=exc.data)

    if result.alert_event_payload:
        socketio.emit('anomaly_detected', result.alert_event_payload, namespace='/alerts')

        logger.warning(
            "Suspicious transaction flagged and added to mempool: tx=%s status=%s",
            str(result.data['transaction']['transaction_id'])[:16],
            result.data['analysis']['overall_status']
        )

    if not result.success:
        return api_error(result.message, result.status_code, data=result.data, error_code=result.error_code)

    return api_success(data=result.data, message=result.message, status_code=result.status_code)


@transaction_bp.route('/transaction/analyze/<transaction_id>', methods=['GET'])
@jwt_required()
def analyze_transaction(transaction_id):
    app_ctx = get_app_ctx()
    report = app_ctx.analyzer_repository.analyze_transaction(transaction_id)
    if report:
        return api_success(data=report.to_dict())
    return api_error("Transaction not found", 404, error_code="TX_NOT_FOUND")