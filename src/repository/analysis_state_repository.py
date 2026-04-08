"""In-memory repository for transaction analysis runtime state."""

from __future__ import annotations

from typing import Dict, List, Optional

from src.domain.entities.audit_report import AuditReport
from src.domain.entities.transaction import Transaction


class AnalysisStateRepository:
    def __init__(self):
        self.alerts: List[AuditReport] = []
        self.analysis_count = 0
        self.historical_transactions: List[Transaction] = []
        self.reports_by_transaction_id: Dict[str, AuditReport] = {}

    def snapshot_history(self) -> List[Transaction]:
        return list(self.historical_transactions)

    def append_history(self, transaction: Transaction) -> None:
        self.historical_transactions.append(transaction)

    def increment_analysis_count(self) -> None:
        self.analysis_count += 1

    def save_report(self, report: AuditReport) -> None:
        self.reports_by_transaction_id[report.transaction_id] = report

    def cache_report(self, report: AuditReport) -> None:
        self.save_report(report)
        if report.is_suspicious:
            self.alerts.append(report)

    def get_report(self, transaction_id: str) -> Optional[AuditReport]:
        return self.reports_by_transaction_id.get(transaction_id)

    def get_alerts(self, limit: int = None, severity: str = None) -> List[AuditReport]:
        alerts = self.alerts
        if severity:
            alerts = [item for item in alerts if item.overall_status == severity]
        if limit:
            alerts = alerts[-limit:]
        return alerts

