"""Repository for wallet persistence and retrieval."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.domain import Wallet, WalletManager


class WalletRepository:
    """Persistence gateway around wallet manager."""

    def __init__(self, wallet_manager: WalletManager):
        self._wallet_manager = wallet_manager

    @property
    def wallet_manager(self) -> WalletManager:
        return self._wallet_manager

    def create_wallet(self, name: str, metadata: Optional[Dict[str, Any]] = None, persist_private_key: bool = True) -> Wallet:
        return self._wallet_manager.create_wallet(name, metadata=metadata, persist_private_key=persist_private_key)

    def get_wallet(self, name: str) -> Optional[Wallet]:
        return self._wallet_manager.get_wallet(name)

    def get_wallet_by_address(self, address: str) -> Optional[Wallet]:
        return self._wallet_manager.get_wallet_by_address(address)

    def list_wallets(self):
        return self._wallet_manager.list_wallets()
