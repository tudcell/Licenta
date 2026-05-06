"""JSON-on-disk adapter for the Blockchain aggregate."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Optional

from src.domain.entities.block import Block
from src.domain.entities.blockchain import Blockchain, BlockchainConfig
from src.domain.entities.transaction import Transaction

logger = logging.getLogger("blockchain_audit")


class JsonBlockchainRepository:
    """Persists chain + mempool as separate JSON files under the configured data dir."""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir

    # ------------------------------------------------------------------
    # paths
    # ------------------------------------------------------------------
    def _metadata_path(self) -> str:
        return os.path.join(self.data_dir, "metadata.json")

    def _chain_path(self) -> str:
        return os.path.join(self.data_dir, "chain.json")

    def _mempool_path(self) -> str:
        return os.path.join(self.data_dir, "mempool.json")

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def load(self, config: BlockchainConfig) -> Optional[Blockchain]:
        if not os.path.isdir(self.data_dir):
            return None
        chain_path = self._chain_path()
        if not os.path.exists(chain_path):
            return None
        try:
            with open(chain_path, "r", encoding="utf-8") as chain_file:
                chain_data = json.load(chain_file)
            chain = [Block.from_dict(item) for item in chain_data]

            mempool: list[Transaction] = []
            mempool_path = self._mempool_path()
            if os.path.exists(mempool_path):
                with open(mempool_path, "r", encoding="utf-8") as mempool_file:
                    mempool_data = json.load(mempool_file)
                mempool = [Transaction.from_dict(item) for item in mempool_data]
        except Exception as exc:
            logger.error("Could not load blockchain from %s: %s", self.data_dir, exc)
            raise

        blockchain = Blockchain(config)
        blockchain.chain = chain
        blockchain.mempool = mempool

        is_valid, error = blockchain.validate_chain()
        if not is_valid:
            raise ValueError(f"Persisted chain failed validation: {error}")
        return blockchain

    def save(self, blockchain: Blockchain) -> None:
        os.makedirs(self.data_dir, exist_ok=True)
        metadata = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "difficulty": blockchain.config.difficulty,
            "max_transactions_per_block": blockchain.config.max_transactions_per_block,
            "height": len(blockchain.chain),
            "mempool_size": len(blockchain.mempool),
        }
        self._atomic_json_write(self._metadata_path(), metadata)
        self._atomic_json_write(self._chain_path(), [block.to_dict() for block in blockchain.chain])
        self._atomic_json_write(self._mempool_path(), [tx.to_dict() for tx in blockchain.mempool])

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    @staticmethod
    def _atomic_json_write(path: str, payload: Any) -> None:
        directory = os.path.dirname(path) or "."
        fd, temp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".json", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
                json.dump(payload, temp_file, ensure_ascii=False, indent=2)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.replace(temp_path, path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
