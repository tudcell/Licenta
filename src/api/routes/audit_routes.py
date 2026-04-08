"""Audit controller routes."""

import logging

from flask import Blueprint, request, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from ..app_context import get_app_ctx
from ..rate_limit import rate_limit
from ..responses import api_success, api_error

logger = logging.getLogger('blockchain_audit')

audit_bp = Blueprint('audit', __name__, url_prefix='/api/audit')


def _require_admin():
    claims = get_jwt()
    if claims.get('role') != 'admin':
        return api_error("Access forbidden. Required: admin", 403, error_code="FORBIDDEN")
    return None


@audit_bp.route('/integrity', methods=['GET'])
@jwt_required()
def check_integrity():
    app_ctx = get_app_ctx()
    return api_success(data=app_ctx.audit_service.check_integrity())


@audit_bp.route('/export', methods=['GET'])
@jwt_required()
def export_audit():
    app_ctx = get_app_ctx()
    forbidden = _require_admin()
    if forbidden:
        return forbidden

    logger.info("Audit export requested by %s", get_jwt_identity())
    return app_ctx.audit_service.export_audit(), 200, {
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

    return api_success(data={'snapshots': app_ctx.audit_service.list_backups()})


@audit_bp.route('/backup', methods=['POST'])
@rate_limit(limit=5, window_seconds=60, scope='audit_backup')
@jwt_required()
def create_backup_route():
    app_ctx = get_app_ctx()
    forbidden = _require_admin()
    if forbidden:
        return forbidden

    snapshot = app_ctx.audit_service.create_backup()
    logger.info("Backup created by %s: %s", get_jwt_identity(), snapshot.get('name'))
    return api_success(data={'snapshot_name': snapshot['name'], 'pruned': snapshot.get('pruned', [])}, message='Backup created successfully', status_code=201)


@audit_bp.route('/backups/<snapshot_name>/download', methods=['GET'])
@jwt_required()
def download_backup(snapshot_name: str):
    app_ctx = get_app_ctx()
    forbidden = _require_admin()
    if forbidden:
        return forbidden

    try:
        snapshot_path = app_ctx.audit_service.get_backup_path(snapshot_name)
    except (FileNotFoundError, ValueError):
        return api_error('Snapshot not found', 404, error_code='SNAPSHOT_NOT_FOUND')

    return send_file(snapshot_path, mimetype='application/zip', as_attachment=True, download_name=snapshot_path.name)


@audit_bp.route('/restore', methods=['POST'])
@rate_limit(limit=3, window_seconds=300, scope='audit_restore')
@jwt_required()
def restore_backup_route():
    app_ctx = get_app_ctx()
    forbidden = _require_admin()
    if forbidden:
        return forbidden

    payload = request.get_json(silent=True) or {}
    snapshot_name = payload.get('snapshot_name')
    if not snapshot_name:
        return api_error("Field 'snapshot_name' is required", 400, error_code='VALIDATION_ERROR')

    try:
        result = app_ctx.audit_service.restore_backup(snapshot_name)
        logger.warning('System restored from snapshot %s by %s', snapshot_name, get_jwt_identity())
        return api_success(data=result, message='Snapshot restored successfully')
    except FileNotFoundError:
        return api_error('Snapshot not found', 404, error_code='SNAPSHOT_NOT_FOUND')
    except ValueError as exc:
        return api_error(str(exc), 400, error_code='SNAPSHOT_INVALID')
    except Exception as exc:  # noqa: BLE001
        logger.exception('Snapshot restore failed')
        return api_error(f'Restore failed: {exc}', 500, error_code='RESTORE_FAILED')
