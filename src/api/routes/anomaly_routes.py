"""Anomaly detection routes blueprint."""

from __future__ import annotations

import logging
from typing import Any, Dict

from flask import Blueprint, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from ..app_context import get_app_ctx
from ..rate_limit import rate_limit
from ..responses import api_error, api_success, get_pagination_params
from src.service.exceptions import ServiceError

logger = logging.getLogger("blockchain_audit")

anomaly_bp = Blueprint("anomaly", __name__, url_prefix="/api")


@anomaly_bp.route("/anomaly/train", methods=["POST"])
@rate_limit(limit=10, window_seconds=60, scope='anomaly_train')
@jwt_required()
def train_detector():
    """Train the anomaly detector using either clean blockchain data or synthetic normal data."""
    app_ctx = get_app_ctx()
    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    try:
        data, message = app_ctx.anomaly_service.train_detector(
            role=get_jwt().get("role", "viewer"),
            payload=payload,
            model_path=app_ctx.ml_model_path,
        )
        return api_success(data=data, message=message)
    except ServiceError as exc:
        return api_error(exc.message, exc.status_code, errors=exc.errors, error_code=exc.error_code, data=exc.data)


@anomaly_bp.route("/anomaly/stats", methods=["GET"])
@jwt_required()
def get_anomaly_stats():
    app_ctx = get_app_ctx()
    return api_success(data=app_ctx.anomaly_service.get_anomaly_stats())


@anomaly_bp.route("/alerts", methods=["GET"])
@jwt_required()
def get_alerts():
    app_ctx = get_app_ctx()
    page, per_page = get_pagination_params()
    data, pagination = app_ctx.anomaly_service.get_alerts(
        page=page,
        per_page=per_page,
        severity=request.args.get("severity"),
        resolved_param=request.args.get("resolved"),
    )
    return api_success(data=data, pagination=pagination)


@anomaly_bp.route("/alerts/<int:alert_id>/resolve", methods=["PUT"])
@jwt_required()
def resolve_alert(alert_id: int):
    app_ctx = get_app_ctx()
    try:
        app_ctx.anomaly_service.resolve_alert(
            role=get_jwt().get("role", "viewer"),
            alert_id=alert_id,
            resolved_by=get_jwt_identity(),
        )
        logger.info("Alert #%s resolved by %s", alert_id, get_jwt_identity())
        return api_success(message=f"Alert #{alert_id} marked as resolved")
    except ServiceError as exc:
        return api_error(exc.message, exc.status_code, errors=exc.errors, error_code=exc.error_code, data=exc.data)


@anomaly_bp.route("/demo/generate", methods=["POST"])
@jwt_required()
def generate_demo_data():
    app_ctx = get_app_ctx()
    payload = request.get_json(silent=True) or {}
    data, message = app_ctx.anomaly_service.generate_demo_data(get_jwt_identity(), payload)
    return api_success(data=data, message=message)
