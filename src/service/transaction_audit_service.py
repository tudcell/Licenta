"""Per-transaction analysis + statistics for the dashboard."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.domain.entities.audit_report import AuditReport
from src.domain.entities.blockchain import Blockchain
from src.domain.entities.transaction import Transaction
from src.domain.ml.anomaly_detector import AnomalyDetector
from src.service.analysis_state import AnalysisState
from src.service.detector_training_service import DetectorTrainingService


class TransactionAuditService:
    def __init__(
        self,
        blockchain: Blockchain,
        detector: AnomalyDetector,
        state: AnalysisState,
        training_service: DetectorTrainingService,
    ):
        self.blockchain = blockchain
        self.detector = detector
        self.state = state
        self.training_service = training_service

    def _rehydrate_state_from_blockchain_if_needed(self) -> None:
        """Rebuild in-memory reports/alerts from persisted chain data after restart."""
        all_transactions = self.blockchain.get_all_transactions()
        if not all_transactions:
            return
        # Skip only when our cache already covers every chain transaction.
        if len(self.state.reports_by_transaction_id) >= len(all_transactions):
            return

        blockchain_valid, _ = self.blockchain.validate_chain()
        history: List[Transaction] = []
        reconstructed_reports: Dict[str, AuditReport] = {}
        reconstructed_alerts: List[AuditReport] = []

        for block in self.blockchain:
            for tx in block.transactions:
                signature_valid = tx.verify_signature()
                merkle_valid = block.verify_transaction_inclusion(tx)
                anomaly_result = None
                flagged_for_review = False

                if self.detector.is_fitted and signature_valid:
                    anomaly_result = self.detector.predict(tx, history)
                    flagged_for_review = bool(anomaly_result.is_anomaly)

                report = AuditReport(
                    transaction_id=tx.transaction_id,
                    blockchain_valid=blockchain_valid,
                    signature_valid=signature_valid,
                    anomaly_result=anomaly_result,
                    block_index=block.index,
                    merkle_proof_valid=merkle_valid,
                    flagged_for_review=flagged_for_review,
                    added_to_mempool=False,
                )
                reconstructed_reports[tx.transaction_id] = report
                if report.is_suspicious:
                    reconstructed_alerts.append(report)
                if signature_valid:
                    history.append(tx)

        self.state.reports_by_transaction_id = reconstructed_reports
        self.state.alerts = reconstructed_alerts
        self.state.historical_transactions = history
        self.state.analysis_count = max(self.state.analysis_count, len(reconstructed_reports))

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
        self._rehydrate_state_from_blockchain_if_needed()
        return self.state.get_alerts(limit=limit, severity=severity)

    def get_statistics(self) -> Dict[str, Any]:
        self._rehydrate_state_from_blockchain_if_needed()
        return self.statistics_from_reports(list(self.state.reports_by_transaction_id.values()))

    def statistics_from_reports(self, reports: List[AuditReport]) -> Dict[str, Any]:
        """Build the statistics payload from a precomputed report set, without
        re-traversing the chain. Used by IntegrityService.export_audit_log."""
        blockchain_stats = self.blockchain.get_statistics()
        anomaly_stats: Dict[str, Any] = {}
        detector_trained = bool(self.detector.is_fitted)
        training_stats = self.detector.training_stats if detector_trained else {}

        if detector_trained and reports:
            anomaly_results = [report.anomaly_result for report in reports if report.anomaly_result is not None]
            if anomaly_results:
                anomaly_stats = self.detector.get_anomaly_statistics(anomaly_results)

        alerts_count = sum(1 for report in reports if report.is_suspicious)

        return {
            "blockchain": blockchain_stats,
            "analysis": {
                "total_analyzed": max(self.state.analysis_count, len(reports)),
                "alerts_count": alerts_count,
                "blockchain_length": len(self.blockchain.chain),
                "clean_training_candidates": len(
                    self.training_service.get_clean_training_transactions(self.state.historical_transactions)
                ),
                "detector_fitted": detector_trained,
                "training_samples": training_stats.get("n_samples", 0),
                "trained_at": training_stats.get("trained_at"),
            },
            "anomaly_detection": anomaly_stats,
        }
