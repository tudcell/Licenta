"""Wallet entity. Pure domain object; persistence + encryption live in adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.domain.entities.transaction import Transaction
from src.domain.policies.digital_signature import DigitalSignature, KeyPair


@dataclass
class Wallet:
    name: str
    _key_pair: KeyPair = field(default=None, repr=False)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self._key_pair is None:
            self._key_pair = DigitalSignature.generate_key_pair()

    @property
    def address(self) -> str:
        return self._key_pair.get_address()

    @property
    def public_key(self) -> str:
        return self._key_pair.get_public_key_hex()

    @property
    def private_key(self) -> str:
        return self._key_pair.get_private_key_hex()

    def sign_transaction(self, transaction: Transaction) -> Transaction:
        transaction.public_key = self.public_key
        transaction.sign(self.private_key)
        return transaction

    def create_and_sign_transaction(self, transaction_type, data: Dict[str, Any], metadata: Dict[str, Any] = None) -> Transaction:
        tx = Transaction(transaction_type=transaction_type, sender_address=self.address, data=data, metadata=metadata or {})
        return self.sign_transaction(tx)

    def to_dict(self, include_private_key: bool = False) -> Dict[str, Any]:
        data = {
            "name": self.name,
            "address": self.address,
            "public_key": self.public_key,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }
        if include_private_key:
            data["private_key"] = self.private_key
        return data


class WalletManager:
    """In-memory cache of wallets. Persistence is delegated to a WalletRepository."""

    def __init__(self, repository):
        self._repository = repository
        self.wallets: Dict[str, Wallet] = {}

    def create_wallet(self, name: str, metadata: Dict[str, Any] = None, persist: bool = True) -> Wallet:
        if name in self.wallets or self._repository.exists(name):
            raise ValueError(f"Wallet '{name}' already exists")
        wallet = Wallet(name=name, metadata=metadata or {})
        self.wallets[name] = wallet
        if persist:
            self._repository.save(wallet)
        return wallet

    def get_wallet(self, name: str) -> Optional[Wallet]:
        if name in self.wallets:
            return self.wallets[name]
        wallet = self._repository.load(name)
        if wallet:
            self.wallets[name] = wallet
        return wallet

    def list_wallets(self) -> List[Dict[str, Any]]:
        wallets: List[Dict[str, Any]] = []
        for name in self._repository.list_names():
            wallet = self.get_wallet(name)
            if wallet:
                wallets.append(wallet.to_dict(include_private_key=False))
        return wallets


__all__ = ["Wallet", "WalletManager"]
