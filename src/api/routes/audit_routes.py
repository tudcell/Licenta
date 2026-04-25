"""
Audit routes blueprint.
Handles blockchain integrity checking and audit log export.
"""

import logging

from flask import Blueprint, request, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from ..app_context import get_app_ctx
from ..rate_limit import rate_limit
from ..responses import api_success, api_error
from src.service.exceptions import ServiceError

logger = logging.getLogger('blockchain_audit')

audit_bp = Blueprint('audit', __name__, url_prefix='/api/audit')

@audit_bp.route('/integrity', methods=['GET'])
@jwt_required()
def check_integrity():
    """Checks complete system integrity."""
    app_ctx = get_app_ctx()
    return api_success(data=app_ctx.audit_service.check_integrity())


@audit_bp.route('/export', methods=['GET'])
@jwt_required()
def export_audit():
    """Exports complete audit log (admin only)."""
    app_ctx = get_app_ctx()
    try:
        export_payload = app_ctx.audit_service.export_audit_log(get_jwt().get('role', 'viewer'))
        logger.info("Audit export requested by %s", get_jwt_identity())
        return export_payload, 200, {
            'Content-Type': 'application/json',
            'Content-Disposition': 'attachment; filename=audit_log.json'
        }
    except ServiceError as exc:
        return api_error(exc.message, exc.status_code, errors=exc.errors, error_code=exc.error_code, data=exc.data)


@audit_bp.route('/backups', methods=['GET'])
@jwt_required()
def get_backups():
    app_ctx = get_app_ctx()
    try:
        snapshots = app_ctx.audit_service.list_backups(get_jwt().get('role', 'viewer'))
        return api_success(data={'snapshots': snapshots})
    except ServiceError as exc:
        return api_error(exc.message, exc.status_code, errors=exc.errors, error_code=exc.error_code, data=exc.data)


@audit_bp.route('/backup', methods=['POST'])
@rate_limit(limit=5, window_seconds=60, scope='audit_backup')
@jwt_required()
def create_backup():
    app_ctx = get_app_ctx()
    try:
        data = app_ctx.audit_service.create_backup(
            role=get_jwt().get('role', 'viewer'),
            requested_by=get_jwt_identity(),
        )
        return api_success(data=data, message='Snapshot created successfully', status_code=201)
    except ServiceError as exc:
        return api_error(exc.message, exc.status_code, errors=exc.errors, error_code=exc.error_code, data=exc.data)


@audit_bp.route('/restore', methods=['POST'])
@rate_limit(limit=3, window_seconds=60, scope='audit_restore')
@jwt_required()
def restore_backup():
    app_ctx = get_app_ctx()
    payload = request.get_json(silent=True) or {}
    snapshot_name = (payload.get('snapshot_name') or '').strip()
    try:
        data = app_ctx.audit_service.restore_backup(
            role=get_jwt().get('role', 'viewer'),
            requested_by=get_jwt_identity(),
            snapshot_name=snapshot_name,
        )
        return api_success(data=data, message='Snapshot restored. Restart the app to reload in-memory state.')
    except ServiceError as exc:
        return api_error(exc.message, exc.status_code, errors=exc.errors, error_code=exc.error_code, data=exc.data)


@audit_bp.route('/backups/<snapshot_name>/download', methods=['GET'])
@jwt_required()
def download_backup(snapshot_name: str):
    app_ctx = get_app_ctx()
    try:
        snapshot_path = app_ctx.audit_service.get_backup_download_path(
            role=get_jwt().get('role', 'viewer'),
            snapshot_name=snapshot_name,
        )
    except ServiceError as exc:
        return api_error(exc.message, exc.status_code, errors=exc.errors, error_code=exc.error_code, data=exc.data)

    return send_file(snapshot_path.resolve(), mimetype='application/zip', as_attachment=True, download_name=snapshot_name)

