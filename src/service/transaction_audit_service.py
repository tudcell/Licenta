"""Service for transaction-level analysis and audit/statistics export."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.domain.entities.audit_report import AuditReport
from src.domain.entities.blockchain import Blockchain
from src.domain.ml.anomaly_detector import AnomalyDetector
from src.repository.analysis_state_repository import AnalysisStateRepository
from src.service.detector_training_service import DetectorTrainingService


class TransactionAuditService:
    def __init__(
        self,
        blockchain: Blockchain,
        detector: AnomalyDetector,
        state: AnalysisStateRepository,
        training_service: DetectorTrainingService,
    ):
        self.blockchain = blockchain
        self.detector = detector
        self.state = state
        self.training_service = training_service

    def analyze_transaction(self, transaction_id: str) -> Optional[AuditReport]:
        cached = self.state.get_report(transaction_id)
        if cached:
            return cached

        result = self.blockchain.get_transaction(transaction_id)
        if not result:
            return None

        tx, block = result
        signature_valid = tx.verify_signature()
        merkle_valid = block.verify_transaction_inclusion(tx)
        blockchain_valid, _ = self.blockchain.validate_chain()

        anomaly_result = None
        flagged_for_review = False
        if self.detector.is_fitted:
            all_transactions = self.blockchain.get_all_transactions()
            tx_index = next((i for i, item in enumerate(all_transactions) if item.transaction_id == transaction_id), -1)
            historical = all_transactions[:tx_index] if tx_index > 0 else []
            anomaly_result = self.detector.predict(tx, historical)
            flagged_for_review = bool(anomaly_result.is_anomaly)

        report = AuditReport(
            transaction_id=transaction_id,
            blockchain_valid=blockchain_valid,
            signature_valid=signature_valid,
            anomaly_result=anomaly_result,
            block_index=block.index,
            merkle_proof_valid=merkle_valid,
            flagged_for_review=flagged_for_review,
            added_to_mempool=False,
        )
        self.state.save_report(report)
        return report

    def get_alerts(self, limit: int = None, severity: str = None) -> List[AuditReport]:
        return self.state.get_alerts(limit=limit, severity=severity)

    def get_statistics(self) -> Dict[str, Any]:
        blockchain_stats = self.blockchain.get_statistics()
        anomaly_stats = {}
        detector_trained = bool(self.detector.is_fitted)
        training_stats = self.detector.training_stats if detector_trained else {}

        if self.detector.is_fitted and self.state.reports_by_transaction_id:
            anomaly_results = [
                report.anomaly_result
                for report in self.state.reports_by_transaction_id.values()
                if report.anomaly_result is not None
            ]
            if anomaly_results:
                anomaly_stats = self.detector.get_anomaly_statistics(anomaly_results)

        return {
            "blockchain": blockchain_stats,
            "analysis": {
                "total_analyzed": self.state.analysis_count,
                "alerts_count": len(self.state.alerts),
                "blockchain_length": len(self.blockchain.chain),
                "clean_training_candidates": len(
                    self.training_service.get_clean_training_transactions(self.state.historical_transactions)
                ),
                "detector_fitted": detector_trained,
                "detector_trained": detector_trained,
                "training_samples": training_stats.get("n_samples", 0),
                "trained_at": training_stats.get("trained_at"),
            },
            "anomaly_detection": anomaly_stats,
        }

    def validate_blockchain_integrity(self) -> Dict[str, Any]:
        is_valid, error = self.blockchain.validate_chain()
        invalid_signatures = []
        for block in self.blockchain:
            for tx in block.transactions:
                if not tx.verify_signature():
                    invalid_signatures.append(tx.transaction_id)

        return {
            "chain_valid": is_valid,
            "error": error,
            "invalid_signatures": invalid_signatures,
            "total_blocks": len(self.blockchain),
            "total_transactions": sum(len(item.transactions) for item in self.blockchain),
        }

    def export_audit_log(self) -> str:
        return json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "statistics": self.get_statistics(),
                "integrity_check": self.validate_blockchain_integrity(),
                "alerts": [item.to_dict() for item in self.state.alerts],
                "blockchain": {
                    "height": self.blockchain.height,
                    "blocks": [item.to_dict() for item in self.blockchain],
                },
            },
            ensure_ascii=False,
            indent=2,
        )
