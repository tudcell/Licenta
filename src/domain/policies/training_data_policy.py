"""Policy rules for selecting clean detector training transactions."""

from __future__ import annotations

from src.domain.entities.transaction import Transaction, TransactionType
from src.domain.value_objects import RiskLevel

_HIGH_RISK_LEVELS = {RiskLevel.HIGH, RiskLevel.CRITICAL}
_DIRTY_TYPES = {
    TransactionType.LOGIN_FAILED,
    TransactionType.ACCESS_DENIED,
    TransactionType.DATA_DELETE,
}


class TrainingDataPolicy:
    @staticmethod
    def is_clean_candidate(transaction: Transaction) -> bool:
        if not transaction.verify_signature():
            return False
        if transaction.metadata.get("anomaly_type"):
            return False

        risk_level = RiskLevel.from_string(
            transaction.metadata.get("risk_level"),
            default=RiskLevel.LOW,
        )
        if risk_level in _HIGH_RISK_LEVELS:
            return False

        return transaction.transaction_type not in _DIRTY_TYPES
