"""
Anomaly detection routes blueprint.
Handles ML training, statistics, alerts, and demo data generation.
"""

import logging
from flask import Blueprint, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from ..responses import api_success, api_error, get_pagination_params

logger = logging.getLogger('blockchain_audit')

anomaly_bp = Blueprint('anomaly', __name__, url_prefix='/api')


@anomaly_bp.route('/anomaly/train', methods=['POST'])
@jwt_required()
def train_detector():
    """
    Trains the anomaly detector.

    By default uses blockchain transactions.
    Optionally send JSON body with:
    - use_synthetic: true (generates synthetic training data)
    - sample_count: number of samples (default 500, max 2000)

    Requires admin or operator role.
    """
    claims = get_jwt()
    if claims.get('role') not in ('admin', 'operator'):
        return api_error("Access forbidden. Required: admin, operator", 403, error_code="FORBIDDEN")

    try:
        # Check if synthetic training requested (optional JSON body)
        data = request.get_json(silent=True) or {}
        use_synthetic = data.get('use_synthetic', False)

        if use_synthetic:
            # Generate synthetic training data
            from src.utils.training_data_generator import TrainingDataGenerator

            sample_count = min(data.get('sample_count', 800), 5000)
            logger.info("Generating %d synthetic training samples...", sample_count)

            generator = TrainingDataGenerator(num_users=20)
            transactions = generator.generate_only_normal(count=sample_count)
            current_app.analyzer.detector.fit(transactions)
            message = f"Detector trained with {sample_count} synthetic samples"
        else:
            # Use blockchain transactions (original behavior)
            transactions = current_app.blockchain.get_all_transactions()
            min_samples = current_app.analyzer.min_training_samples

            if len(transactions) < min_samples:
                return api_error(
                    f"At least {min_samples} transactions required (have {len(transactions)})",
                    400, error_code="INSUFFICIENT_DATA"
                )

            current_app.analyzer.train_detector(transactions)
            message = f"Detector trained with {len(transactions)} blockchain transactions"

        # Save model to disk
        current_app.analyzer.detector.save(current_app.ml_model_path)
        logger.info("ML model saved to %s", current_app.ml_model_path)

        return api_success(
            data={
                'training_samples': len(transactions),
                'stats': current_app.analyzer.detector.training_stats,
                'model_saved': current_app.ml_model_path,
                'detector_fitted': current_app.analyzer.detector.is_fitted,
            },
            message=message
        )
    except Exception as e:
        logger.exception("Error training detector")
        return api_error(f"Training error: {str(e)}", 500, error_code="TRAINING_ERROR")


@anomaly_bp.route('/anomaly/stats', methods=['GET'])
@jwt_required()
def get_anomaly_stats():
    """Returns combined anomaly statistics (memory + SQLite)."""
    analyzer_stats = current_app.analyzer.get_statistics()
    db_alert_stats = current_app.metadata_store.get_alert_stats()

    return api_success(data={
        **analyzer_stats,
        'persistent_alerts': db_alert_stats
    })


@anomaly_bp.route('/alerts', methods=['GET'])
@jwt_required()
def get_alerts():
    """
    Returns paginated anomaly alerts from SQLite.

    Query params:
        page, per_page: Pagination
        severity: Filter (low, medium, high)
        resolved: Filter (true/false)
    """
    page, per_page = get_pagination_params()
    severity = request.args.get('severity')
    resolved_param = request.args.get('resolved')

    is_resolved = None
    if resolved_param is not None:
        is_resolved = resolved_param.lower() in ('true', '1', 'yes')

    alerts, total = current_app.metadata_store.get_alerts(
        page=page, per_page=per_page,
        severity=severity, is_resolved=is_resolved
    )

    pagination = {
        'page': page, 'per_page': per_page,
        'total': total,
        'total_pages': max(1, (total + per_page - 1) // per_page),
        'has_next': page * per_page < total,
        'has_prev': page > 1,
    }

    return api_success(data={
        'alerts': alerts,
        'count': len(alerts)
    }, pagination=pagination)


@anomaly_bp.route('/alerts/<int:alert_id>/resolve', methods=['PUT'])
@jwt_required()
def resolve_alert(alert_id):
    """Marks an alert as resolved."""
    # Check role
    claims = get_jwt()
    if claims.get('role') not in ('admin', 'operator'):
        return api_error("Access forbidden. Required: admin, operator", 403, error_code="FORBIDDEN")

    resolved = current_app.metadata_store.resolve_alert(alert_id, get_jwt_identity())
    if resolved:
        logger.info("Alert #%d resolved by %s", alert_id, get_jwt_identity())
        return api_success(message=f"Alert #{alert_id} marked as resolved")
    return api_error(f"Alert #{alert_id} not found or already resolved",
                     404, error_code="ALERT_NOT_FOUND")


@anomaly_bp.route('/demo/generate', methods=['POST'])
@jwt_required()
def generate_demo_data():
    """
    Generates demonstration data.

    Body JSON:
        { "count": 50, "include_anomalies": true }
    """
    data = request.get_json() or {}
    count = min(data.get('count', 50), 500)
    include_anomalies = data.get('include_anomalies', True)

    from src.utils.data_generator import DataGenerator
    generator = DataGenerator(current_app.wallet_manager)

    transactions = generator.generate_normal_transactions(count)

    if include_anomalies:
        anomalies = generator.generate_anomalies(max(1, count // 10))
        transactions.extend(anomalies)

    anomalies_detected = 0
    quarantined_count = 0
    for tx in transactions:
        report = current_app.analyzer.add_transaction(tx)

        if not report.quarantined:
            current_app.metadata_store.index_transaction(tx)

        if report.is_suspicious:
            anomalies_detected += 1
            current_app.metadata_store.save_alert(report)
        if report.quarantined:
            quarantined_count += 1

    logger.info("Demo data: %d tx, %d anomalies, %d quarantined by %s",
                 len(transactions), anomalies_detected, quarantined_count,
                 get_jwt_identity())

    return api_success(
        data={
            'generated': len(transactions),
            'anomalies_detected': anomalies_detected,
            'quarantined': quarantined_count
        },
        message=f"{len(transactions)} transactions generated ({quarantined_count} quarantined)"
    )

