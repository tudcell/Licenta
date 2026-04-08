"""
Block Module - The basic block in the blockchain.
Contains a set of transactions cryptographically aggregated through Merkle Tree.
"""

import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from src.crypto.hashing import HashUtils
from src.crypto.merkle_tree import MerkleTree, MerkleProof
from src.blockchain.transaction import Transaction


@dataclass
class Block:
    """
    Represents a block in the blockchain.

    Block structure
    - Header: contains metadata and cryptographic links
    - Body: contains the list of transactions

    Integrity is ensured through:
    - Previous block hash (chaining)
    - Merkle Root (transaction aggregation)
    - Proof of Work (nonce)
    """

    # Header
    index: int
    previous_hash: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    nonce: int = 0
    difficulty: int = 4  # Number of zeros required at the beginning of the hash

    # Body
    transactions: List[Transaction] = field(default_factory=list)

    # Calculated fields
    merkle_root: str = field(default="", init=False)
    block_hash: str = field(default="", init=False)

    # Merkle Tree for verifications
    _merkle_tree: Optional[MerkleTree] = field(default=None, repr=False, init=False)

    def __post_init__(self):
        """Calculates Merkle Root and block hash after initialization."""
        self._build_merkle_tree()
        if not self.block_hash:
            self.block_hash = self.calculate_hash()

    def _build_merkle_tree(self):
        """Builds Merkle Tree from transactions."""
        tx_hashes = [tx.calculate_hash() for tx in self.transactions]
        self._merkle_tree = MerkleTree(tx_hashes)
        self.merkle_root = self._merkle_tree.get_root_hash()

    def get_header(self) -> Dict[str, Any]:
        """Returns the block header for hashing."""
        return {
            "index": self.index,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
            "merkle_root": self.merkle_root,
            "nonce": self.nonce,
            "difficulty": self.difficulty
        }

    def calculate_hash(self) -> str:
        """
        Calculates the block hash based on header.

        Returns:
            SHA-256 hash of the header
        """
        return HashUtils.hash_object(self.get_header())

    def mine(self, difficulty: int = None) -> int:
        """
        Mines the block using Proof of Work.
        Finds a nonce such that the hash starts with 'difficulty' zeros.

        Args:
            difficulty: Number of zeros (if None, uses self.difficulty)

        Returns:
            Number of iterations required
        """
        if difficulty is not None:
            self.difficulty = difficulty

        target = '0' * self.difficulty
        iterations = 0

        while True:
            self.block_hash = self.calculate_hash()
            iterations += 1

            if self.block_hash.startswith(target):
                return iterations

            self.nonce += 1

    def add_transaction(self, transaction: Transaction) -> bool:
        """
        Adds a transaction to the block.

        Args:
            transaction: The transaction to add

        Returns:
            True if the transaction was added successfully
        """
        # Verify signature if it exists
        if not transaction.verify_signature():
            return False

        self.transactions.append(transaction)
        self._build_merkle_tree()
        self.block_hash = self.calculate_hash()
        return True

    def get_transaction_proof(self, transaction_id: str) -> Optional[MerkleProof]:
        """
        Generates the inclusion proof for a transaction.

        Args:
            transaction_id: The transaction ID

        Returns:
            MerkleProof or None if the transaction doesn't exist
        """
        for tx in self.transactions:
            if tx.transaction_id == transaction_id:
                tx_hash = tx.calculate_hash()
                return self._merkle_tree.get_proof(tx_hash)
        return None

    def verify_transaction_inclusion(self, transaction: Transaction) -> bool:
        """
        Verifies if a transaction is part of the block using Merkle Proof.

        Args:
            transaction: The transaction to verify

        Returns:
            True if the transaction is included in the block
        """
        proof = self.get_transaction_proof(transaction.transaction_id)
        if proof is None:
            return False
        return MerkleTree.verify_proof(proof)

    def verify_integrity(self) -> bool:
        """
        Verifies the complete integrity of the block.

        Returns:
            True if the block is valid
        """
        # Verify block hash
        if self.block_hash != self.calculate_hash():
            return False

        # Verify Proof of Work
        if not self.block_hash.startswith('0' * self.difficulty):
            return False

        # Verify Merkle Root
        tx_hashes = [tx.calculate_hash() for tx in self.transactions]
        tree = MerkleTree(tx_hashes)
        if self.merkle_root != tree.get_root_hash():
            return False

        # Verify transaction signatures
        for tx in self.transactions:
            if not tx.verify_signature():
                return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the block to dictionary."""
        return {
            "index": self.index,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "difficulty": self.difficulty,
            "merkle_root": self.merkle_root,
            "block_hash": self.block_hash,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "transaction_count": len(self.transactions)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Block':
        """Deserializes the block from dictionary."""
        transactions = [Transaction.from_dict(tx) for tx in data.get("transactions", [])]

        block = cls(
            index=data["index"],
            previous_hash=data["previous_hash"],
            timestamp=data["timestamp"],
            nonce=data["nonce"],
            difficulty=data["difficulty"],
            transactions=transactions
        )
        block.merkle_root = data["merkle_root"]
        block.block_hash = data["block_hash"]

        return block

    def to_json(self) -> str:
        """Serializes to JSON."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_string: str) -> 'Block':
        """Deserializes from JSON."""
        return cls.from_dict(json.loads(json_string))

    def get_summary(self) -> str:
        """Returns a summary of the block."""
        return (
            f"Block #{self.index}\n"
            f"  Hash: {self.block_hash[:32]}...\n"
            f"  Prev: {self.previous_hash[:32]}...\n"
            f"  Merkle Root: {self.merkle_root[:32]}...\n"
            f"  Transactions: {len(self.transactions)}\n"
            f"  Nonce: {self.nonce}\n"
            f"  Difficulty: {self.difficulty}\n"
            f"  Timestamp: {self.timestamp}"
        )

    def __str__(self) -> str:
        return f"Block[{self.index}] hash={self.block_hash[:16]}... txs={len(self.transactions)}"

    def __repr__(self) -> str:
        return self.__str__()


class GenesisBlock(Block):
    """
    Genesis Block - the first block in the blockchain.
    Has no previous block (previous_hash = 0).
    """

    def __init__(self, difficulty: int = 4):
        super().__init__(
            index=0,
            previous_hash='0' * 64,
            difficulty=difficulty,
            transactions=[]
        )
        self.mine()

