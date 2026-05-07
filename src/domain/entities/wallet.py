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

    def sign_transaction(self, transaction: Transaction) -> Transaction:
        """Stamp public_key + signature on the transaction without exposing
        the private key."""
        transaction.public_key = self.public_key
        transaction.signature = self._key_pair.sign(transaction.get_signable_data())
        return transaction

    def create_and_sign_transaction(self, transaction_type, data: Dict[str, Any],
                                    metadata: Dict[str, Any] = None) -> Transaction:
        tx = Transaction(transaction_type=transaction_type, sender_address=self.address, data=data,
                         metadata=metadata or {})
        return self.sign_transaction(tx)

    def to_dict(self) -> Dict[str, Any]:
        """Public, safe representation. Never includes the private key."""
        return {
            "name": self.name,
            "address": self.address,
            "public_key": self.public_key,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    def export_private_key_hex(self) -> str:
        """Hex-encoded private key for persistence layer use only.

        Callers MUST encrypt the return value before writing it anywhere.
        Anything else (logging, HTTP responses, in-memory caches) is a leak.
        """
        return self._key_pair.export_private_key_hex()


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
                wallets.append(wallet.to_dict())
        return wallets


__all__ = ["Wallet", "WalletManager"]
