"""Authentication use-cases orchestrating user storage and password policies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.domain.authorization import Principal, Role
from src.domain.errors import AuthError, ConflictError, ValidationError
from src.infrastructure.persistence.sqlite import TokenBlocklistRepository, UserRepository
from src.utils.password_security import hash_password, needs_rehash, verify_password


@dataclass(frozen=True)
class AuthenticatedUser:
    username: str
    role: Role
    wallet_name: Optional[str]


class AuthService:
    def __init__(self, users: UserRepository, tokens: TokenBlocklistRepository):
        self._users = users
        self._tokens = tokens

    def authenticate(self, username: str, password: str) -> AuthenticatedUser:
        user_record = self._users.get(username)
        if not user_record or not verify_password(password, user_record["password_hash"]):
            raise AuthError("Invalid credentials")

        if needs_rehash(user_record["password_hash"]):
            self._users.update_password_hash(username, hash_password(password))
            user_record = self._users.get(username)

        self._users.update_last_login(username)
        return AuthenticatedUser(
            username=username,
            role=Role(user_record["role"]),
            wallet_name=user_record.get("wallet_name"),
        )

    def register_user(self, principal: Principal, username: str, password: str, role: str, wallet_name: Optional[str]) -> dict:
        principal.require(Role.ADMIN)
        self._validate_username(username)
        self._validate_password(password)
        self._validate_role(role)
        self._create_user_record(username, password, role, wallet_name)
        return {"username": username, "role": role, "wallet_name": wallet_name}

    def register_viewer(self, username: str, password: str) -> dict:
        self._validate_username(username)
        self._validate_password(password)
        self._create_user_record(username, password, Role.VIEWER.value, None)
        return {"username": username, "role": Role.VIEWER.value, "wallet_name": None}

    def revoke_token(self, jti: str) -> None:
        self._tokens.revoke(jti)

    def get_user(self, username: str) -> Optional[dict]:
        return self._users.get(username)

    @staticmethod
    def _validate_username(username: str) -> None:
        if not username or len(username) < 3:
            raise ValidationError("Username must have at least 3 characters")

    @staticmethod
    def _validate_password(password: str) -> None:
        if not password or len(password) < 8:
            raise ValidationError("Password must have at least 8 characters")

    @staticmethod
    def _validate_role(role: str) -> None:
        if role not in {item.value for item in Role}:
            raise ValidationError("Invalid role. Options: admin, operator, viewer")

    def _create_user_record(self, username: str, password: str, role: str, wallet_name: Optional[str]) -> None:
        if self._users.create(username=username, password_hash=hash_password(password), role=role, wallet_name=wallet_name):
            return
        raise ConflictError(f"User '{username}' already exists", error_code="USER_EXISTS")
