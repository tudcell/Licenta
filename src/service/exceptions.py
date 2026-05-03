"""Service-layer exceptions used to keep controller code thin."""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ServiceError(Exception):
    message: str
    status_code: int = 400
    error_code: Optional[str] = None
    errors: Optional[list] = None
    data: Any = None

