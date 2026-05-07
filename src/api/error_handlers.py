"""Maps domain errors and Flask defaults to standardized API responses."""

from __future__ import annotations

import logging

from flask import Flask

from src.domain.errors import (
    AuthError,
    ConflictError,
    DomainError,
    ForbiddenError,
    InternalError,
    NotFoundError,
    ValidationError,
)
from .responses import api_error

logger = logging.getLogger("blockchain_audit")

_DEFAULT_STATUS = {
    ValidationError: 400,
    AuthError: 401,
    ForbiddenError: 403,
    NotFoundError: 404,
    ConflictError: 409,
    InternalError: 500,
}


def _status_for(exc: DomainError) -> int:
    for cls, code in _DEFAULT_STATUS.items():
        if isinstance(exc, cls):
            return code
    return 400


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(DomainError)
    def handle_domain_error(exc: DomainError):
        return api_error(
            exc.message,
            _status_for(exc),
            errors=exc.errors,
            error_code=exc.error_code,
            data=exc.data,
        )

    @app.errorhandler(400)
    def bad_request(_error):
        return api_error("Invalid request", 400, error_code="BAD_REQUEST")

    @app.errorhandler(404)
    def not_found(_error):
        return api_error("Resource not found", 404, error_code="NOT_FOUND")

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return api_error("HTTP method not allowed", 405, error_code="METHOD_NOT_ALLOWED")

    @app.errorhandler(500)
    def internal_error(_error):
        logger.exception("Internal server error")
        return api_error("Internal server error", 500, error_code="INTERNAL_ERROR")
