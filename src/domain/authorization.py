"""Authorization primitives: roles, principal, and a single guard helper."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional

from src.domain.errors import ForbiddenError


class Role(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"

    @classmethod
    def from_string(cls, value: str | None) -> "Role":
        try:
            return cls((value or "viewer").lower())
        except ValueError:
            return cls.VIEWER


@dataclass(frozen=True)
class Principal:
    username: str
    role: Role
    wallet_name: Optional[str] = None

    def is_admin(self) -> bool:
        return self.role is Role.ADMIN

    def require(self, *allowed: Role) -> None:
        require_role(self.role, *allowed)


def require_role(role: Role | str, *allowed: Role) -> None:
    """Raise ForbiddenError if `role` is not in `allowed`."""
    role_value = role.value if isinstance(role, Role) else str(role or "").lower()
    allowed_values = tuple(item.value for item in allowed)
    if role_value not in allowed_values:
        names = ", ".join(allowed_values)
        raise ForbiddenError(f"Access forbidden. Required: {names}")


def require_any_of(role: Role | str, allowed: Iterable[Role]) -> None:
    require_role(role, *list(allowed))
