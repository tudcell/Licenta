"""Block module - canonical domain implementation."""

import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from src.domain.entities.transaction import Transaction
from src.domain.policies import HashUtils, MerkleProof, MerkleTree


@dataclass
class Block:
	index: int
	previous_hash: str
	timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
	nonce: int = 0
	difficulty: int = 4
	transactions: List[Transaction] = field(default_factory=list)
	merkle_root: str = field(default="", init=False)
	block_hash: str = field(default="", init=False)
	_merkle_tree: Optional[MerkleTree] = field(default=None, repr=False, init=False)

	def __post_init__(self):
		self._build_merkle_tree()
		if not self.block_hash:
			self.block_hash = self.calculate_hash()

	def _build_merkle_tree(self):
		tx_hashes = [tx.calculate_hash() for tx in self.transactions]
		self._merkle_tree = MerkleTree(tx_hashes)
		self.merkle_root = self._merkle_tree.get_root_hash()

	def get_header(self) -> Dict[str, Any]:
		return {
			"index": self.index,
			"previous_hash": self.previous_hash,
			"timestamp": self.timestamp,
			"merkle_root": self.merkle_root,
			"nonce": self.nonce,
			"difficulty": self.difficulty,
		}

	def calculate_hash(self) -> str:
		return HashUtils.hash_object(self.get_header())

	def mine(self, difficulty: int = None) -> int:
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
		if not transaction.verify_signature():
			return False
		self.transactions.append(transaction)
		self._build_merkle_tree()
		self.block_hash = self.calculate_hash()
		return True

	def get_transaction_proof(self, transaction_id: str) -> Optional[MerkleProof]:
		for tx in self.transactions:
			if tx.transaction_id == transaction_id:
				return self._merkle_tree.get_proof(tx.calculate_hash())
		return None

	def verify_transaction_inclusion(self, transaction: Transaction) -> bool:
		proof = self.get_transaction_proof(transaction.transaction_id)
		if proof is None:
			return False
		return MerkleTree.verify_proof(proof)

	def verify_integrity(self) -> bool:
		if self.block_hash != self.calculate_hash():
			return False
		if not self.block_hash.startswith('0' * self.difficulty):
			return False
		tree = MerkleTree([tx.calculate_hash() for tx in self.transactions])
		if self.merkle_root != tree.get_root_hash():
			return False
		return all(tx.verify_signature() for tx in self.transactions)

	def to_dict(self) -> Dict[str, Any]:
		return {
			"index": self.index,
			"previous_hash": self.previous_hash,
			"timestamp": self.timestamp,
			"nonce": self.nonce,
			"difficulty": self.difficulty,
			"merkle_root": self.merkle_root,
			"block_hash": self.block_hash,
			"transactions": [tx.to_dict() for tx in self.transactions],
			"transaction_count": len(self.transactions),
		}

	@classmethod
	def from_dict(cls, data: Dict[str, Any]) -> 'Block':
		transactions = [Transaction.from_dict(tx) for tx in data.get("transactions", [])]
		block = cls(
			index=data["index"],
			previous_hash=data["previous_hash"],
			timestamp=data["timestamp"],
			nonce=data["nonce"],
			difficulty=data["difficulty"],
			transactions=transactions,
		)
		block.merkle_root = data["merkle_root"]
		block.block_hash = data["block_hash"]
		return block

	def to_json(self) -> str:
		return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

	@classmethod
	def from_json(cls, json_string: str) -> 'Block':
		return cls.from_dict(json.loads(json_string))


class GenesisBlock(Block):
	def __init__(self, difficulty: int = 4):
		super().__init__(index=0, previous_hash='0' * 64, difficulty=difficulty, transactions=[])
		self.mine()


__all__ = ["Block", "GenesisBlock"]

