"""Repository adapter around wallet storage/lookup operations."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.domain.entities.wallet import Wallet, WalletManager


class WalletRepository:
    def __init__(self, wallet_manager: WalletManager):
        self._wallet_manager = wallet_manager

    @property
    def raw(self) -> WalletManager:
        return self._wallet_manager

    def get_wallet(self, name: str) -> Optional[Wallet]:
        return self._wallet_manager.get_wallet(name)

    def create_wallet(self, name: str, metadata: Dict[str, Any] = None) -> Wallet:
        return self._wallet_manager.create_wallet(name, metadata=metadata or {})

    def get_or_create_wallet(self, name: str, metadata: Dict[str, Any] = None) -> Wallet:
        wallet = self._wallet_manager.get_wallet(name)
        if wallet is not None:
            return wallet
        return self._wallet_manager.create_wallet(name, metadata=metadata or {})

    def list_wallets(self) -> list[dict]:
        return self._wallet_manager.list_wallets()

