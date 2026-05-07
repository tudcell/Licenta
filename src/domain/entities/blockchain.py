"""Blockchain aggregate. Pure domain object; persistence lives in adapters."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional

from src.domain.entities.block import Block, GenesisBlock
from src.domain.entities.transaction import Transaction
from src.domain.policies import MerkleTree


@dataclass
class BlockchainConfig:
    """Pure-domain configuration. Persistence concerns live in adapters."""
    difficulty: int = 4
    max_transactions_per_block: int = 100


class Blockchain:
    def __init__(self, config: Optional[BlockchainConfig] = None):
        self.config = config or BlockchainConfig()
        self.chain: List[Block] = []
        self.mempool: List[Transaction] = []
        self._lock = threading.RLock()
        if not self.chain:
            self._create_genesis_block()

    def _create_genesis_block(self) -> None:
        self.chain = [GenesisBlock(difficulty=self.config.difficulty)]

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
        with self._lock:
            if not transaction.verify_signature() or transaction.transaction_id in self._all_transaction_ids():
                return False
            self.mempool.append(transaction)
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
            new_block.mine()
            self.chain.append(new_block)
            self.mempool = self.mempool[self.config.max_transactions_per_block:]
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
        return self.chain[index] if 0 <= index < len(self.chain) else None

    def get_transaction(self, transaction_id: str) -> Optional[tuple[Transaction, Block]]:
        for block in self.chain:
            for tx in block.transactions:
                if tx.transaction_id == transaction_id:
                    return tx, block
        return None

    # Deleted: get_block_by_hash, get_transactions_by_address, get_transactions_by_type
    # were never called outside their own module.

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
        return {
            "transaction_id": transaction_id,
            "block_index": block.index,
            "merkle_root": block.merkle_root,
            "proof": proof.to_dict(),
            "verified": MerkleTree.verify_proof(proof),
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config": {
                "difficulty": self.config.difficulty,
                "max_transactions_per_block": self.config.max_transactions_per_block,
            },
            "chain": [block.to_dict() for block in self.chain],
            "mempool": [tx.to_dict() for tx in self.mempool],
        }


__all__ = ["Blockchain", "BlockchainConfig"]
