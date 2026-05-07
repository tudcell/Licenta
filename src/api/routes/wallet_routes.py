"""Wallet routes blueprint."""

import logging

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from src.domain.errors import ValidationError
from ..app_context import get_app_ctx
from ..responses import api_success, get_pagination_params
from ..security import current_principal

logger = logging.getLogger("blockchain_audit")

wallet_bp = Blueprint("wallets", __name__, url_prefix="/api")


@wallet_bp.route("/wallets", methods=["GET"])
@jwt_required()
def get_wallets():
    app_ctx = get_app_ctx()
    page, per_page = get_pagination_params()
    data, pagination = app_ctx.wallet_service.list_wallets(
        principal=current_principal(),
        page=page,
        per_page=per_page,
    )
    return api_success(data=data, pagination=pagination)


@wallet_bp.route("/wallet", methods=["POST"])
@jwt_required()
def create_wallet():
    app_ctx = get_app_ctx()
    data = request.get_json(silent=True) or {}
    if "name" not in data:
        raise ValidationError("Field 'name' is required")

    result = app_ctx.wallet_service.create_wallet(
        principal=current_principal(),
        name=data["name"],
        assign_to_user=data.get("assign_to_user"),
    )
    logger.info(
        "Wallet created: %s assigned_to=%s by=%s",
        result["wallet_name"],
        result["assigned_to"],
        get_jwt_identity(),
    )
    return api_success(
        data={"wallet": result["wallet"], "assigned_to": result["assigned_to"]},
        message=f"Wallet '{result['wallet_name']}' created successfully",
        status_code=201,
    )


@wallet_bp.route("/wallet/<name>", methods=["GET"])
@jwt_required()
def get_wallet(name):
    app_ctx = get_app_ctx()
    page, per_page = get_pagination_params()
    data, pagination = app_ctx.wallet_service.get_wallet_details(
        principal=current_principal(),
        wallet_name=name,
        page=page,
        per_page=per_page,
    )
    return api_success(data=data, pagination=pagination)
