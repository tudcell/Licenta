"""Authentication use-cases orchestrating repository and password policies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.repository.metadata_repository import MetadataRepository
from src.service.exceptions import ServiceError
from src.utils.password_security import hash_password, needs_rehash, verify_password


@dataclass
class AuthenticatedUser:
    username: str
    role: str
    wallet_name: Optional[str]


class AuthService:
    def __init__(self, metadata_repository: MetadataRepository):
        self.metadata_repository = metadata_repository

    def authenticate(self, username: str, password: str) -> AuthenticatedUser:
        user = self.metadata_repository.get_user(username)
        if not user or not verify_password(password, user["password_hash"]):
            raise ServiceError("Invalid credentials", status_code=401, error_code="AUTH_FAILED")

        if needs_rehash(user["password_hash"]):
            self.metadata_repository.update_password_hash(username, hash_password(password))
            user = self.metadata_repository.get_user(username)

        self.metadata_repository.update_last_login(username)
        return AuthenticatedUser(username=username, role=user["role"], wallet_name=user.get("wallet_name"))

    def register_user(self, requester_role: str, username: str, password: str, role: str, wallet_name: Optional[str]) -> dict:
        if requester_role != "admin":
            raise ServiceError("Access forbidden. Required: admin", status_code=403, error_code="FORBIDDEN")

        if not username or len(username) < 3:
            raise ServiceError("Username must have at least 3 characters", status_code=400)
        if not password or len(password) < 8:
            raise ServiceError("Password must have at least 8 characters", status_code=400)
        if role not in ("admin", "operator", "viewer"):
            raise ServiceError("Invalid role. Options: admin, operator, viewer", status_code=400)

        success = self.metadata_repository.create_user(
            username=username,
            password_hash=hash_password(password),
            role=role,
            wallet_name=wallet_name,
        )
        if not success:
            raise ServiceError(f"User '{username}' already exists", status_code=409, error_code="USER_EXISTS")

        return {"username": username, "role": role, "wallet_name": wallet_name}

    def revoke_token(self, jti: str) -> None:
        self.metadata_repository.revoke_token(jti)

