"""Service-layer error compatibility shim.

New code should raise concrete `DomainError` subclasses from `src.domain.errors`.
`ServiceError` is kept as a compatibility export so any external/legacy
imports keep working; it now inherits from `DomainError` and exposes a
status_code mapping handled by the API error handler.
"""

from __future__ import annotations

from typing import Any, Optional

from src.domain.errors import DomainError


class ServiceError(DomainError):
    """Backwards-compatible domain error carrying an explicit HTTP status."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        error_code: Optional[str] = None,
        errors: Optional[list] = None,
        data: Any = None,
    ) -> None:
        super().__init__(message, error_code=error_code, errors=errors, data=data)
        self.status_code = status_code
