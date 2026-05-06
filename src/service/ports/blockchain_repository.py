"""Port for persisting and loading the Blockchain aggregate."""

from __future__ import annotations

from typing import Optional, Protocol

from src.domain.entities.blockchain import Blockchain, BlockchainConfig


class BlockchainRepository(Protocol):
    def load(self, config: BlockchainConfig) -> Optional[Blockchain]: ...
    def save(self, blockchain: Blockchain) -> None: ...
