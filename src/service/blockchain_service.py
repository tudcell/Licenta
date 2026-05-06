"""Blockchain use-cases for chain queries, mining, and mempool views."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple

from src.domain.authorization import Role, require_role
from src.domain.entities.blockchain import Blockchain
from src.domain.errors import InternalError, NotFoundError, ValidationError
from src.infrastructure.metadata_store import MetadataStore
from src.domain.events import DomainEvent, EventBus, NullEventBus
from src.service.transaction_analyzer import TransactionAnalyzer
from src.utils.pagination import paginate_sequence


class BlockchainService:
    def __init__(
        self,
        blockchain: Blockchain,
        analyzer: TransactionAnalyzer,
        metadata_store: MetadataStore,
        event_bus: EventBus | None = None,
    ):
        self.blockchain = blockchain
        self.analyzer = analyzer
        self.metadata_store = metadata_store
        self.event_bus: EventBus = event_bus or NullEventBus()

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
            raise NotFoundError("Block not found", error_code="BLOCK_NOT_FOUND")
        return block.to_dict()

    def mine_block(self, role: str) -> dict:
        require_role(role, Role.ADMIN, Role.OPERATOR)

        if not self.blockchain.get_mempool_transactions():
            raise ValidationError("No transactions in mempool", error_code="EMPTY_MEMPOOL")

        result = self.analyzer.mine_and_analyze()
        if not result:
            raise InternalError("Could not mine block", error_code="MINE_FAILED")

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

        event_payload = {
            "block_index": result["block"]["index"],
            "transaction_count": result["block"].get("transaction_count", 0),
            "anomalies_found": result["anomalies_found"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.event_bus.publish(DomainEvent(name="block_mined", payload=event_payload))

        return {
            "block": result["block"],
            "anomalies_found": result["anomalies_found"],
        }

    def get_mempool(self, page: int, per_page: int) -> Tuple[dict, dict]:
        mempool_txs = [tx.to_dict() for tx in self.blockchain.get_mempool_transactions()]
        paginated, pagination = paginate_sequence(mempool_txs, page, per_page)
        return {
            "transactions": paginated,
            "count": len(paginated),
            "total_mempool": len(mempool_txs),
        }, pagination
