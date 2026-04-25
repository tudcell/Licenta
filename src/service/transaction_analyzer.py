"""Facade service coordinating transaction analysis sub-services."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.domain.entities.audit_report import AuditReport
from src.domain.entities.blockchain import Blockchain, BlockchainConfig
from src.domain.entities.transaction import Transaction
from src.domain.ml.anomaly_detector import AnomalyDetector
from src.repository.analysis_state_repository import AnalysisStateRepository
from src.service.detector_training_service import DetectorTrainingService
from src.service.mining_analysis_service import MiningAnalysisService
from src.service.transaction_audit_service import TransactionAuditService
from src.service.transaction_ingestion_service import TransactionIngestionService


class TransactionAnalyzer:
    def __init__(
        self,
        blockchain: Blockchain = None,
        detector: AnomalyDetector = None,
        auto_train: bool = False,
        min_training_samples: int = 100,
    ):
        self.blockchain = blockchain or Blockchain(BlockchainConfig(auto_save=False))
        self._detector = detector or AnomalyDetector()
        self.auto_train = auto_train
        self.min_training_samples = min_training_samples
        self.state = AnalysisStateRepository()

        self.training_service = DetectorTrainingService(self._detector, self.min_training_samples)
        self.ingestion_service = TransactionIngestionService(
            blockchain=self.blockchain,
            detector=self._detector,
            state=self.state,
            training_service=self.training_service,
            auto_train=self.auto_train,
        )
        self.mining_service = MiningAnalysisService(self.blockchain, self.state)
        self.audit_service = TransactionAuditService(
            blockchain=self.blockchain,
            detector=self._detector,
            state=self.state,
            training_service=self.training_service,
        )

    @property
    def detector(self) -> AnomalyDetector:
        return self._detector

    @detector.setter
    def detector(self, value: AnomalyDetector) -> None:
        self._detector = value
        self.training_service.detector = value
        self.ingestion_service.detector = value
        self.audit_service.detector = value

    @property
    def alerts(self) -> List[AuditReport]:
        return self.state.alerts

    @property
    def analysis_count(self) -> int:
        return self.state.analysis_count

    def get_clean_training_transactions(self, transactions: Optional[List[Transaction]] = None) -> List[Transaction]:
        source = transactions if transactions is not None else self.state.historical_transactions
        return self.training_service.get_clean_training_transactions(source)


    def add_transaction(self, transaction: Transaction) -> AuditReport:
        return self.ingestion_service.add_transaction(transaction)

    def train_detector(self, transactions: List[Transaction] = None):
        source = transactions if transactions is not None else self.state.historical_transactions
        self.training_service.train_detector(source)

    def mine_and_analyze(self) -> Optional[Dict[str, Any]]:
        return self.mining_service.mine_and_analyze()

    def analyze_transaction(self, transaction_id: str) -> Optional[AuditReport]:
        return self.audit_service.analyze_transaction(transaction_id)

    def get_alerts(self, limit: int = None, severity: str = None) -> List[AuditReport]:
        return self.audit_service.get_alerts(limit=limit, severity=severity)

    def get_statistics(self) -> Dict[str, Any]:
        return self.audit_service.get_statistics()

    def validate_blockchain_integrity(self) -> Dict[str, Any]:
        return self.audit_service.validate_blockchain_integrity()

    def export_audit_log(self) -> str:
        return self.audit_service.export_audit_log()

