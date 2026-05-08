"""Transaction use-cases: create + index + alert + publish."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.domain.authorization import Principal, Role
from src.domain.entities.blockchain import Blockchain
from src.domain.entities.transaction import TransactionStatus, TransactionType
from src.domain.entities.wallet import WalletManager
from src.domain.errors import (
    AuthError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from src.domain.events import DomainEvent, EventBus, NullEventBus
from src.infrastructure.persistence.sqlite import (
    AlertRepository,
    TransactionIndexRepository,
    UserRepository,
)
from src.service.transaction_audit_service import TransactionAuditService
from src.service.transaction_ingestion_service import TransactionIngestionService
from src.utils.pagination import build_pagination_metadata

logger = logging.getLogger("blockchain_audit")


class TransactionService:
    def __init__(
            self,
            wallet_manager: WalletManager,
            blockchain: Blockchain,
            ingestion: TransactionIngestionService,
            audit: TransactionAuditService,
            users: UserRepository,
            transactions: TransactionIndexRepository,
            alerts: AlertRepository,
            event_bus: Optional[EventBus] = None,
    ):
        self._wallets = wallet_manager
        self._blockchain = blockchain
        self._ingestion = ingestion
        self._audit = audit
        self._users = users
        self._transactions = transactions
        self._alerts = alerts
        self._event_bus: EventBus = event_bus or NullEventBus()

    def create_transaction(
            self,
            principal: Principal,
            transaction_type: TransactionType,
            transaction_data: Dict[str, Any],
            wallet_name: Optional[str],
            metadata: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        principal.require(Role.ADMIN, Role.OPERATOR)
        user = self._users.get(principal.username)
        if not user:
            raise AuthError("Authenticated user not found")

        owned_wallet = user.get("wallet_name")
        requested_wallet_name = wallet_name or owned_wallet
        if not requested_wallet_name:
            raise ValidationError(
                "User has no wallet assigned. Create a wallet first via /api/wallet.",
                error_code="USER_HAS_NO_WALLET",
            )
        if owned_wallet and requested_wallet_name != owned_wallet and principal.role is not Role.ADMIN:
            raise ForbiddenError(
                "Wallet does not belong to the authenticated user",
                error_code="WALLET_FORBIDDEN",
            )

        wallet = self._wallets.get_wallet(requested_wallet_name)
        if wallet is None:
            raise NotFoundError(
                f"Wallet '{requested_wallet_name}' not found. Create it first via /api/wallet.",
                error_code="WALLET_NOT_FOUND",
            )

        tx_metadata: Dict[str, Any] = dict(metadata or {})
        tx_metadata.setdefault("submitted_by", principal.username)
        tx_metadata.setdefault("flagged", False)

        tx = wallet.create_and_sign_transaction(
            transaction_type=transaction_type,
            data=transaction_data,
            metadata=tx_metadata,
        )

        report = self._ingestion.add_transaction(tx)

        if not report.signature_valid:
            self._index(tx, report, tx_status=TransactionStatus.REJECTED, is_flagged=True)
            self._alerts.save(report)
            raise ValidationError(
                "Transaction signature is invalid",
                error_code="INVALID_SIGNATURE",
                data={"transaction": tx.to_dict(), "analysis": report.to_dict()},
            )

        if not report.added_to_mempool:
            self._index(tx, report, tx_status=TransactionStatus.REJECTED, is_flagged=report.is_suspicious)
            if report.is_suspicious:
                self._alerts.save(report)
            raise ConflictError(
                "Transaction was not added to the mempool",
                error_code="MEMPOOL_REJECTED",
                data={"transaction": tx.to_dict(), "analysis": report.to_dict()},
            )

        tx_status = TransactionStatus.FLAGGED if report.flagged_for_review else TransactionStatus.PENDING
        self._index(tx, report, tx_status=tx_status, is_flagged=report.flagged_for_review)

        if report.is_suspicious:
            alert_id = self._alerts.save(report)
            self._event_bus.publish(
                DomainEvent(
                    name="anomaly_detected",
                    payload=self._alert_payload(tx, report, alert_id),
                )
            )
            logger.warning(
                "Suspicious transaction flagged and added to mempool: tx=%s status=%s",
                str(tx.transaction_id)[:16],
                report.overall_status,
            )

        return {"transaction": tx.to_dict(), "analysis": report.to_dict()}

    def list_indexed_transactions(
            self,
            page: int,
            per_page: int,
            sender: Optional[str] = None,
            tx_type: Optional[str] = None,
            tx_status: Optional[str] = None,
            flagged: Optional[bool] = None,
            transaction_id: Optional[str] = None,
    ) -> tuple[dict, dict]:
        entries, total = self._transactions.search(
            sender=sender,
            tx_type=tx_type,
            status=tx_status,
            flagged=flagged,
            transaction_id=transaction_id,
            page=page,
            per_page=per_page,
        )
        serialized = [entry.to_legacy_dict() for entry in entries]
        pagination = build_pagination_metadata(page, per_page, total)
        return {"transactions": serialized, "count": len(serialized)}, pagination

    def get_transaction_details(self, transaction_id: str) -> Optional[dict]:
        proof = self._blockchain.verify_transaction_proof(transaction_id)
        index_entry = self._transactions.get(transaction_id)
        if proof:
            payload = dict(proof)
            if index_entry:
                payload["index_record"] = index_entry.to_legacy_dict()
            return payload
        if index_entry:
            return {"index_record": index_entry.to_legacy_dict()}
        return None

    def analyze_transaction(self, transaction_id: str):
        return self._audit.analyze_transaction(transaction_id)

    def _index(self, tx, report, tx_status: TransactionStatus, is_flagged: bool) -> None:
        self._transactions.index(
            tx,
            tx_status=tx_status.value,
            is_flagged=is_flagged,
            ml_score=self._score(report),
            ml_reason=self._reason(report),
        )

    @staticmethod
    def _score(report) -> Optional[float]:
        return float(report.anomaly_result.anomaly_score) if report.anomaly_result else None

    @staticmethod
    def _reason(report) -> Optional[str]:
        return report.anomaly_result.explanation if report.anomaly_result else None

    @staticmethod
    def _alert_payload(tx, report, alert_id: int) -> dict:
        return {
            "alert_id": alert_id,
            "transaction_id": tx.transaction_id,
            "status": report.overall_status,
            "explanation": report.anomaly_result.explanation if report.anomaly_result else None,
            "score": float(report.anomaly_result.anomaly_score) if report.anomaly_result else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
