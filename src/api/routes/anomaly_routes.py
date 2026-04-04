"""Anomaly detection routes blueprint."""

from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

from flask import Blueprint, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from ..app_context import get_app_ctx
from ..rate_limit import rate_limit
from ..responses import api_error, api_success, get_pagination_params

logger = logging.getLogger("blockchain_audit")

anomaly_bp = Blueprint("anomaly", __name__, url_prefix="/api")


ALLOWED_TRAINING_MODES = {"blockchain", "synthetic"}


def _require_operator_or_admin() -> Tuple[bool, Any]:
    claims = get_jwt()
    if claims.get("role") not in ("admin", "operator"):
        return False, api_error("Access forbidden. Required: admin, operator", 403, error_code="FORBIDDEN")
    return True, None


@anomaly_bp.route("/anomaly/train", methods=["POST"])
@rate_limit(limit=10, window_seconds=60, scope='anomaly_train')
@jwt_required()
def train_detector():
    """Train the anomaly detector using either clean blockchain data or synthetic normal data."""
    app_ctx = get_app_ctx()
    allowed, response = _require_operator_or_admin()
    if not allowed:
        return response

    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    mode = str(payload.get("mode") or ("synthetic" if payload.get("use_synthetic") else "blockchain")).lower()
    if mode not in ALLOWED_TRAINING_MODES:
        return api_error("Invalid training mode. Use 'blockchain' or 'synthetic'.", 400, error_code="INVALID_MODE")

    try:
        if mode == "synthetic":
            from src.utils.training_data_generator import TrainingDataGenerator

            sample_count = max(100, min(int(payload.get("sample_count", 800)), 5000))
            logger.info("Training detector with %s synthetic normal sample(s)", sample_count)
            generator = TrainingDataGenerator(num_users=20)
            transactions = generator.generate_only_normal(count=sample_count)
            app_ctx.analyzer.detector.fit(transactions)
            clean_count = len(transactions)
            message = f"Detector trained with {clean_count} synthetic normal samples"
        else:
            all_transactions = app_ctx.blockchain.get_all_transactions()
            clean_transactions = app_ctx.analyzer._get_clean_training_transactions(all_transactions)
            min_samples = app_ctx.analyzer.min_training_samples
            if len(clean_transactions) < min_samples:
                return api_error(
                    f"At least {min_samples} clean transactions required (have {len(clean_transactions)} clean out of {len(all_transactions)} total)",
                    400,
                    error_code="INSUFFICIENT_DATA",
                )
            app_ctx.analyzer.train_detector(all_transactions)
            transactions = clean_transactions
            clean_count = len(clean_transactions)
            message = f"Detector trained with {clean_count} clean blockchain transactions"

        app_ctx.analyzer.detector.save(app_ctx.ml_model_path)
        logger.info("ML model saved to %s", app_ctx.ml_model_path)

        return api_success(
            data={
                "training_mode": mode,
                "training_samples": len(transactions),
                "stats": app_ctx.analyzer.detector.training_stats,
                "model_saved": app_ctx.ml_model_path,
                "detector_fitted": app_ctx.analyzer.detector.is_fitted,
            },
            message=message,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error training detector")
        return api_error(f"Training error: {exc}", 500, error_code="TRAINING_ERROR")


@anomaly_bp.route("/anomaly/stats", methods=["GET"])
@jwt_required()
def get_anomaly_stats():
    app_ctx = get_app_ctx()
    analyzer_stats = app_ctx.analyzer.get_statistics()
    db_alert_stats = app_ctx.metadata_store.get_alert_stats()
    return api_success(data={**analyzer_stats, "persistent_alerts": db_alert_stats})


@anomaly_bp.route("/alerts", methods=["GET"])
@jwt_required()
def get_alerts():
    app_ctx = get_app_ctx()
    page, per_page = get_pagination_params()
    severity = request.args.get("severity")
    resolved_param = request.args.get("resolved")

    is_resolved = None
    if resolved_param is not None:
        is_resolved = resolved_param.lower() in ("true", "1", "yes")

    alerts, total = app_ctx.metadata_store.get_alerts(
        page=page,
        per_page=per_page,
        severity=severity,
        is_resolved=is_resolved,
    )
    pagination = {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": max(1, (total + per_page - 1) // per_page),
        "has_next": page * per_page < total,
        "has_prev": page > 1,
    }
    return api_success(data={"alerts": alerts, "count": len(alerts)}, pagination=pagination)


@anomaly_bp.route("/alerts/<int:alert_id>/resolve", methods=["PUT"])
@jwt_required()
def resolve_alert(alert_id: int):
    app_ctx = get_app_ctx()
    allowed, response = _require_operator_or_admin()
    if not allowed:
        return response

    resolved = app_ctx.metadata_store.resolve_alert(alert_id, get_jwt_identity())
    if resolved:
        logger.info("Alert #%s resolved by %s", alert_id, get_jwt_identity())
        return api_success(message=f"Alert #{alert_id} marked as resolved")
    return api_error(f"Alert #{alert_id} not found or already resolved", 404, error_code="ALERT_NOT_FOUND")


@anomaly_bp.route("/demo/generate", methods=["POST"])
@jwt_required()
def generate_demo_data():
    app_ctx = get_app_ctx()
    payload = request.get_json(silent=True) or {}
    count = max(1, min(int(payload.get("count", 50)), 500))
    include_anomalies = bool(payload.get("include_anomalies", True))
    anomaly_ratio = float(payload.get("anomaly_ratio", 0.10 if include_anomalies else 0.0))

    from src.utils.data_generator import DataGenerator

    generator = DataGenerator(app_ctx.wallet_manager)
    transactions = generator.generate_normal_transactions(count)
    labels = ["normal"] * len(transactions)

    if include_anomalies:
        anomaly_count = max(1, min(count // 2, int(round(count * anomaly_ratio))))
        anomaly_transactions = generator.generate_anomalies(anomaly_count)
        transactions.extend(anomaly_transactions)
        labels.extend(["anomaly"] * len(anomaly_transactions))

    combined = sorted(zip(transactions, labels), key=lambda item: item[0].timestamp)

    anomalies_detected = 0
    flagged_count = 0
    invalid_signature_count = 0

    for tx, _label in combined:
        report = app_ctx.analyzer.add_transaction(tx)
        status = "REJECTED"
        if report.signature_valid:
            status = "FLAGGED" if report.flagged_for_review else "PENDING"
        app_ctx.metadata_store.index_transaction(
            tx,
            block_index=None,
            tx_status=status,
            is_flagged=report.flagged_for_review,
        )

        if report.is_suspicious:
            anomalies_detected += 1
            if report.flagged_for_review:
                flagged_count += 1
            if not report.signature_valid:
                invalid_signature_count += 1
            app_ctx.metadata_store.save_alert(report)

    logger.info(
        "Demo data generated by %s: %s transaction(s), %s suspicious, %s flagged, %s invalid-signature",
        get_jwt_identity(),
        len(combined),
        anomalies_detected,
        flagged_count,
        invalid_signature_count,
    )

    return api_success(
        data={
            "generated": len(combined),
            "anomalies_detected": anomalies_detected,
            "flagged": flagged_count,
            "invalid_signatures": invalid_signature_count,
        },
        message=f"{len(combined)} transactions generated ({flagged_count} flagged for review)",
    )
