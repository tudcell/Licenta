"""Transaction routes blueprint. Thin HTTP layer over the transaction service."""

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from src.domain.policies.transaction_payload import parse_transaction_request
from ..app_context import get_app_ctx
from ..rate_limit import rate_limit
from ..responses import api_error, api_success, get_pagination_params
from ..security import current_principal

transaction_bp = Blueprint("transactions", __name__, url_prefix="/api")


@transaction_bp.route("/transactions", methods=["GET"])
@jwt_required()
def get_transactions():
    app_ctx = get_app_ctx()
    page, per_page = get_pagination_params()

    flagged_param = request.args.get("flagged")
    flagged_value = None
    if flagged_param is not None:
        flagged_value = flagged_param.lower() in ("1", "true", "yes")

    data, pagination = app_ctx.transaction_service.list_indexed_transactions(
        page=page,
        per_page=per_page,
        sender=request.args.get("sender"),
        tx_type=request.args.get("type"),
        tx_status=request.args.get("status"),
        flagged=flagged_value,
    )
    return api_success(data=data, pagination=pagination)


@transaction_bp.route("/transaction/<transaction_id>", methods=["GET"])
@jwt_required()
def get_transaction(transaction_id):
    app_ctx = get_app_ctx()
    payload = app_ctx.transaction_service.get_transaction_details(transaction_id)
    if payload:
        return api_success(data=payload)
    return api_error("Transaction not found", 404, error_code="TX_NOT_FOUND")


@transaction_bp.route("/transaction", methods=["POST"])
@rate_limit(limit=120, window_seconds=60, scope="tx_create")
@jwt_required()
def create_transaction():
    app_ctx = get_app_ctx()
    request_payload = request.get_json(silent=True)
    parsed = parse_transaction_request(request_payload, get_jwt_identity())

    data = app_ctx.transaction_service.create_transaction(
        principal=current_principal(),
        transaction_type=parsed.transaction_type,
        transaction_data=parsed.data,
        wallet_name=parsed.wallet_name,
        metadata=parsed.metadata,
    )
    return api_success(data=data, message="Transaction created successfully", status_code=201)


@transaction_bp.route("/transaction/analyze/<transaction_id>", methods=["GET"])
@jwt_required()
def analyze_transaction(transaction_id):
    app_ctx = get_app_ctx()
    report = app_ctx.transaction_service.analyze_transaction(transaction_id)
    if report:
        return api_success(data=report.to_dict())
    return api_error("Transaction not found", 404, error_code="TX_NOT_FOUND")
