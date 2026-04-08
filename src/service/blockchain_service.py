"""Blockchain service use-cases."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.repository import BlockchainRepository, MetadataRepository


class BlockchainService:
    def __init__(self, blockchain_repository: BlockchainRepository, metadata_repository: MetadataRepository, analyzer):
        self.blockchain_repository = blockchain_repository
        self.metadata_repository = metadata_repository
        self.analyzer = analyzer

    def get_health(self):
        return {
            'status': 'healthy',
            'blockchain_height': self.blockchain_repository.get_height(),
            'mempool_size': len(self.blockchain_repository.get_mempool_transactions()),
            'detector_trained': self.analyzer.detector.is_fitted,
            'alerts_unresolved': self.metadata_repository.get_alert_stats().get('unresolved', 0),
        }

    def get_chain(self):
        blocks = [block.to_dict() for block in self.blockchain_repository.iter_chain()]
        return {
            'chain': blocks,
            'height': self.blockchain_repository.get_height(),
            'is_valid': self.blockchain_repository.validate_chain()[0],
        }

    def get_stats(self):
        stats = self.blockchain_repository.get_statistics()
        stats['alerts'] = self.metadata_repository.get_alert_stats()
        return stats

    def validate(self):
        is_valid, error = self.blockchain_repository.validate_chain()
        return {'is_valid': is_valid, 'error': error, 'height': self.blockchain_repository.get_height()}

    def mine_block(self) -> Optional[Dict[str, Any]]:
        result = self.analyzer.mine_and_analyze()
        if not result:
            return None

        new_block = self.blockchain_repository.get_block(result['block']['index'])
        if new_block:
            for tx in new_block.transactions:
                index_record = self.metadata_repository.get_transaction_index(tx.transaction_id) or {}
                is_flagged = bool(index_record.get('is_flagged', 0))
                self.metadata_repository.update_transaction_state(
                    tx.transaction_id,
                    block_index=new_block.index,
                    tx_status='FLAGGED' if is_flagged else 'MINED',
                    is_flagged=is_flagged,
                )
        return result
