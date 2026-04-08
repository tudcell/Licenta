"""Repository adapter around blockchain aggregate operations."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.domain.entities.block import Block
from src.domain.entities.blockchain import Blockchain
from src.domain.entities.transaction import Transaction, TransactionType


class BlockchainRepository:
    def __init__(self, blockchain: Blockchain):
        self._blockchain = blockchain

    @property
    def raw(self) -> Blockchain:
        return self._blockchain

    def __iter__(self):
        return iter(self._blockchain)

    def __len__(self) -> int:
        return len(self._blockchain)

    def get_statistics(self) -> Dict[str, Any]:
        return self._blockchain.get_statistics()

    def validate_chain(self) -> tuple[bool, Optional[str]]:
        return self._blockchain.validate_chain()

    def get_block(self, index: int) -> Optional[Block]:
        return self._blockchain.get_block(index)

    def get_all_transactions(self) -> list[Transaction]:
        return self._blockchain.get_all_transactions()

    def get_mempool_transactions(self) -> list[Transaction]:
        return self._blockchain.get_mempool_transactions()

    def add_transaction(self, transaction: Transaction) -> bool:
        return self._blockchain.add_transaction(transaction)

    def mine_pending_transactions(self) -> Optional[Block]:
        return self._blockchain.mine_pending_transactions()

    def verify_transaction_proof(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        return self._blockchain.verify_transaction_proof(transaction_id)

    def get_transaction(self, transaction_id: str):
        return self._blockchain.get_transaction(transaction_id)

    def get_transactions_by_type(self, tx_type: TransactionType) -> list[Transaction]:
        return self._blockchain.get_transactions_by_type(tx_type)

