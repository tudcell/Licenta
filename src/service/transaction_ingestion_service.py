"""Service for validating, scoring, and ingesting new transactions."""

from __future__ import annotations

from src.domain.entities.audit_report import AuditReport
from src.domain.entities.blockchain import Blockchain
from src.domain.entities.transaction import Transaction
from src.domain.ml.anomaly_detector import AnomalyDetector
from src.service.analysis_state import AnalysisState
from src.service.detector_training_service import DetectorTrainingService


class TransactionIngestionService:
    def __init__(
        self,
        blockchain: Blockchain,
        detector: AnomalyDetector,
        state: AnalysisState,
        training_service: DetectorTrainingService,
        auto_train: bool,
    ):
        self.blockchain = blockchain
        self.detector = detector
        self.state = state
        self.training_service = training_service
        self.auto_train = auto_train

    def add_transaction(self, transaction: Transaction) -> AuditReport:
        signature_valid = transaction.verify_signature()
        history_before_current = self.state.snapshot_history()

        self.training_service.try_auto_train(history_before_current, auto_train=self.auto_train)

        anomaly_result = None
        flagged_for_review = False
        if self.detector.is_fitted and signature_valid:
            anomaly_result = self.detector.predict(transaction, history_before_current)
            flagged_for_review = bool(anomaly_result.is_anomaly)

        added_to_mempool = False
        if signature_valid:
            added_to_mempool = self.blockchain.add_transaction(transaction)

        if signature_valid and added_to_mempool:
            self.state.append_history(transaction)

        report = AuditReport(
            transaction_id=transaction.transaction_id,
            blockchain_valid=True,
            signature_valid=signature_valid,
            anomaly_result=anomaly_result,
            block_index=None,
            merkle_proof_valid=True,
            flagged_for_review=flagged_for_review,
            added_to_mempool=added_to_mempool,
        )

        self.state.increment_analysis_count()
        self.state.cache_report(report)
        return report

