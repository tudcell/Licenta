"""Authorization primitives: Role enum, Principal value object, single guard."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from src.domain.errors import ForbiddenError


class Role(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


def parse_role(value: str | None) -> Role:
    try:
        return Role((value or "viewer").lower())
    except ValueError:
        return Role.VIEWER


@dataclass(frozen=True)
class Principal:
    username: str
    role: Role
    wallet_name: Optional[str] = None

    def require(self, *allowed: Role) -> None:
        if self.role not in allowed:
            names = ", ".join(item.value for item in allowed)
            raise ForbiddenError(f"Access forbidden. Required: {names}")
