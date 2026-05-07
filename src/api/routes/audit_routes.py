"""Audit (integrity) + snapshot/backup routes blueprint."""

import json
import logging

from flask import Blueprint, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..app_context import get_app_ctx
from ..rate_limit import rate_limit
from ..responses import api_success
from ..security import current_principal

logger = logging.getLogger("blockchain_audit")

audit_bp = Blueprint("audit", __name__, url_prefix="/api/audit")


@audit_bp.route("/integrity", methods=["GET"])
@jwt_required()
def check_integrity():
    app_ctx = get_app_ctx()
    return api_success(data=app_ctx.integrity_service.check_integrity())


@audit_bp.route("/export", methods=["GET"])
@jwt_required()
def export_audit():
    app_ctx = get_app_ctx()
    payload = app_ctx.integrity_service.export_audit_log(current_principal())
    logger.info("Audit export requested by %s", get_jwt_identity())
    return json.dumps(payload, ensure_ascii=False, indent=2), 200, {
        "Content-Type": "application/json",
        "Content-Disposition": "attachment; filename=audit_log.json",
    }


@audit_bp.route("/backups", methods=["GET"])
@jwt_required()
def get_backups():
    app_ctx = get_app_ctx()
    snapshots = app_ctx.backup_service.list_backups(current_principal())
    return api_success(data={"snapshots": snapshots})


@audit_bp.route("/backup", methods=["POST"])
@rate_limit(limit=5, window_seconds=60, scope="audit_backup")
@jwt_required()
def create_backup():
    app_ctx = get_app_ctx()
    data = app_ctx.backup_service.create_backup(current_principal())
    return api_success(data=data, message="Snapshot created successfully", status_code=201)


@audit_bp.route("/restore", methods=["POST"])
@rate_limit(limit=3, window_seconds=60, scope="audit_restore")
@jwt_required()
def restore_backup():
    app_ctx = get_app_ctx()
    request_payload = request.get_json(silent=True) or {}
    data = app_ctx.backup_service.restore_backup(
        principal=current_principal(),
        snapshot_name=(request_payload.get("snapshot_name") or "").strip(),
    )
    return api_success(data=data, message="Snapshot restored. Restart the app to reload in-memory state.")


@audit_bp.route("/backups/<snapshot_name>/download", methods=["GET"])
@jwt_required()
def download_backup(snapshot_name: str):
    app_ctx = get_app_ctx()
    snapshot_path = app_ctx.backup_service.get_backup_download_path(
        principal=current_principal(),
        snapshot_name=snapshot_name,
    )
    return send_file(
        snapshot_path.resolve(),
        mimetype="application/zip",
        as_attachment=True,
        download_name=snapshot_name,
    )
