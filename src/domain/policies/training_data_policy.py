"""Policy rules for selecting clean detector training transactions."""

from __future__ import annotations

from src.domain.entities.transaction import Transaction, TransactionType


class TrainingDataPolicy:
    @staticmethod
    def is_clean_candidate(transaction: Transaction) -> bool:
        if not transaction.verify_signature():
            return False
        if transaction.metadata.get("anomaly_type"):
            return False

        risk_level = str(transaction.metadata.get("risk_level", "low")).lower()
        if risk_level in {"high", "critical"}:
            return False

        if transaction.transaction_type in {
            TransactionType.LOGIN_FAILED,
            TransactionType.ACCESS_DENIED,
            TransactionType.DATA_DELETE,
        }:
            return False

        return True

