"""Audit routes blueprint."""

import logging

from flask import Blueprint, request, send_file
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from ..app_context import get_app_ctx
from ..rate_limit import rate_limit
from ..responses import api_success

logger = logging.getLogger("blockchain_audit")

audit_bp = Blueprint("audit", __name__, url_prefix="/api/audit")


@audit_bp.route("/integrity", methods=["GET"])
@jwt_required()
def check_integrity():
    app_ctx = get_app_ctx()
    return api_success(data=app_ctx.audit_service.check_integrity())


@audit_bp.route("/export", methods=["GET"])
@jwt_required()
def export_audit():
    app_ctx = get_app_ctx()
    export_payload = app_ctx.audit_service.export_audit_log(get_jwt().get("role", "viewer"))
    logger.info("Audit export requested by %s", get_jwt_identity())
    return export_payload, 200, {
        "Content-Type": "application/json",
        "Content-Disposition": "attachment; filename=audit_log.json",
    }


@audit_bp.route("/backups", methods=["GET"])
@jwt_required()
def get_backups():
    app_ctx = get_app_ctx()
    snapshots = app_ctx.audit_service.list_backups(get_jwt().get("role", "viewer"))
    return api_success(data={"snapshots": snapshots})


@audit_bp.route("/backup", methods=["POST"])
@rate_limit(limit=5, window_seconds=60, scope="audit_backup")
@jwt_required()
def create_backup():
    app_ctx = get_app_ctx()
    data = app_ctx.audit_service.create_backup(
        role=get_jwt().get("role", "viewer"),
        requested_by=get_jwt_identity(),
    )
    return api_success(data=data, message="Snapshot created successfully", status_code=201)


@audit_bp.route("/restore", methods=["POST"])
@rate_limit(limit=3, window_seconds=60, scope="audit_restore")
@jwt_required()
def restore_backup():
    app_ctx = get_app_ctx()
    request_payload = request.get_json(silent=True) or {}
    data = app_ctx.audit_service.restore_backup(
        role=get_jwt().get("role", "viewer"),
        requested_by=get_jwt_identity(),
        snapshot_name=(request_payload.get("snapshot_name") or "").strip(),
    )
    return api_success(data=data, message="Snapshot restored. Restart the app to reload in-memory state.")


@audit_bp.route("/backups/<snapshot_name>/download", methods=["GET"])
@jwt_required()
def download_backup(snapshot_name: str):
    app_ctx = get_app_ctx()
    snapshot_path = app_ctx.audit_service.get_backup_download_path(
        role=get_jwt().get("role", "viewer"),
        snapshot_name=snapshot_name,
    )
    return send_file(
        snapshot_path.resolve(),
        mimetype="application/zip",
        as_attachment=True,
        download_name=snapshot_name,
    )
