"""JSON-on-disk adapter for wallets, with mandatory Fernet encryption.

Security model:
    - Active key encrypts every wallet on save. There is no plaintext path
      for new writes.
    - Optional `extra_keys` accept previous keys so wallets persisted under
      a rotated key still load. On read, when an old key decrypts a wallet,
      the manager re-saves it under the active key (key migration in place).
    - Each saved wallet carries a `key_version` integer so future operators
      can audit which keys are still active.
    - Legacy plaintext wallets (`key_storage: "plaintext"`) load with a loud
      warning and are immediately re-saved under the active key.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from typing import Any, Dict, Iterable, List, Optional

from cryptography.fernet import Fernet, InvalidToken

from src.domain.entities.wallet import Wallet
from src.domain.policies.digital_signature import DigitalSignature, KeyPair

logger = logging.getLogger("blockchain_audit")

CURRENT_KEY_VERSION = 1


def _build_cipher(secret: str) -> Fernet:
    derived = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(derived)


class JsonWalletRepository:
    def __init__(
            self,
            wallets_dir: str,
            encryption_key: str,
            legacy_keys: Optional[Iterable[str]] = None,
    ):
        if not encryption_key:
            raise ValueError(
                "JsonWalletRepository requires a non-empty encryption_key. "
                "Saving wallets in plaintext is not supported."
            )
        self.wallets_dir = wallets_dir
        os.makedirs(wallets_dir, exist_ok=True)
        self._active_cipher = _build_cipher(encryption_key)
        self._fallback_ciphers = [_build_cipher(item) for item in (legacy_keys or []) if item]

    # ------------------------------------------------------------------
    # paths
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def save(self, wallet: Wallet) -> None:
        os.makedirs(self.wallets_dir, exist_ok=True)
        encrypted = self._active_cipher.encrypt(wallet.export_private_key_hex().encode("utf-8")).decode("utf-8")
        payload: Dict[str, Any] = wallet.to_dict()
        payload["encrypted_private_key"] = encrypted
        payload["key_storage"] = "fernet"
        payload["key_version"] = CURRENT_KEY_VERSION
        with open(self._path(wallet.name), "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def load(self, name: str) -> Optional[Wallet]:
        path = self._path(name)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        private_key_hex, needs_resave = self._extract_private_key(data, name)

        private_key = DigitalSignature.private_key_from_hex(private_key_hex)
        wallet = Wallet(
            name=data["name"],
            _key_pair=KeyPair(private_key=private_key, public_key=private_key.public_key()),
        )
        wallet.created_at = data["created_at"]
        wallet.metadata = data.get("metadata", {})

        if needs_resave:
            logger.warning(
                "Wallet '%s' was loaded under a non-active key; re-saving under the active key.",
                name,
            )
            self.save(wallet)

        return wallet

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _extract_private_key(self, data: Dict[str, Any], name: str) -> tuple[str, bool]:
        """Return (hex_key, needs_resave). Tries active cipher, then legacy
        ciphers, then a final loud-warning plaintext fallback for pre-encryption
        wallets. Anything else is a hard error."""
        encrypted = data.get("encrypted_private_key")
        if encrypted:
            token = encrypted.encode("utf-8")
            for cipher in (self._active_cipher, *self._fallback_ciphers):
                try:
                    return cipher.decrypt(token).decode("utf-8"), cipher is not self._active_cipher
                except InvalidToken:
                    continue
            raise ValueError(
                f"Cannot decrypt wallet '{name}' with any configured key. "
                "If you rotated WALLET_ENCRYPTION_KEY, set WALLET_ENCRYPTION_LEGACY_KEYS "
                "to the previous key(s) so existing wallets can be migrated."
            )

        plaintext = data.get("private_key")
        if plaintext:
            logger.warning(
                "Wallet '%s' was stored in plaintext (legacy format); "
                "encrypting under the active key on next save.",
                name,
            )
            return plaintext, True

        raise ValueError(f"Wallet '{name}' contains no loadable private key")
