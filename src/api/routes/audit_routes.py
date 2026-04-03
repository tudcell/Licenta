"""
Audit routes blueprint.
Handles blockchain integrity checking and audit log export.
"""

import logging
from flask import Blueprint, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from ..responses import api_success, api_error

logger = logging.getLogger('blockchain_audit')

audit_bp = Blueprint('audit', __name__, url_prefix='/api/audit')


@audit_bp.route('/integrity', methods=['GET'])
@jwt_required()
def check_integrity():
    """Checks complete system integrity."""
    return api_success(data=current_app.analyzer.validate_blockchain_integrity())


@audit_bp.route('/export', methods=['GET'])
@jwt_required()
def export_audit():
    """Exports complete audit log (admin only)."""
    # Check role
    claims = get_jwt()
    if claims.get('role') != 'admin':
        return api_error("Access forbidden. Required: admin", 403, error_code="FORBIDDEN")

    logger.info("Audit export requested by %s", get_jwt_identity())
    return current_app.analyzer.export_audit_log(), 200, {
        'Content-Type': 'application/json',
        'Content-Disposition': 'attachment; filename=audit_log.json'
    }

