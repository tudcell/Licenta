"""Convenience factories for synthesizing transactions in demo/data generators.

Lives in `utils/` because production code never builds transactions through
these helpers — `Wallet.create_and_sign_transaction` is the real entry point.
"""

from __future__ import annotations

from typing import Optional

from src.domain.entities.transaction import Transaction, TransactionType
from src.domain.value_objects import RiskLevel


class TransactionFactory:
    """Stateless factory used by demo/training data generators only."""

    @staticmethod
    def create_login_event(
        user_id: str,
        sender_address: str,
        ip_address: str,
        user_agent: Optional[str] = None,
        success: bool = True,
    ) -> Transaction:
        tx_type = TransactionType.LOGIN if success else TransactionType.LOGIN_FAILED
        risk = RiskLevel.LOW if success else RiskLevel.MEDIUM
        return Transaction(
            transaction_type=tx_type,
            sender_address=sender_address,
            data={"user_id": user_id, "ip_address": ip_address, "user_agent": user_agent, "success": success},
            metadata={"category": "authentication", "risk_level": risk.value},
        )

    @staticmethod
    def create_data_access_event(
        user_id: str,
        sender_address: str,
        resource_id: str,
        action: str,
        success: bool = True,
    ) -> Transaction:
        type_map = {
            "read": TransactionType.DATA_READ,
            "write": TransactionType.DATA_WRITE,
            "delete": TransactionType.DATA_DELETE,
            "modify": TransactionType.DATA_MODIFY,
        }
        risk = RiskLevel.HIGH if action == "delete" else RiskLevel.LOW
        return Transaction(
            transaction_type=type_map.get(action, TransactionType.CUSTOM),
            sender_address=sender_address,
            data={"user_id": user_id, "resource_id": resource_id, "action": action, "success": success},
            metadata={"category": "data_access", "risk_level": risk.value},
        )

    @staticmethod
    def create_transfer_event(
        sender_address: str,
        recipient_address: str,
        amount: float,
        currency: str = "RON",
    ) -> Transaction:
        risk = RiskLevel.HIGH if amount > 10000 else RiskLevel.MEDIUM if amount > 1000 else RiskLevel.LOW
        return Transaction(
            transaction_type=TransactionType.TRANSFER,
            sender_address=sender_address,
            data={"recipient": recipient_address, "amount": amount, "currency": currency},
            metadata={"category": "financial", "risk_level": risk.value},
        )
