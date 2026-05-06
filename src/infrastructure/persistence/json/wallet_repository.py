"""JSON-on-disk adapter for wallets, with optional Fernet encryption of private keys."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Any, Dict, List, Optional

from cryptography.fernet import Fernet, InvalidToken

from src.domain.entities.wallet import Wallet
from src.domain.policies.digital_signature import DigitalSignature, KeyPair


class JsonWalletRepository:
    def __init__(self, wallets_dir: str, encryption_key: Optional[str] = None):
        self.wallets_dir = wallets_dir
        os.makedirs(wallets_dir, exist_ok=True)
        self._cipher = self._build_cipher(encryption_key)

    @staticmethod
    def _build_cipher(secret: Optional[str]) -> Optional[Fernet]:
        if not secret:
            return None
        derived = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
        return Fernet(derived)

    def _path(self, name: str) -> str:
        return os.path.join(self.wallets_dir, f"{name}.json")

    def exists(self, name: str) -> bool:
        return os.path.exists(self._path(name))

    def list_names(self) -> List[str]:
        return sorted(
            filename[:-5]
            for filename in os.listdir(self.wallets_dir)
            if filename.endswith(".json")
        )

    def save(self, wallet: Wallet) -> None:
        os.makedirs(self.wallets_dir, exist_ok=True)
        payload: Dict[str, Any] = wallet.to_dict(include_private_key=False)
        payload.update(self._encrypt_private_key(wallet.private_key))
        with open(self._path(wallet.name), "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def load(self, name: str) -> Optional[Wallet]:
        path = self._path(name)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        private_key_hex = self._decrypt_private_key(data)
        if not private_key_hex:
            raise ValueError(f"Wallet '{data.get('name', name)}' does not contain a loadable private key")
        private_key = DigitalSignature.private_key_from_hex(private_key_hex)
        wallet = Wallet(
            name=data["name"],
            _key_pair=KeyPair(private_key=private_key, public_key=private_key.public_key()),
        )
        wallet.created_at = data["created_at"]
        wallet.metadata = data.get("metadata", {})
        return wallet

    # ------------------------------------------------------------------
    def _encrypt_private_key(self, private_key: str) -> Dict[str, str]:
        if not self._cipher:
            return {"private_key": private_key, "key_storage": "plaintext"}
        encrypted = self._cipher.encrypt(private_key.encode("utf-8")).decode("utf-8")
        return {"encrypted_private_key": encrypted, "key_storage": "fernet"}

    def _decrypt_private_key(self, data: Dict[str, Any]) -> Optional[str]:
        if "encrypted_private_key" in data:
            if not self._cipher:
                raise ValueError("Encrypted wallet cannot be loaded without WALLET_ENCRYPTION_KEY")
            try:
                return self._cipher.decrypt(data["encrypted_private_key"].encode("utf-8")).decode("utf-8")
            except InvalidToken as exc:
                raise ValueError("Invalid WALLET_ENCRYPTION_KEY for encrypted wallet") from exc
        return data.get("private_key")
