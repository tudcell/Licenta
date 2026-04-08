"""Blockchain use-cases for chain queries, mining, and mempool views."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple

from src.repository.analyzer_repository import AnalyzerRepository
from src.repository.blockchain_repository import BlockchainRepository
from src.repository.metadata_repository import MetadataRepository
from src.service.exceptions import ServiceError


def _paginate(items: list, page: int, per_page: int) -> Tuple[list, dict]:
    safe_page = max(1, page)
    safe_per_page = max(1, min(per_page, 100))
    total = len(items)
    start = (safe_page - 1) * safe_per_page
    end = start + safe_per_page
    pagination = {
        "page": safe_page,
        "per_page": safe_per_page,
        "total": total,
        "total_pages": max(1, (total + safe_per_page - 1) // safe_per_page),
        "has_next": safe_page * safe_per_page < total,
        "has_prev": safe_page > 1,
    }
    return items[start:end], pagination


class BlockchainService:
    def __init__(
        self,
        blockchain_repository: BlockchainRepository,
        analyzer_repository: AnalyzerRepository,
        metadata_repository: MetadataRepository,
    ):
        self.blockchain_repository = blockchain_repository
        self.analyzer_repository = analyzer_repository
        self.metadata_repository = metadata_repository

    def health(self) -> dict:
        return {
            "status": "healthy",
            "blockchain_height": len(self.blockchain_repository),
            "mempool_size": len(self.blockchain_repository.get_mempool_transactions()),
            "detector_trained": self.analyzer_repository.detector.is_fitted,
            "alerts_unresolved": self.metadata_repository.get_alert_stats().get("unresolved", 0),
        }

    def get_blockchain(self, page: int, per_page: int) -> Tuple[dict, dict]:
        blocks = [block.to_dict() for block in self.blockchain_repository]
        paginated_blocks, pagination = _paginate(blocks, page, per_page)
        return {
            "chain": paginated_blocks,
            "height": len(self.blockchain_repository),
            "is_valid": self.blockchain_repository.validate_chain()[0],
        }, pagination

    def get_stats(self) -> dict:
        stats = self.blockchain_repository.get_statistics()
        stats["alerts"] = self.metadata_repository.get_alert_stats()
        return stats

    def validate(self) -> dict:
        is_valid, error = self.blockchain_repository.validate_chain()
        return {
            "is_valid": is_valid,
            "error": error,
            "height": len(self.blockchain_repository),
        }

    def get_block(self, index: int) -> dict:
        block = self.blockchain_repository.get_block(index)
        if not block:
            raise ServiceError("Block not found", status_code=404, error_code="BLOCK_NOT_FOUND")
        return block.to_dict()

    def mine_block(self, role: str) -> dict:
        if role not in ("admin", "operator"):
            raise ServiceError("Access forbidden. Required: admin, operator", status_code=403, error_code="FORBIDDEN")

        if not self.blockchain_repository.get_mempool_transactions():
            raise ServiceError("No transactions in mempool", status_code=400, error_code="EMPTY_MEMPOOL")

        result = self.analyzer_repository.mine_and_analyze()
        if not result:
            raise ServiceError("Could not mine block", status_code=500, error_code="MINE_FAILED")

        new_block = self.blockchain_repository.get_block(result["block"]["index"])
        if new_block:
            for tx in new_block.transactions:
                index_record = self.metadata_repository.get_transaction_index(tx.transaction_id) or {}
                is_flagged = bool(index_record.get("is_flagged", 0))
                self.metadata_repository.update_transaction_state(
                    tx.transaction_id,
                    block_index=new_block.index,
                    tx_status="FLAGGED" if is_flagged else "MINED",
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
        mempool_txs = [tx.to_dict() for tx in self.blockchain_repository.get_mempool_transactions()]
        paginated, pagination = _paginate(mempool_txs, page, per_page)
        return {
            "transactions": paginated,
            "count": len(paginated),
            "total_mempool": len(mempool_txs),
        }, pagination


