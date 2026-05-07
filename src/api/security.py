"""Build a domain Principal from the current JWT context."""

from __future__ import annotations

from flask_jwt_extended import get_jwt, get_jwt_identity

from src.domain.authorization import Principal, parse_role


def current_principal() -> Principal:
    return Principal(
        username=get_jwt_identity(),
        role=parse_role(get_jwt().get("role")),
    )
