"""Integrity / audit reporting use-cases (chain validity + export)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from src.domain.authorization import Principal, Role
from src.domain.entities.audit_report import AuditReport
from src.domain.entities.blockchain import Blockchain
from src.domain.ml.anomaly_detector import AnomalyDetector, AnomalyResult
from src.infrastructure.persistence.sqlite import TransactionIndexRepository
from src.service.transaction_audit_service import TransactionAuditService


class IntegrityService:
    def __init__(
            self,
            blockchain: Blockchain,
            audit: TransactionAuditService,
            transactions: TransactionIndexRepository,
    ):
        self._blockchain = blockchain
        self._audit = audit
        self._transactions = transactions

    def check_integrity(self) -> Dict[str, Any]:
        is_valid, error = self._blockchain.validate_chain()
        invalid_signatures: List[str] = []
        total_transactions = 0
        for block in self._blockchain:
            for tx in block.transactions:
                total_transactions += 1
                if not tx.verify_signature():
                    invalid_signatures.append(tx.transaction_id)
        return {
            "chain_valid": is_valid,
            "error": error,
            "invalid_signatures": invalid_signatures,
            "total_blocks": len(self._blockchain),
            "total_transactions": total_transactions,
        }

    def export_audit_log(self, principal: Principal) -> Dict[str, Any]:
        """Build the audit log payload as a plain dict; serialization is the
        controller's job. Single chain traversal collects integrity state,
        per-tx reports, and the chain dump in one pass."""
        principal.require(Role.ADMIN)

        is_valid, error = self._blockchain.validate_chain()
        invalid_signatures: List[str] = []
        total_transactions = 0
        reports: List[AuditReport] = []
        alerts: List[AuditReport] = []
        blocks_dump: List[Dict[str, Any]] = []

        for block in self._blockchain:
            blocks_dump.append(block.to_dict())
            for tx in block.transactions:
                total_transactions += 1
                signature_valid = tx.verify_signature()
                if not signature_valid:
                    invalid_signatures.append(tx.transaction_id)
                    continue
                merkle_valid = block.verify_transaction_inclusion(tx)

                index_entry = self._transactions.get(tx.transaction_id)
                anomaly_result = self._build_cached_anomaly(index_entry)
                flagged_for_review = bool(index_entry.is_flagged) if index_entry else False

                report = AuditReport(
                    transaction_id=tx.transaction_id,
                    blockchain_valid=is_valid,
                    signature_valid=True,
                    anomaly_result=anomaly_result,
                    block_index=block.index,
                    merkle_proof_valid=merkle_valid,
                    flagged_for_review=flagged_for_review,
                    added_to_mempool=False,
                )
                reports.append(report)
                if report.is_suspicious:
                    alerts.append(report)

        statistics = self._audit.statistics_from_reports(reports)
        statistics["analysis"] = {
            **statistics.get("analysis", {}),
            "alerts_count": len(alerts),
        }

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "statistics": statistics,
            "integrity_check": {
                "chain_valid": is_valid,
                "error": error,
                "invalid_signatures": invalid_signatures,
                "total_blocks": len(self._blockchain),
                "total_transactions": total_transactions,
            },
            "alerts": [item.to_dict() for item in alerts],
            "blockchain": {
                "height": self._blockchain.height,
                "blocks": blocks_dump,
            },
        }

    @staticmethod
    def _build_cached_anomaly(index_entry) -> AnomalyResult | None:
        if not index_entry:
            return None
        has_cached_values = index_entry.ml_score is not None or index_entry.ml_reason is not None or index_entry.is_flagged
        if not has_cached_values:
            return None
        score = float(index_entry.ml_score) if index_entry.ml_score is not None else 0.0
        explanation = index_entry.ml_reason or (
            "Flagged by previous analysis" if index_entry.is_flagged else "Historical analysis result"
        )
        return AnomalyResult(
            transaction_id=index_entry.transaction_id,
            is_anomaly=bool(index_entry.is_flagged),
            anomaly_score=score,
            confidence=0.0,
            explanation=explanation,
            model_score=score,
            rule_penalty=0.0,
            threshold=0.0,
            model_is_anomaly=bool(index_entry.is_flagged),
            decision_source="cached",
        )
