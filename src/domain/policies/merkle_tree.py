"""
Merkle Tree implementation for cryptographic aggregation of transactions.
Allows efficient verification of transaction inclusion in a block.
"""

from typing import List, Optional, Tuple
from dataclasses import dataclass
from .hashing import HashUtils


@dataclass
class MerkleNode:
    """
    Node in the Merkle tree.
    """
    hash: str
    left: Optional['MerkleNode'] = None
    right: Optional['MerkleNode'] = None
    data: Optional[str] = None  # Only for leaves

    def is_leaf(self) -> bool:
        """Checks if the node is a leaf."""
        return self.left is None and self.right is None


@dataclass
class MerkleProof:
    """
    Merkle inclusion proof (Merkle Proof / Authentication Path).
    Allows verification that a transaction is part of the tree without knowing all transactions.
    """
    leaf_hash: str
    proof_hashes: List[Tuple[str, str]]  # List of (hash, position: 'left' or 'right')
    root_hash: str

    def to_dict(self) -> dict:
        """Serializes the proof for storage/transmission."""
        return {
            "leaf_hash": self.leaf_hash,
            "proof_hashes": self.proof_hashes,
            "root_hash": self.root_hash
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'MerkleProof':
        """Deserializes the proof."""
        return cls(
            leaf_hash=data["leaf_hash"],
            proof_hashes=[tuple(x) for x in data["proof_hashes"]],
            root_hash=data["root_hash"]
        )


class MerkleTree:
    """
    Merkle Tree implementation (binary hash tree).

    Properties:
    - Each leaf is the hash of a transaction
    - Each internal node is the hash of the concatenation of its children
    - The root (Merkle Root) represents a cryptographic summary of all transactions
    - Modifying any transaction changes the Merkle Root
    - Allows inclusion proofs in O(log n)
    """

    def __init__(self, transactions: List[str] = None):
        """
        Builds the Merkle Tree from the transaction list.

        Args:
            transactions: List of transaction hashes (or raw data)
        """
        self.transactions = transactions or []
        self.leaves: List[MerkleNode] = []
        self.root: Optional[MerkleNode] = None

        if self.transactions:
            self._build_tree()

    def _build_tree(self):
        """Builds the tree from bottom to top."""
        if not self.transactions:
            self.root = MerkleNode(hash=HashUtils.hash_string(""))
            return

        # Create leaf nodes
        self.leaves = []
        for tx in self.transactions:
            # If tx is not already a hash, hash it
            if len(tx) != 64:  # Not a SHA-256 hash
                tx_hash = HashUtils.hash_string(tx)
            else:
                tx_hash = tx
            self.leaves.append(MerkleNode(hash=tx_hash, data=tx))

        # Build levels
        current_level = self.leaves.copy()

        while len(current_level) > 1:
            next_level = []

            # If odd number, duplicate the last node
            if len(current_level) % 2 == 1:
                current_level.append(current_level[-1])

            # Combine nodes in pairs
            for i in range(0, len(current_level), 2):
                left_node = current_level[i]
                right_node = current_level[i + 1]

                # Parent hash = hash(left + right)
                parent_hash = HashUtils.hash_pair(left_node.hash, right_node.hash)
                parent = MerkleNode(
                    hash=parent_hash,
                    left=left_node,
                    right=right_node
                )
                next_level.append(parent)

            current_level = next_level

        self.root = current_level[0] if current_level else None

    def get_root_hash(self) -> str:
        """
        Returns the Merkle Root - the root hash representing all transactions.

        Returns:
            Root hash or empty hash if tree is empty
        """
        if self.root:
            return self.root.hash
        return HashUtils.hash_string("")

    def get_proof(self, transaction: str) -> Optional[MerkleProof]:
        """
        Generates the inclusion proof for a transaction.

        Args:
            transaction: The transaction or its hash

        Returns:
            MerkleProof or None if transaction doesn't exist
        """
        # Find transaction hash
        if len(transaction) != 64:
            tx_hash = HashUtils.hash_string(transaction)
        else:
            tx_hash = transaction

        # Find leaf index
        leaf_index = None
        for i, leaf in enumerate(self.leaves):
            if leaf.hash == tx_hash:
                leaf_index = i
                break

        if leaf_index is None:
            return None

        # Build authentication path
        proof_hashes = []
        current_index = leaf_index
        current_level = self.leaves.copy()

        while len(current_level) > 1:
            # Duplicate if odd number
            if len(current_level) % 2 == 1:
                current_level.append(current_level[-1])

            # Find sibling
            if current_index % 2 == 0:
                # We're on left, need sibling on right
                sibling_index = current_index + 1
                position = 'right'
            else:
                # We're on right, need sibling on left
                sibling_index = current_index - 1
                position = 'left'

            sibling_hash = current_level[sibling_index].hash
            proof_hashes.append((sibling_hash, position))

            # Build next level
            next_level = []
            for i in range(0, len(current_level), 2):
                combined_hash = HashUtils.hash_pair(
                    current_level[i].hash,
                    current_level[i + 1].hash
                )
                next_level.append(MerkleNode(hash=combined_hash))

            current_level = next_level
            current_index = current_index // 2

        return MerkleProof(
            leaf_hash=tx_hash,
            proof_hashes=proof_hashes,
            root_hash=self.get_root_hash()
        )

    @staticmethod
    def verify_proof(proof: MerkleProof) -> bool:
        """
        Verifies a Merkle proof.

        Args:
            proof: The Merkle proof to verify

        Returns:
            True if proof is valid
        """
        current_hash = proof.leaf_hash

        for sibling_hash, position in proof.proof_hashes:
            if position == 'left':
                # Sibling is on left, we are on right
                current_hash = HashUtils.hash_pair(sibling_hash, current_hash)
            else:
                # Sibling is on right, we are on left
                current_hash = HashUtils.hash_pair(current_hash, sibling_hash)

        return current_hash == proof.root_hash

    def __len__(self) -> int:
        return len(self.transactions)

    def __str__(self) -> str:
        return f"MerkleTree(transactions={len(self.transactions)}, root={self.get_root_hash()[:16]}...)"


