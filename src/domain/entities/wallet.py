"""Wallet module - canonical domain implementation."""

import base64
import json
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime

from cryptography.fernet import Fernet, InvalidToken

from src.domain.entities.transaction import Transaction, TransactionFactory
from src.domain.policies.digital_signature import DigitalSignature, KeyPair


def _get_wallet_cipher() -> Optional[Fernet]:
	secret = os.environ.get("WALLET_ENCRYPTION_KEY")
	if not secret:
		return None
	import hashlib
	derived = base64.urlsafe_b64encode(hashlib.sha256(secret.encode('utf-8')).digest())
	return Fernet(derived)


def _encrypt_private_key(private_key: str) -> Dict[str, str]:
	cipher = _get_wallet_cipher()
	if not cipher:
		return {"private_key": private_key, "key_storage": "plaintext"}
	encrypted = cipher.encrypt(private_key.encode('utf-8')).decode('utf-8')
	return {"encrypted_private_key": encrypted, "key_storage": "fernet"}


def _decrypt_private_key(data: Dict[str, Any]) -> Optional[str]:
	if "encrypted_private_key" in data:
		cipher = _get_wallet_cipher()
		if not cipher:
			raise ValueError("Encrypted wallet cannot be loaded without WALLET_ENCRYPTION_KEY")
		try:
			return cipher.decrypt(data["encrypted_private_key"].encode('utf-8')).decode('utf-8')
		except InvalidToken as exc:
			raise ValueError("Invalid WALLET_ENCRYPTION_KEY for encrypted wallet") from exc
	return data.get("private_key")


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

	def create_login_event(self, ip_address: str, user_agent: str = None, success: bool = True) -> Transaction:
		tx = TransactionFactory.create_login_event(
			user_id=self.name,
			sender_address=self.address,
			ip_address=ip_address,
			user_agent=user_agent,
			success=success,
		)
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
			data.update(_encrypt_private_key(self.private_key))
		return data

	def save(self, filepath: str, include_private_key: bool = True):
		os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
		with open(filepath, 'w') as f:
			json.dump(self.to_dict(include_private_key=include_private_key), f, indent=2)

	@classmethod
	def load(cls, filepath: str) -> 'Wallet':
		with open(filepath, 'r') as f:
			data = json.load(f)
		private_key_hex = _decrypt_private_key(data)
		if not private_key_hex:
			raise ValueError(f"Wallet '{data.get('name', 'unknown')}' does not contain a loadable private key")
		private_key = DigitalSignature.private_key_from_hex(private_key_hex)
		wallet = cls(name=data["name"], _key_pair=KeyPair(private_key=private_key, public_key=private_key.public_key()))
		wallet.created_at = data["created_at"]
		wallet.metadata = data.get("metadata", {})
		return wallet

class WalletManager:
	def __init__(self, wallets_dir: str = "wallets"):
		self.wallets_dir = wallets_dir
		self.wallets: Dict[str, Wallet] = {}
		os.makedirs(wallets_dir, exist_ok=True)

	def create_wallet(self, name: str, metadata: Dict[str, Any] = None, persist_private_key: bool = True) -> Wallet:
		if name in self.wallets:
			raise ValueError(f"Wallet '{name}' already exists")
		wallet = Wallet(name=name, metadata=metadata or {})
		self.wallets[name] = wallet
		wallet.save(os.path.join(self.wallets_dir, f"{name}.json"), include_private_key=persist_private_key)
		return wallet

	def get_wallet(self, name: str) -> Optional[Wallet]:
		if name in self.wallets:
			return self.wallets[name]
		filepath = os.path.join(self.wallets_dir, f"{name}.json")
		if os.path.exists(filepath):
			wallet = Wallet.load(filepath)
			self.wallets[name] = wallet
			return wallet
		return None

	def list_wallets(self) -> List[Dict[str, Any]]:
		wallets = []
		for filename in os.listdir(self.wallets_dir):
			if filename.endswith('.json'):
				wallet = self.get_wallet(filename[:-5])
				if wallet:
					wallets.append(wallet.to_dict(include_private_key=False))
		return wallets


__all__ = ["Wallet", "WalletManager"]

