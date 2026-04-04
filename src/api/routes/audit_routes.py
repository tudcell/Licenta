"""
Audit routes blueprint.
Handles blockchain integrity checking and audit log export.
"""

import logging
from pathlib import Path

from flask import Blueprint, request, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from ..app_context import get_app_ctx
from ..rate_limit import rate_limit
from ..responses import api_success, api_error
from src.utils.snapshot_manager import (
    create_snapshot,
    get_snapshot_path,
    list_snapshots,
    restore_snapshot,
)

logger = logging.getLogger('blockchain_audit')

audit_bp = Blueprint('audit', __name__, url_prefix='/api/audit')


def _require_admin():
    claims = get_jwt()
    if claims.get('role') != 'admin':
        return api_error("Access forbidden. Required: admin", 403, error_code="FORBIDDEN")
    return None


def _snapshot_paths(app_ctx):
    data_dir = Path(app_ctx.blockchain.config.data_dir).parent
    return data_dir / 'backups', {
        'blockchain': Path(app_ctx.blockchain.config.data_dir),
        'wallets': Path(app_ctx.wallet_manager.wallets_dir),
        'metadata_db': Path(app_ctx.metadata_store.db_path),
        'ml_model': Path(app_ctx.ml_model_path),
    }


@audit_bp.route('/integrity', methods=['GET'])
@jwt_required()
def check_integrity():
    """Checks complete system integrity."""
    app_ctx = get_app_ctx()
    return api_success(data=app_ctx.analyzer.validate_blockchain_integrity())


@audit_bp.route('/export', methods=['GET'])
@jwt_required()
def export_audit():
    """Exports complete audit log (admin only)."""
    app_ctx = get_app_ctx()
    forbidden = _require_admin()
    if forbidden:
        return forbidden

    logger.info("Audit export requested by %s", get_jwt_identity())
    return app_ctx.analyzer.export_audit_log(), 200, {
        'Content-Type': 'application/json',
        'Content-Disposition': 'attachment; filename=audit_log.json'
    }


@audit_bp.route('/backups', methods=['GET'])
@jwt_required()
def get_backups():
    app_ctx = get_app_ctx()
    forbidden = _require_admin()
    if forbidden:
        return forbidden

    snapshot_dir, _ = _snapshot_paths(app_ctx)
    return api_success(data={'snapshots': list_snapshots(snapshot_dir)})


@audit_bp.route('/backup', methods=['POST'])
@rate_limit(limit=5, window_seconds=60, scope='audit_backup')
@jwt_required()
def create_backup():
    app_ctx = get_app_ctx()
    forbidden = _require_admin()
    if forbidden:
        return forbidden

    snapshot_dir, sources = _snapshot_paths(app_ctx)
    snapshot = create_snapshot(snapshot_dir, sources, retention_count=app_ctx.snapshot_retention_count)
    logger.info("Snapshot created by %s: %s", get_jwt_identity(), snapshot['name'])
    return api_success(
        data={
            'snapshot_name': snapshot['name'],
            'manifest': snapshot['manifest'],
            'pruned_snapshots': snapshot.get('pruned', []),
        },
        message='Snapshot created successfully',
        status_code=201,
    )


@audit_bp.route('/restore', methods=['POST'])
@rate_limit(limit=3, window_seconds=60, scope='audit_restore')
@jwt_required()
def restore_backup():
    app_ctx = get_app_ctx()
    forbidden = _require_admin()
    if forbidden:
        return forbidden

    payload = request.get_json(silent=True) or {}
    snapshot_name = (payload.get('snapshot_name') or '').strip()
    if not snapshot_name:
        return api_error("Field 'snapshot_name' is required", 400, error_code="VALIDATION_ERROR")

    snapshot_dir, targets = _snapshot_paths(app_ctx)

    # Always snapshot current state before restore because restore is destructive.
    pre_restore_snapshot = create_snapshot(snapshot_dir, targets, retention_count=app_ctx.snapshot_retention_count)

    try:
        restore_result = restore_snapshot(snapshot_dir, snapshot_name, targets)
    except FileNotFoundError as exc:
        return api_error(str(exc), 404, error_code="SNAPSHOT_NOT_FOUND")
    except ValueError as exc:
        return api_error(str(exc), 400, error_code="INVALID_SNAPSHOT")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Snapshot restore failed")
        return api_error(f"Restore failed: {exc}", 500, error_code="RESTORE_FAILED")

    logger.warning(
        "Snapshot restored by %s: target=%s pre_restore=%s",
        get_jwt_identity(),
        snapshot_name,
        pre_restore_snapshot['name'],
    )
    return api_success(
        data={
            'restored_snapshot': restore_result['name'],
            'restored_components': restore_result['restored'],
            'pre_restore_snapshot': pre_restore_snapshot['name'],
            'pruned_snapshots': pre_restore_snapshot.get('pruned', []),
            'restart_required': True,
        },
        message='Snapshot restored. Restart the app to reload in-memory state.',
    )


@audit_bp.route('/backups/<snapshot_name>/download', methods=['GET'])
@jwt_required()
def download_backup(snapshot_name: str):
    app_ctx = get_app_ctx()
    forbidden = _require_admin()
    if forbidden:
        return forbidden

    snapshot_dir, _ = _snapshot_paths(app_ctx)
    try:
        snapshot_path = get_snapshot_path(snapshot_dir, snapshot_name)
    except FileNotFoundError as exc:
        return api_error(str(exc), 404, error_code="SNAPSHOT_NOT_FOUND")
    except ValueError as exc:
        return api_error(str(exc), 400, error_code="INVALID_SNAPSHOT")

    return send_file(snapshot_path.resolve(), mimetype='application/zip', as_attachment=True, download_name=snapshot_name)


