"""Repository for blockchain and mempool persistence-backed access."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.domain import Blockchain, Block, Transaction, TransactionType


class BlockchainRepository:
    """Persistence gateway around the domain blockchain aggregate."""

    def __init__(self, blockchain: Blockchain):
        self._blockchain = blockchain

    @property
    def blockchain(self) -> Blockchain:
        return self._blockchain

    def iter_chain(self):
        return iter(self._blockchain)

    def get_height(self) -> int:
        return len(self._blockchain)

    def get_block(self, index: int) -> Optional[Block]:
        return self._blockchain.get_block(index)

    def get_statistics(self) -> Dict[str, Any]:
        return self._blockchain.get_statistics()

    def validate_chain(self):
        return self._blockchain.validate_chain()

    def get_mempool_transactions(self):
        return self._blockchain.get_mempool_transactions()

    def add_transaction(self, transaction: Transaction) -> bool:
        return self._blockchain.add_transaction(transaction)

    def mine_pending_transactions(self) -> Optional[Block]:
        return self._blockchain.mine_pending_transactions()

    def verify_transaction_proof(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        return self._blockchain.verify_transaction_proof(transaction_id)

    def get_all_transactions(self):
        return self._blockchain.get_all_transactions()

    def get_transactions_by_type(self, tx_type: TransactionType):
        return self._blockchain.get_transactions_by_type(tx_type)
