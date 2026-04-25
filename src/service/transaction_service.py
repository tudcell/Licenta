"""Transaction use-cases orchestrating wallet management, analysis, and metadata indexing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.infrastructure.metadata_store import MetadataStore
from src.domain.entities.transaction import TransactionType
from src.domain.entities.wallet import WalletManager
from src.service.exceptions import ServiceError
from src.service.transaction_analyzer import TransactionAnalyzer
from src.utils.pagination import build_pagination_metadata


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
        wallet_manager: WalletManager,
        metadata_store: MetadataStore,
        analyzer: TransactionAnalyzer,
    ):
        self.wallet_manager = wallet_manager
        self.metadata_store = metadata_store
        self.analyzer = analyzer

    def _resolve_transaction_wallet(self, requested_wallet_name: str, username: str):
        wallet = self.wallet_manager.get_wallet(requested_wallet_name)
        if wallet is None:
            return self.wallet_manager.create_wallet(requested_wallet_name, metadata={"owner": username})
        return wallet

    @staticmethod
    def _analysis_score(report) -> Optional[float]:
        if not report.anomaly_result:
            return None
        return float(report.anomaly_result.anomaly_score)

    @staticmethod
    def _analysis_reason(report) -> Optional[str]:
        if not report.anomaly_result:
            return None
        return report.anomaly_result.explanation

    def _index_transaction(
        self,
        tx,
        report,
        tx_status: str,
        is_flagged: bool,
    ) -> None:
        self.metadata_store.index_transaction(
            tx,
            tx_status=tx_status,
            is_flagged=is_flagged,
            ml_score=self._analysis_score(report),
            ml_reason=self._analysis_reason(report),
        )

    @staticmethod
    def _build_alert_event_payload(tx, report, alert_id: int) -> dict:
        return {
            "alert_id": alert_id,
            "transaction_id": tx.transaction_id,
            "status": report.overall_status,
            "explanation": report.anomaly_result.explanation if report.anomaly_result else None,
            "score": float(report.anomaly_result.anomaly_score) if report.anomaly_result else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def create_transaction(
        self,
        username: str,
        user_role: str,
        transaction_type: TransactionType,
        transaction_data: Dict[str, Any],
        wallet_name: Optional[str],
        metadata: Optional[Dict[str, Any]],
    ) -> TransactionCreateResult:
        user = self.metadata_store.get_user(username)
        if not user:
            raise ServiceError("Authenticated user not found", status_code=401, error_code="AUTH_FAILED")

        requested_wallet_name = wallet_name or user.get("wallet_name") or username
        if user.get("wallet_name") and requested_wallet_name != user["wallet_name"] and user_role != "admin":
            raise ServiceError(
                "Wallet does not belong to the authenticated user",
                status_code=403,
                error_code="WALLET_FORBIDDEN",
            )

        wallet = self._resolve_transaction_wallet(requested_wallet_name, username)

        if not user.get("wallet_name"):
            self.metadata_store.assign_wallet_to_user(username, requested_wallet_name)

        tx_metadata: Dict[str, Any] = dict(metadata or {})
        tx_metadata.setdefault("submitted_by", username)
        tx_metadata.setdefault("flagged", False)

        tx = wallet.create_and_sign_transaction(
            transaction_type=transaction_type,
            data=transaction_data,
            metadata=tx_metadata,
        )

        report = self.analyzer.add_transaction(tx)

        if not report.signature_valid:
            self._index_transaction(tx, report, tx_status="REJECTED", is_flagged=True)
            self.metadata_store.save_alert(report)
            return TransactionCreateResult(
                status_code=400,
                success=False,
                message="Transaction signature is invalid",
                error_code="INVALID_SIGNATURE",
                data={"transaction": tx.to_dict(), "analysis": report.to_dict()},
            )

        if not report.added_to_mempool:
            self._index_transaction(tx, report, tx_status="REJECTED", is_flagged=report.is_suspicious)
            if report.is_suspicious:
                self.metadata_store.save_alert(report)

            return TransactionCreateResult(
                status_code=409,
                success=False,
                message="Transaction was not added to the mempool",
                error_code="MEMPOOL_REJECTED",
                data={"transaction": tx.to_dict(), "analysis": report.to_dict()},
            )

        tx_status = "FLAGGED" if report.flagged_for_review else "PENDING"
        self._index_transaction(tx, report, tx_status=tx_status, is_flagged=report.flagged_for_review)

        alert_event_payload = None
        if report.is_suspicious:
            alert_id = self.metadata_store.save_alert(report)
            alert_event_payload = self._build_alert_event_payload(tx, report, alert_id)

        return TransactionCreateResult(
            status_code=201,
            success=True,
            message="Transaction created successfully",
            data={"transaction": tx.to_dict(), "analysis": report.to_dict()},
            alert_event_payload=alert_event_payload,
        )

    def list_indexed_transactions(
        self,
        page: int,
        per_page: int,
        sender: Optional[str] = None,
        tx_type: Optional[str] = None,
        tx_status: Optional[str] = None,
        flagged: Optional[bool] = None,
    ) -> tuple[dict, dict]:
        indexed_txs, total = self.metadata_store.search_transactions(
            sender=sender,
            tx_type=tx_type,
            status=tx_status,
            flagged=flagged,
            page=page,
            per_page=per_page,
        )
        pagination = build_pagination_metadata(page, per_page, total)
        return {"transactions": indexed_txs, "count": len(indexed_txs)}, pagination

    def get_transaction_details(self, transaction_id: str) -> Optional[dict]:
        proof = self.analyzer.blockchain.verify_transaction_proof(transaction_id)
        index_record = self.metadata_store.get_transaction_index(transaction_id)
        if proof:
            payload = dict(proof)
            if index_record:
                payload["index_record"] = index_record
            return payload
        if index_record:
            return {"index_record": index_record}
        return None

    def analyze_transaction(self, transaction_id: str):
        return self.analyzer.analyze_transaction(transaction_id)
