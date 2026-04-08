"""Transaction use-cases orchestrating wallet, analyzer, and metadata repositories."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.domain.entities.transaction import TransactionType
from src.repository.analyzer_repository import AnalyzerRepository
from src.repository.metadata_repository import MetadataRepository
from src.repository.wallet_repository import WalletRepository
from src.service.exceptions import ServiceError


@dataclass
class TransactionCreateResult:
    status_code: int
    success: bool
    message: str
    data: Dict[str, Any]
    error_code: Optional[str] = None
    alert_event_payload: Optional[Dict[str, Any]] = None


class TransactionService:
    def __init__(
        self,
        wallet_repository: WalletRepository,
        metadata_repository: MetadataRepository,
        analyzer_repository: AnalyzerRepository,
    ):
        self.wallet_repository = wallet_repository
        self.metadata_repository = metadata_repository
        self.analyzer_repository = analyzer_repository

    def create_transaction(
        self,
        username: str,
        user_role: str,
        transaction_type: TransactionType,
        transaction_data: Dict[str, Any],
        wallet_name: Optional[str],
        metadata: Optional[Dict[str, Any]],
    ) -> TransactionCreateResult:
        user = self.metadata_repository.get_user(username)
        if not user:
            raise ServiceError("Authenticated user not found", status_code=401, error_code="AUTH_FAILED")

        requested_wallet_name = wallet_name or user.get("wallet_name") or username
        if user.get("wallet_name") and requested_wallet_name != user["wallet_name"] and user_role != "admin":
            raise ServiceError(
                "Wallet does not belong to the authenticated user",
                status_code=403,
                error_code="WALLET_FORBIDDEN",
            )

        wallet = self.wallet_repository.get_or_create_wallet(requested_wallet_name, metadata={"owner": username})

        if not user.get("wallet_name"):
            self.metadata_repository.assign_wallet_to_user(username, requested_wallet_name)

        tx_metadata: Dict[str, Any] = dict(metadata or {})
        tx_metadata.setdefault("submitted_by", username)
        tx_metadata.setdefault("flagged", False)

        tx = wallet.create_and_sign_transaction(
            transaction_type=transaction_type,
            data=transaction_data,
            metadata=tx_metadata,
        )

        report = self.analyzer_repository.add_transaction(tx)

        if not report.signature_valid:
            self.metadata_repository.index_transaction(
                tx,
                tx_status="REJECTED",
                is_flagged=True,
                ml_score=float(report.anomaly_result.anomaly_score) if report.anomaly_result else None,
                ml_reason=report.anomaly_result.explanation if report.anomaly_result else None,
            )
            self.metadata_repository.save_alert(report)
            return TransactionCreateResult(
                status_code=400,
                success=False,
                message="Transaction signature is invalid",
                error_code="INVALID_SIGNATURE",
                data={"transaction": tx.to_dict(), "analysis": report.to_dict()},
            )

        if not report.added_to_mempool:
            self.metadata_repository.index_transaction(
                tx,
                tx_status="REJECTED",
                is_flagged=report.is_suspicious,
                ml_score=float(report.anomaly_result.anomaly_score) if report.anomaly_result else None,
                ml_reason=report.anomaly_result.explanation if report.anomaly_result else None,
            )
            if report.is_suspicious:
                self.metadata_repository.save_alert(report)

            return TransactionCreateResult(
                status_code=409,
                success=False,
                message="Transaction was not added to the mempool",
                error_code="MEMPOOL_REJECTED",
                data={"transaction": tx.to_dict(), "analysis": report.to_dict()},
            )

        tx_status = "FLAGGED" if report.flagged_for_review else "PENDING"
        self.metadata_repository.index_transaction(
            tx,
            tx_status=tx_status,
            is_flagged=report.flagged_for_review,
            ml_score=float(report.anomaly_result.anomaly_score) if report.anomaly_result else None,
            ml_reason=report.anomaly_result.explanation if report.anomaly_result else None,
        )

        alert_event_payload = None
        if report.is_suspicious:
            alert_id = self.metadata_repository.save_alert(report)
            alert_event_payload = {
                "alert_id": alert_id,
                "transaction_id": tx.transaction_id,
                "status": report.overall_status,
                "explanation": report.anomaly_result.explanation if report.anomaly_result else None,
                "score": float(report.anomaly_result.anomaly_score) if report.anomaly_result else None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        return TransactionCreateResult(
            status_code=201,
            success=True,
            message="Transaction created successfully",
            data={"transaction": tx.to_dict(), "analysis": report.to_dict()},
            alert_event_payload=alert_event_payload,
        )

