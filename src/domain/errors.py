"""Domain error hierarchy. HTTP-agnostic; the API layer maps to status codes."""

from __future__ import annotations

from typing import Any, Optional


class DomainError(Exception):
    """Base class for all domain/application errors."""

    default_code: Optional[str] = None

    def __init__(
            self,
            message: str,
            *,
            error_code: Optional[str] = None,
            errors: Optional[list] = None,
            data: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.default_code
        self.errors = errors
        self.data = data


class ValidationError(DomainError):
    default_code = "VALIDATION_ERROR"


class AuthError(DomainError):
    default_code = "AUTH_FAILED"


class ForbiddenError(DomainError):
    default_code = "FORBIDDEN"


class NotFoundError(DomainError):
    default_code = "NOT_FOUND"


class ConflictError(DomainError):
    default_code = "CONFLICT"


class InternalError(DomainError):
    default_code = "INTERNAL_ERROR"
