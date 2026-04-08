"""Repository adapter around transaction analyzer operations/state."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.domain.entities.audit_report import AuditReport
from src.domain.entities.transaction import Transaction
from src.service.transaction_analyzer import TransactionAnalyzer


class AnalyzerRepository:
    def __init__(self, analyzer: TransactionAnalyzer):
        self._analyzer = analyzer

    @property
    def raw(self) -> TransactionAnalyzer:
        return self._analyzer

    @property
    def detector(self):
        return self._analyzer.detector

    @property
    def min_training_samples(self) -> int:
        return self._analyzer.min_training_samples

    def add_transaction(self, transaction: Transaction) -> AuditReport:
        return self._analyzer.add_transaction(transaction)

    def train_detector(self, transactions: list[Transaction] = None) -> None:
        self._analyzer.train_detector(transactions)

    def mine_and_analyze(self) -> Optional[Dict[str, Any]]:
        return self._analyzer.mine_and_analyze()

    def analyze_transaction(self, transaction_id: str) -> Optional[AuditReport]:
        return self._analyzer.analyze_transaction(transaction_id)

    def get_statistics(self) -> Dict[str, Any]:
        return self._analyzer.get_statistics()

    def validate_blockchain_integrity(self) -> Dict[str, Any]:
        return self._analyzer.validate_blockchain_integrity()

    def export_audit_log(self) -> str:
        return self._analyzer.export_audit_log()

    def get_clean_training_transactions(self, transactions: list[Transaction]) -> list[Transaction]:
        return self._analyzer._get_clean_training_transactions(transactions)

