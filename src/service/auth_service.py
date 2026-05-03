"""Authentication use-cases orchestrating metadata storage and password policies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.infrastructure.metadata_store import MetadataStore
from src.service.exceptions import ServiceError
from src.utils.password_security import hash_password, needs_rehash, verify_password


@dataclass
class AuthenticatedUser:
    username: str
    role: str
    wallet_name: Optional[str]


class AuthService:
    def __init__(self, metadata_store: MetadataStore):
        self.metadata_store = metadata_store

    def authenticate(self, username: str, password: str) -> AuthenticatedUser:
        user_record = self.metadata_store.get_user(username)
        if not user_record or not verify_password(password, user_record["password_hash"]):
            raise ServiceError("Invalid credentials", status_code=401, error_code="AUTH_FAILED")

        if needs_rehash(user_record["password_hash"]):
            self.metadata_store.update_password_hash(username, hash_password(password))
            user_record = self.metadata_store.get_user(username)

        self.metadata_store.update_last_login(username)
        return AuthenticatedUser(
            username=username,
            role=user_record["role"],
            wallet_name=user_record.get("wallet_name"),
        )

    def register_user(self, requester_role: str, username: str, password: str, role: str, wallet_name: Optional[str]) -> dict:
        self._require_admin(requester_role)
        self._validate_username(username)
        self._validate_password(password)
        self._validate_role(role)
        self._create_user_record(
            username=username,
            password=password,
            role=role,
            wallet_name=wallet_name,
        )
        return {"username": username, "role": role, "wallet_name": wallet_name}

    def register_viewer(self, username: str, password: str) -> dict:
        self._validate_username(username)
        self._validate_password(password)
        self._create_user_record(
            username=username,
            password=password,
            role="viewer",
            wallet_name=None,
        )
        return {"username": username, "role": "viewer", "wallet_name": None}

    def revoke_token(self, jti: str) -> None:
        self.metadata_store.revoke_token(jti)

    def get_user(self, username: str) -> Optional[dict]:
        return self.metadata_store.get_user(username)

    @staticmethod
    def _require_admin(requester_role: str) -> None:
        if requester_role != "admin":
            raise ServiceError("Access forbidden. Required: admin", status_code=403, error_code="FORBIDDEN")

    @staticmethod
    def _validate_username(username: str) -> None:
        if not username or len(username) < 3:
            raise ServiceError("Username must have at least 3 characters", status_code=400)

    @staticmethod
    def _validate_password(password: str) -> None:
        if not password or len(password) < 8:
            raise ServiceError("Password must have at least 8 characters", status_code=400)

    @staticmethod
    def _validate_role(role: str) -> None:
        if role not in ("admin", "operator", "viewer"):
            raise ServiceError("Invalid role. Options: admin, operator, viewer", status_code=400)

    def _create_user_record(self, username: str, password: str, role: str, wallet_name: Optional[str]) -> None:
        creation_successful = self.metadata_store.create_user(
            username=username,
            password_hash=hash_password(password),
            role=role,
            wallet_name=wallet_name,
        )
        if creation_successful:
            return
        raise ServiceError(f"User '{username}' already exists", status_code=409, error_code="USER_EXISTS")
