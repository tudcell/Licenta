"""
Blockchain Module - The complete chain of blocks with validation and persistence.
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional, Iterator
from dataclasses import dataclass, field
import threading

from src.blockchain.block import Block, GenesisBlock
from src.blockchain.transaction import Transaction, TransactionType
from src.crypto.merkle_tree import MerkleTree, MerkleProof


@dataclass
class BlockchainConfig:
    """Blockchain configuration."""
    difficulty: int = 4
    max_transactions_per_block: int = 100
    data_dir: str = "blockchain_data"
    auto_save: bool = True


class Blockchain:
    """
    Complete blockchain implementation for secure audit.

    Features:
    - Immutable chain of blocks
    - Complete integrity validation
    - Disk persistence
    - Mempool for pending transactions
    - Thread-safe
    """

    def __init__(self, config: BlockchainConfig = None):
        """
        Initializes the blockchain.

        Args:
            config: Blockchain configuration
        """
        self.config = config or BlockchainConfig()
        self.chain: List[Block] = []
        self.mempool: List[Transaction] = []  # Pending transactions
        self._lock = threading.RLock()

        # Load or create Genesis Block
        if not self._load_from_disk():
            self._create_genesis_block()

    def _create_genesis_block(self):
        """Creates the Genesis block."""
        genesis = GenesisBlock(difficulty=self.config.difficulty)
        self.chain.append(genesis)
        if self.config.auto_save:
            self._save_to_disk()

    @property
    def last_block(self) -> Block:
        """Returns the last block in the chain."""
        return self.chain[-1]

    @property
    def height(self) -> int:
        """Returns the blockchain height (number of blocks)."""
        return len(self.chain)

    def add_transaction(self, transaction: Transaction) -> bool:
        """
        Adds a transaction to the mempool.

        Args:
            transaction: The transaction to add

        Returns:
            True if the transaction was added
        """
        with self._lock:
            # Verify signature
            if not transaction.verify_signature():
                print(f"Invalid signature for transaction {transaction.transaction_id}")
                return False

            # Check if transaction already exists
            if self._transaction_exists(transaction.transaction_id):
                print(f"Transaction {transaction.transaction_id} already exists")
                return False

            self.mempool.append(transaction)
            return True

    def _transaction_exists(self, transaction_id: str) -> bool:
        """Checks if a transaction exists in blockchain or mempool."""
        # Check in mempool
        for tx in self.mempool:
            if tx.transaction_id == transaction_id:
                return True

        # Check in blockchain
        for block in self.chain:
            for tx in block.transactions:
                if tx.transaction_id == transaction_id:
                    return True

        return False

    def mine_pending_transactions(self) -> Optional[Block]:
        """
        Creates and mines a new block with transactions from mempool.

        Returns:
            The mined block or None if there are no transactions
        """
        with self._lock:
            if not self.mempool:
                return None

            # Select transactions for the block
            transactions_to_include = self.mempool[:self.config.max_transactions_per_block]

            # Create the new block
            new_block = Block(
                index=len(self.chain),
                previous_hash=self.last_block.block_hash,
                transactions=transactions_to_include,
                difficulty=self.config.difficulty
            )

            # Mine the block
            iterations = new_block.mine()
            print(f"Block #{new_block.index} mined in {iterations} iterations")

            # Add block to chain
            self.chain.append(new_block)

            # Remove transactions from mempool
            self.mempool = self.mempool[self.config.max_transactions_per_block:]

            if self.config.auto_save:
                self._save_to_disk()

            return new_block

    def validate_chain(self) -> tuple[bool, Optional[str]]:
        """
        Validates the entire blockchain.

        Returns:
            (valid, error_message) - Tuple with validation result
        """
        with self._lock:
            for i, block in enumerate(self.chain):
                # Verify block hash
                if block.block_hash != block.calculate_hash():
                    return False, f"Invalid hash for block #{i}"

                # Verify Proof of Work
                if not block.block_hash.startswith('0' * block.difficulty):
                    return False, f"Invalid Proof of Work for block #{i}"

                # Verify link to previous block
                if i > 0:
                    if block.previous_hash != self.chain[i - 1].block_hash:
                        return False, f"Invalid link between blocks #{i-1} and #{i}"

                # Verify block integrity (including Merkle Root)
                if not block.verify_integrity():
                    return False, f"Invalid integrity for block #{i}"

            return True, None

    def get_block(self, index: int) -> Optional[Block]:
        """Returns a block by index."""
        if 0 <= index < len(self.chain):
            return self.chain[index]
        return None

    def get_block_by_hash(self, block_hash: str) -> Optional[Block]:
        """Returns a block by hash."""
        for block in self.chain:
            if block.block_hash == block_hash:
                return block
        return None

    def get_transaction(self, transaction_id: str) -> Optional[tuple[Transaction, Block]]:
        """
        Finds a transaction in the blockchain.

        Returns:
            Tuple (transaction, block) or None
        """
        for block in self.chain:
            for tx in block.transactions:
                if tx.transaction_id == transaction_id:
                    return tx, block
        return None

    def get_transactions_by_address(self, address: str) -> List[Transaction]:
        """Returns all transactions for an address."""
        transactions = []
        for block in self.chain:
            for tx in block.transactions:
                if tx.sender_address == address:
                    transactions.append(tx)
                elif tx.data.get('recipient') == address:
                    transactions.append(tx)
        return transactions

    def get_transactions_by_type(self, tx_type: TransactionType) -> List[Transaction]:
        """Returns all transactions of a certain type."""
        transactions = []
        for block in self.chain:
            for tx in block.transactions:
                if tx.transaction_type == tx_type:
                    transactions.append(tx)
        return transactions

    def get_all_transactions(self) -> List[Transaction]:
        """Returns all transactions from the blockchain."""
        transactions = []
        for block in self.chain:
            transactions.extend(block.transactions)
        return transactions

    def get_transaction_proof(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """
        Generates complete proof for a transaction.
        Includes block and Merkle Proof.
        """
        result = self.get_transaction(transaction_id)
        if not result:
            return None

        tx, block = result
        merkle_proof = block.get_transaction_proof(transaction_id)

        return {
            "transaction": tx.to_dict(),
            "block_index": block.index,
            "block_hash": block.block_hash,
            "merkle_proof": merkle_proof.to_dict() if merkle_proof else None,
            "timestamp": block.timestamp
        }

    def verify_transaction_proof(self, proof_data: Dict[str, Any]) -> bool:
        """Verifies a transaction proof."""
        try:
            # Verify that the block exists and is valid
            block = self.get_block(proof_data["block_index"])
            if not block or block.block_hash != proof_data["block_hash"]:
                return False

            # Verify Merkle Proof
            if proof_data["merkle_proof"]:
                merkle_proof = MerkleProof.from_dict(proof_data["merkle_proof"])
                if not MerkleTree.verify_proof(merkle_proof):
                    return False

            return True
        except Exception as e:
            print(f"Error verifying proof: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """Returns blockchain statistics."""
        total_transactions = sum(len(block.transactions) for block in self.chain)

        # Count transaction types
        type_counts = {}
        for block in self.chain:
            for tx in block.transactions:
                tx_type = tx.transaction_type.value
                type_counts[tx_type] = type_counts.get(tx_type, 0) + 1

        return {
            "height": len(self.chain),
            "total_transactions": total_transactions,
            "mempool_size": len(self.mempool),
            "difficulty": self.config.difficulty,
            "transaction_types": type_counts,
            "last_block_time": self.last_block.timestamp if self.chain else None,
            "genesis_time": self.chain[0].timestamp if self.chain else None
        }

    def _save_to_disk(self):
        """Saves the blockchain to disk."""
        os.makedirs(self.config.data_dir, exist_ok=True)

        # Save each block
        for block in self.chain:
            filepath = os.path.join(self.config.data_dir, f"block_{block.index}.json")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(block.to_json())

        # Save metadata
        metadata = {
            "height": len(self.chain),
            "last_hash": self.last_block.block_hash,
            "config": {
                "difficulty": self.config.difficulty,
                "max_transactions_per_block": self.config.max_transactions_per_block
            }
        }
        with open(os.path.join(self.config.data_dir, "metadata.json"), 'w') as f:
            json.dump(metadata, f, indent=2)

    def _load_from_disk(self) -> bool:
        """
        Loads the blockchain from disk.

        Returns:
            True if loaded successfully
        """
        metadata_path = os.path.join(self.config.data_dir, "metadata.json")

        if not os.path.exists(metadata_path):
            return False

        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

            # Load blocks
            self.chain = []
            for i in range(metadata["height"]):
                filepath = os.path.join(self.config.data_dir, f"block_{i}.json")
                with open(filepath, 'r', encoding='utf-8') as f:
                    block = Block.from_json(f.read())
                    self.chain.append(block)

            # Validate loaded chain
            is_valid, error = self.validate_chain()
            if not is_valid:
                print(f"Loaded blockchain is invalid: {error}")
                self.chain = []
                return False

            print(f"Blockchain loaded: {len(self.chain)} blocks")
            return True

        except Exception as e:
            print(f"Error loading blockchain: {e}")
            return False

    def export_to_json(self) -> str:
        """Exports the entire blockchain to JSON."""
        return json.dumps({
            "chain": [block.to_dict() for block in self.chain],
            "statistics": self.get_statistics()
        }, ensure_ascii=False, indent=2)

    def iter_transactions(self) -> Iterator[Transaction]:
        """Iterates through all transactions."""
        for block in self.chain:
            for tx in block.transactions:
                yield tx

    def __len__(self) -> int:
        return len(self.chain)

    def __iter__(self) -> Iterator[Block]:
        return iter(self.chain)

    def __str__(self) -> str:
        return f"Blockchain(height={len(self.chain)}, transactions={sum(len(b.transactions) for b in self.chain)})"

