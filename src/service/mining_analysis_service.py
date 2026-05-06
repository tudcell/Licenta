"""Service for mining pending transactions and reconciling audit reports."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.domain.entities.audit_report import AuditReport
from src.domain.entities.blockchain import Blockchain
from src.service.analysis_state import AnalysisState


class MiningAnalysisService:
    def __init__(self, blockchain: Blockchain, state: AnalysisState):
        self.blockchain = blockchain
        self.state = state

    def mine_and_analyze(self) -> Optional[Dict[str, Any]]:
        new_block = self.blockchain.mine_pending_transactions()
        if not new_block:
            return None

        results: List[AuditReport] = []
        for tx in new_block.transactions:
            merkle_valid = new_block.verify_transaction_inclusion(tx)
            existing_alert = next((a for a in self.state.alerts if a.transaction_id == tx.transaction_id), None)

            if existing_alert:
                existing_alert.block_index = new_block.index
                existing_alert.merkle_proof_valid = merkle_valid
                existing_alert.blockchain_valid = True
                existing_alert.added_to_mempool = False
                report = existing_alert
            else:
                report = AuditReport(
                    transaction_id=tx.transaction_id,
                    blockchain_valid=True,
                    signature_valid=tx.verify_signature(),
                    anomaly_result=None,
                    block_index=new_block.index,
                    merkle_proof_valid=merkle_valid,
                    flagged_for_review=False,
                    added_to_mempool=False,
                )

            self.state.save_report(report)
            results.append(report)

        return {
            "block": new_block.to_dict(),
            "analysis_results": [item.to_dict() for item in results],
            "anomalies_found": sum(1 for item in results if item.is_suspicious),
        }

