"""Blockchain routes blueprint."""

import logging

from flask import Blueprint
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from ..app_context import get_app_ctx
from ..rate_limit import rate_limit
from ..responses import api_success, get_pagination_params

logger = logging.getLogger("blockchain_audit")

blockchain_bp = Blueprint("blockchain", __name__, url_prefix="/api")


@blockchain_bp.route("/health")
def health():
    app_ctx = get_app_ctx()
    return api_success(data=app_ctx.blockchain_service.health())


@blockchain_bp.route("/blockchain", methods=["GET"])
@jwt_required()
def get_blockchain():
    app_ctx = get_app_ctx()
    page, per_page = get_pagination_params()
    data, pagination = app_ctx.blockchain_service.get_blockchain(page=page, per_page=per_page)
    return api_success(data=data, pagination=pagination)


@blockchain_bp.route("/blockchain/stats", methods=["GET"])
@jwt_required()
def get_blockchain_stats():
    app_ctx = get_app_ctx()
    return api_success(data=app_ctx.blockchain_service.get_stats())


@blockchain_bp.route("/blockchain/validate", methods=["GET"])
@jwt_required()
def validate_blockchain():
    app_ctx = get_app_ctx()
    return api_success(data=app_ctx.blockchain_service.validate())


@blockchain_bp.route("/block/<int:index>", methods=["GET"])
@jwt_required()
def get_block(index):
    app_ctx = get_app_ctx()
    return api_success(data=app_ctx.blockchain_service.get_block(index))


@blockchain_bp.route("/mine", methods=["POST"])
@rate_limit(limit=20, window_seconds=60, scope="mine_block")
@jwt_required()
def mine_block():
    app_ctx = get_app_ctx()
    result = app_ctx.blockchain_service.mine_block(get_jwt().get("role", "viewer"))

    logger.info(
        "Block #%d mined with %d transactions, %d anomalies by %s",
        result["block"]["index"],
        result["block"].get("transaction_count", 0),
        result["anomalies_found"],
        get_jwt_identity(),
    )
    return api_success(
        data={"block": result["block"], "anomalies_found": result["anomalies_found"]},
        message=f"Block #{result['block']['index']} mined successfully",
    )


@blockchain_bp.route("/mempool", methods=["GET"])
@jwt_required()
def get_mempool():
    app_ctx = get_app_ctx()
    page, per_page = get_pagination_params()
    data, pagination = app_ctx.blockchain_service.get_mempool(page=page, per_page=per_page)
    return api_success(data=data, pagination=pagination)
