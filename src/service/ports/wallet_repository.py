"""Port for wallet persistence."""

from __future__ import annotations

from typing import List, Optional, Protocol

from src.domain.entities.wallet import Wallet


class WalletRepository(Protocol):
    def save(self, wallet: Wallet) -> None: ...
    def load(self, name: str) -> Optional[Wallet]: ...
    def exists(self, name: str) -> bool: ...
    def list_names(self) -> List[str]: ...
