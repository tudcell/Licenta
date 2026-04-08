"""Authentication service use-cases."""

from __future__ import annotations

from typing import Dict, Optional

from flask_jwt_extended import create_access_token, create_refresh_token

from src.api.auth import hash_password, needs_rehash, verify_password
from src.repository import MetadataRepository


class AuthService:
    def __init__(self, metadata_repository: MetadataRepository):
        self.metadata_repository = metadata_repository

    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        user = self.metadata_repository.get_user(username)
        if not user or not verify_password(password, user['password_hash']):
            return None

        if needs_rehash(user['password_hash']):
            self.metadata_repository.update_password_hash(username, hash_password(password))
            user = self.metadata_repository.get_user(username)

        additional_claims = {'role': user['role'], 'wallet_name': user.get('wallet_name')}
        access_token = create_access_token(identity=username, additional_claims=additional_claims)
        refresh_token = create_refresh_token(identity=username, additional_claims=additional_claims)
        self.metadata_repository.update_last_login(username)

        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': {
                'username': username,
                'role': user['role'],
                'wallet_name': user.get('wallet_name')
            }
        }

    def refresh_access_token(self, identity: str) -> str:
        user = self.metadata_repository.get_user(identity)
        return create_access_token(
            identity=identity,
            additional_claims={
                'role': user['role'] if user else 'viewer',
                'wallet_name': user.get('wallet_name') if user else None,
            }
        )

    def logout(self, jti: str):
        self.metadata_repository.revoke_token(jti)

    def register_user(self, username: str, password: str, role: str, wallet_name: Optional[str] = None) -> bool:
        return self.metadata_repository.create_user(
            username=username,
            password_hash=hash_password(password),
            role=role,
            wallet_name=wallet_name,
        )
