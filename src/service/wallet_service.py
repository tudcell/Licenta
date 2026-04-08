"""Wallet service use-cases."""

from __future__ import annotations

from typing import Dict, Tuple

from src.repository import MetadataRepository, WalletRepository


class WalletService:
    def __init__(self, wallet_repository: WalletRepository, metadata_repository: MetadataRepository):
        self.wallet_repository = wallet_repository
        self.metadata_repository = metadata_repository

    def list_wallets_for_user(self, username: str, role: str):
        wallets = self.wallet_repository.list_wallets()
        user = self.metadata_repository.get_user(username)
        if role != 'admin' and user and user.get('wallet_name'):
            wallets = [wallet for wallet in wallets if wallet['name'] == user['wallet_name']]
        return wallets

    def create_wallet(self, name: str, requested_owner: str, created_by: str, creator_role: str):
        creator = self.metadata_repository.get_user(created_by)
        if not creator:
            return None, 'AUTH_FAILED'

        if creator_role != 'admin' and requested_owner != created_by:
            return None, 'FORBIDDEN'

        owner_user = self.metadata_repository.get_user(requested_owner)
        if not owner_user:
            return None, 'USER_NOT_FOUND'

        if creator_role != 'admin' and creator.get('wallet_name') and creator['wallet_name'] != name:
            return None, 'WALLET_ALREADY_ASSIGNED'

        wallet = self.wallet_repository.create_wallet(name, {'owner': requested_owner})
        assigned = self.metadata_repository.assign_wallet_to_user(requested_owner, name)
        if not assigned:
            return None, 'USER_NOT_FOUND'
        return wallet, None

    def get_wallet_details(self, wallet_name: str, username: str, role: str) -> Tuple[Dict, int]:
        wallet = self.wallet_repository.get_wallet(wallet_name)
        if not wallet:
            return {'error': 'WALLET_NOT_FOUND'}, 404

        user = self.metadata_repository.get_user(username)
        if role != 'admin' and user and user.get('wallet_name') != wallet_name:
            return {'error': 'FORBIDDEN'}, 403

        return {'wallet': wallet.to_dict(include_private_key=False)}, 200
