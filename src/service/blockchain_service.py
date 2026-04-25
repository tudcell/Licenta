"""Blockchain use-cases for chain queries, mining, and mempool views."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple

from src.infrastructure.metadata_store import MetadataStore
from src.domain.entities.blockchain import Blockchain
from src.service.exceptions import ServiceError
from src.service.transaction_analyzer import TransactionAnalyzer
from src.utils.pagination import paginate_sequence


class BlockchainService:
    def __init__(
        self,
        blockchain: Blockchain,
        analyzer: TransactionAnalyzer,
        metadata_store: MetadataStore,
    ):
        self.blockchain = blockchain
        self.analyzer = analyzer
        self.metadata_store = metadata_store

    def health(self) -> dict:
        return {
            "status": "healthy",
            "blockchain_height": len(self.blockchain),
            "mempool_size": len(self.blockchain.get_mempool_transactions()),
            "detector_trained": self.analyzer.detector.is_fitted,
            "alerts_unresolved": self.metadata_store.get_alert_stats().get("unresolved", 0),
        }

    def get_blockchain(self, page: int, per_page: int) -> Tuple[dict, dict]:
        blocks = [block.to_dict() for block in self.blockchain]
        paginated_blocks, pagination = paginate_sequence(blocks, page, per_page)
        return {
            "chain": paginated_blocks,
            "height": len(self.blockchain),
            "is_valid": self.blockchain.validate_chain()[0],
        }, pagination

    def get_stats(self) -> dict:
        stats = self.blockchain.get_statistics()
        stats["alerts"] = self.metadata_store.get_alert_stats()
        return stats

    def validate(self) -> dict:
        is_valid, error = self.blockchain.validate_chain()
        return {
            "is_valid": is_valid,
            "error": error,
            "height": len(self.blockchain),
        }

    def get_block(self, index: int) -> dict:
        block = self.blockchain.get_block(index)
        if not block:
            raise ServiceError("Block not found", status_code=404, error_code="BLOCK_NOT_FOUND")
        return block.to_dict()

    def mine_block(self, role: str) -> dict:
        if role not in ("admin", "operator"):
            raise ServiceError("Access forbidden. Required: admin, operator", status_code=403, error_code="FORBIDDEN")

        if not self.blockchain.get_mempool_transactions():
            raise ServiceError("No transactions in mempool", status_code=400, error_code="EMPTY_MEMPOOL")

        result = self.analyzer.mine_and_analyze()
        if not result:
            raise ServiceError("Could not mine block", status_code=500, error_code="MINE_FAILED")

        new_block = self.blockchain.get_block(result["block"]["index"])
        if new_block:
            for tx in new_block.transactions:
                index_record = self.metadata_store.get_transaction_index(tx.transaction_id) or {}
                is_flagged = bool(index_record.get("is_flagged", 0))
                self.metadata_store.update_transaction_state(
                    tx.transaction_id,
                    block_index=new_block.index,
                    tx_status="MINED",
                    is_flagged=is_flagged,
                )

        return {
            "block": result["block"],
            "anomalies_found": result["anomalies_found"],
            "event": {
                "block_index": result["block"]["index"],
                "transaction_count": result["block"].get("transaction_count", 0),
                "anomalies_found": result["anomalies_found"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

    def get_mempool(self, page: int, per_page: int) -> Tuple[dict, dict]:
        mempool_txs = [tx.to_dict() for tx in self.blockchain.get_mempool_transactions()]
        paginated, pagination = paginate_sequence(mempool_txs, page, per_page)
        return {
            "transactions": paginated,
            "count": len(paginated),
            "total_mempool": len(mempool_txs),
        }, pagination
