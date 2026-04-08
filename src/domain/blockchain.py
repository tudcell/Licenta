"""Blockchain module with validation, persistence, and thread-safe mempool management."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional

from src.domain.block import Block, GenesisBlock
from src.domain.transaction import Transaction, TransactionType
from src.domain.crypto.merkle_tree import MerkleTree

logger = logging.getLogger("blockchain_audit")


@dataclass
class BlockchainConfig:
    difficulty: int = 4
    max_transactions_per_block: int = 100
    data_dir: str = "blockchain_data"
    auto_save: bool = True


class Blockchain:
    """Complete blockchain implementation for secure audit trails."""

    def __init__(self, config: Optional[BlockchainConfig] = None):
        self.config = config or BlockchainConfig()
        self.chain: List[Block] = []
        self.mempool: List[Transaction] = []
        self._lock = threading.RLock()
        if not self._load_from_disk():
            self._create_genesis_block()

    def _create_genesis_block(self) -> None:
        genesis = GenesisBlock(difficulty=self.config.difficulty)
        self.chain = [genesis]
        if self.config.auto_save:
            self._save_to_disk()

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    @property
    def height(self) -> int:
        return len(self.chain)

    def __len__(self) -> int:
        return len(self.chain)

    def __iter__(self) -> Iterator[Block]:
        return iter(self.chain)

    def _all_transaction_ids(self) -> set[str]:
        ids = {tx.transaction_id for tx in self.mempool}
        for block in self.chain:
            ids.update(tx.transaction_id for tx in block.transactions)
        return ids

    def add_transaction(self, transaction: Transaction) -> bool:
        """Validate and add a transaction to the mempool."""
        with self._lock:
            if not transaction.verify_signature():
                logger.warning(
                    "Rejected transaction %s due to invalid signature",
                    transaction.transaction_id
                )
                return False

            if transaction.transaction_id in self._all_transaction_ids():
                logger.info("Rejected duplicate transaction %s", transaction.transaction_id)
                return False

            self.mempool.append(transaction)

            if self.config.auto_save:
                self._save_to_disk()

            logger.info(
                "Transaction %s added to mempool. Pending count=%s",
                transaction.transaction_id,
                len(self.mempool)
            )
            return True

    def mine_pending_transactions(self) -> Optional[Block]:
        with self._lock:
            if not self.mempool:
                return None

            transactions_to_include = self.mempool[: self.config.max_transactions_per_block]

            new_block = Block(
                index=len(self.chain),
                previous_hash=self.last_block.block_hash,
                transactions=transactions_to_include,
                difficulty=self.config.difficulty,
            )

            iterations = new_block.mine()
            logger.info(
                "Block #%s mined in %s iterations with %s transaction(s)",
                new_block.index,
                iterations,
                len(transactions_to_include)
            )

            self.chain.append(new_block)
            self.mempool = self.mempool[self.config.max_transactions_per_block :]

            if self.config.auto_save:
                self._save_to_disk()

            return new_block

    def validate_chain(self) -> tuple[bool, Optional[str]]:
        with self._lock:
            for index, block in enumerate(self.chain):
                if block.block_hash != block.calculate_hash():
                    return False, f"Invalid hash for block #{index}"

                if not block.block_hash.startswith("0" * block.difficulty):
                    return False, f"Invalid Proof of Work for block #{index}"

                if index > 0 and block.previous_hash != self.chain[index - 1].block_hash:
                    return False, f"Invalid link between blocks #{index - 1} and #{index}"

                if not block.verify_integrity():
                    return False, f"Invalid integrity for block #{index}"

            return True, None

    def get_block(self, index: int) -> Optional[Block]:
        if 0 <= index < len(self.chain):
            return self.chain[index]
        return None

    def get_block_by_hash(self, block_hash: str) -> Optional[Block]:
        return next((block for block in self.chain if block.block_hash == block_hash), None)

    def get_transaction(self, transaction_id: str) -> Optional[tuple[Transaction, Block]]:
        for block in self.chain:
            for tx in block.transactions:
                if tx.transaction_id == transaction_id:
                    return tx, block
        return None

    def get_transactions_by_address(self, address: str) -> List[Transaction]:
        matches: List[Transaction] = []
        for block in self.chain:
            for tx in block.transactions:
                if tx.sender_address == address or tx.data.get("recipient") == address:
                    matches.append(tx)
        return matches

    def get_transactions_by_type(self, tx_type: TransactionType) -> List[Transaction]:
        return [tx for block in self.chain for tx in block.transactions if tx.transaction_type == tx_type]

    def get_all_transactions(self) -> List[Transaction]:
        return [tx for block in self.chain for tx in block.transactions]

    def get_mempool_transactions(self) -> List[Transaction]:
        with self._lock:
            return list(self.mempool)

    def verify_transaction_proof(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        result = self.get_transaction(transaction_id)
        if not result:
            return None

        tx, block = result
        proof = block.get_transaction_proof(transaction_id)
        if proof is None:
            return None

        verified = MerkleTree.verify_proof(proof)

        return {
            "transaction_id": transaction_id,
            "block_index": block.index,
            "merkle_root": block.merkle_root,
            "proof": proof.to_dict(),
            "verified": verified,
        }

    def get_statistics(self) -> Dict[str, Any]:
        total_transactions = sum(len(block.transactions) for block in self.chain)
        mempool_count = len(self.mempool)

        return {
            "height": self.height,
            "chain_length": self.height,
            "total_blocks": len(self.chain),
            "total_transactions": total_transactions,
            "pending_transactions": mempool_count,
            "mempool_size": mempool_count,
            "difficulty": self.config.difficulty,
            "current_difficulty": self.config.difficulty,
            "max_transactions_per_block": self.config.max_transactions_per_block,
            "chain_valid": self.validate_chain()[0],
        }

    def _metadata_path(self) -> str:
        return os.path.join(self.config.data_dir, "metadata.json")

    def _chain_path(self) -> str:
        return os.path.join(self.config.data_dir, "chain.json")

    def _mempool_path(self) -> str:
        return os.path.join(self.config.data_dir, "mempool.json")

    def _atomic_json_write(self, path: str, payload: Any) -> None:
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

    def _save_to_disk(self) -> None:
        os.makedirs(self.config.data_dir, exist_ok=True)

        metadata = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "difficulty": self.config.difficulty,
            "max_transactions_per_block": self.config.max_transactions_per_block,
            "height": len(self.chain),
            "mempool_size": len(self.mempool),
        }

        self._atomic_json_write(self._metadata_path(), metadata)
        self._atomic_json_write(self._chain_path(), [block.to_dict() for block in self.chain])
        self._atomic_json_write(self._mempool_path(), [tx.to_dict() for tx in self.mempool])

    def _load_from_disk(self) -> bool:
        if not os.path.isdir(self.config.data_dir):
            return False

        chain_path = self._chain_path()
        if not os.path.exists(chain_path):
            return False

        try:
            with open(chain_path, "r", encoding="utf-8") as chain_file:
                chain_data = json.load(chain_file)

            self.chain = [Block.from_dict(item) for item in chain_data]

            mempool_path = self._mempool_path()
            if os.path.exists(mempool_path):
                try:
                    with open(mempool_path, "r", encoding="utf-8") as mempool_file:
                        mempool_data = json.load(mempool_file)
                    self.mempool = [Transaction.from_dict(item) for item in mempool_data]
                except Exception as exc:
                    logger.warning("Invalid mempool data ignored: %s", exc)
                    self.mempool = []
            else:
                self.mempool = []

            is_valid, error = self.validate_chain()
            if not is_valid:
                logger.error("Loaded blockchain is invalid: %s", error)
                self.chain = []
                self.mempool = []
                return False

            logger.info(
                "Blockchain loaded with %s block(s) and %s pending transaction(s)",
                len(self.chain),
                len(self.mempool)
            )
            return True

        except Exception as exc:
            logger.exception("Error loading blockchain from disk: %s", exc)
            self.chain = []
            self.mempool = []
            return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config": {
                "difficulty": self.config.difficulty,
                "max_transactions_per_block": self.config.max_transactions_per_block,
                "data_dir": self.config.data_dir,
                "auto_save": self.config.auto_save,
            },
            "chain": [block.to_dict() for block in self.chain],
            "mempool": [tx.to_dict() for tx in self.mempool],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)