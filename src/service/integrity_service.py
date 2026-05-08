"""Integrity / audit reporting use-cases (chain validity + export).

The export endpoint deliberately does NOT re-score transactions with the
live ML model. Re-scoring would (a) be slow on large chains and (b) yield
different numbers from those visible in the dashboard if the model has
been retrained since the alert was raised. Instead we emit, per chain
transaction:
    - Cryptographic state freshly computed from the chain itself
      (signature, merkle proof, block validity).
    - The latest persisted alert for that transaction, if any. This carries
      the values that were *real* at the time of detection (severity,
      confidence, score, explanation).

Fields that are not persisted (per-feature vectors, threshold, hard-rule
flags, etc.) are intentionally omitted from the cached export rather than
defaulted to `0.0` / `null`. The dedicated `/api/transaction/analyze/<id>`
endpoint produces the full live shape if a caller really needs it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.domain.authorization import Principal, Role
from src.domain.entities.blockchain import Blockchain
from src.infrastructure.persistence.sqlite import (
    AlertRepository,
    TransactionIndexRepository,
)
from src.service.transaction_audit_service import TransactionAuditService


class IntegrityService:
    def __init__(
            self,
            blockchain: Blockchain,
            audit: TransactionAuditService,
            transactions: TransactionIndexRepository,
            alerts: AlertRepository,
    ):
        self._blockchain = blockchain
        self._audit = audit
        self._transactions = transactions
        self._alerts = alerts

    # ------------------------------------------------------------------
    # /api/audit/integrity
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # /api/audit/export
    # ------------------------------------------------------------------
    def export_audit_log(self, principal: Principal) -> Dict[str, Any]:
        principal.require(Role.ADMIN)

        is_valid, error = self._blockchain.validate_chain()
        invalid_signatures: List[str] = []

        # Single SQL round-trip for all alerts on the chain
        all_tx_ids = [tx.transaction_id for block in self._blockchain for tx in block.transactions]
        alerts_by_tx = self._alerts.latest_by_transaction_ids(all_tx_ids)

        per_transaction: List[Dict[str, Any]] = []
        suspicious: List[Dict[str, Any]] = []
        blocks_dump: List[Dict[str, Any]] = []
        total_transactions = 0

        for block in self._blockchain:
            blocks_dump.append(block.to_dict())
            for tx in block.transactions:
                total_transactions += 1
                signature_valid = tx.verify_signature()
                if not signature_valid:
                    invalid_signatures.append(tx.transaction_id)

                merkle_valid = block.verify_transaction_inclusion(tx)
                index_entry = self._transactions.get(tx.transaction_id)
                alert_row = alerts_by_tx.get(tx.transaction_id)

                entry = self._build_export_entry(
                    tx=tx,
                    block=block,
                    chain_valid=is_valid,
                    signature_valid=signature_valid,
                    merkle_valid=merkle_valid,
                    index_entry=index_entry,
                    alert_row=alert_row,
                )
                per_transaction.append(entry)
                if entry["is_suspicious"]:
                    suspicious.append(entry)

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "integrity_check": {
                "chain_valid": is_valid,
                "error": error,
                "invalid_signatures": invalid_signatures,
                "total_blocks": len(self._blockchain),
                "total_transactions": total_transactions,
            },
            "alerts_summary": {
                "total": len(suspicious),
                "by_severity": _count_by_severity(suspicious),
                "by_status": _count_by_status(suspicious),
            },
            "transactions": per_transaction,
            "alerts": suspicious,
            "blockchain": {
                "height": self._blockchain.height,
                "blocks": blocks_dump,
            },
        }

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    @staticmethod
    def _build_export_entry(
            *,
            tx,
            block,
            chain_valid: bool,
            signature_valid: bool,
            merkle_valid: bool,
            index_entry,
            alert_row: Optional[dict],
    ) -> Dict[str, Any]:
        is_flagged = bool(index_entry.is_flagged) if index_entry else False
        tx_status = index_entry.tx_status if index_entry else "MINED"

        # Compute the same overall_status the live AuditReport would, but
        # only from values we actually know post-mining.
        if not signature_valid:
            overall_status = "SIGNATURE_INVALID"
        elif not chain_valid:
            overall_status = "BLOCKCHAIN_INVALID"
        elif not merkle_valid:
            overall_status = "MERKLE_INVALID"
        elif is_flagged:
            overall_status = "ANOMALY_DETECTED"
        else:
            overall_status = "VALID"

        is_suspicious = is_flagged or not signature_valid

        entry: Dict[str, Any] = {
            "transaction_id": tx.transaction_id,
            "block_index": block.index,
            "tx_status": tx_status,
            "blockchain_valid": bool(chain_valid),
            "signature_valid": bool(signature_valid),
            "merkle_proof_valid": bool(merkle_valid),
            "is_flagged": is_flagged,
            "is_suspicious": is_suspicious,
            "overall_status": overall_status,
            "timestamp": tx.timestamp,
        }

        anomaly = _build_anomaly_section(index_entry, alert_row)
        if anomaly is not None:
            entry["anomaly"] = anomaly

        return entry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _build_anomaly_section(index_entry, alert_row: Optional[dict]) -> Optional[Dict[str, Any]]:
    """Emit an `anomaly` block only when there's something real to say.

    Sources, in order of trust:
        1. The persisted alert row (richest: severity, confidence, alert_id).
        2. The transaction_index entry (ml_score + ml_reason cached at scoring time).

    If neither has anything, the export omits the field rather than
    emitting `null`-padded placeholders.
    """
    has_index_signal = index_entry is not None and (
            index_entry.ml_score is not None
            or index_entry.ml_reason is not None
            or index_entry.is_flagged
    )
    if alert_row is None and not has_index_signal:
        return None

    anomaly: Dict[str, Any] = {"source": "indexed"}

    if alert_row is not None:
        anomaly["source"] = "alert_record"
        anomaly["alert_id"] = alert_row.get("id")
        anomaly["alert_type"] = alert_row.get("alert_type")
        anomaly["severity"] = alert_row.get("severity")
        if alert_row.get("anomaly_score") is not None:
            anomaly["anomaly_score"] = float(alert_row["anomaly_score"])
        if alert_row.get("confidence") is not None:
            anomaly["confidence"] = float(alert_row["confidence"])
        if alert_row.get("explanation"):
            anomaly["explanation"] = alert_row["explanation"]
        anomaly["created_at"] = alert_row.get("created_at")
        anomaly["is_resolved"] = bool(alert_row.get("is_resolved"))
        if alert_row.get("resolved_at"):
            anomaly["resolved_at"] = alert_row["resolved_at"]
        if alert_row.get("resolved_by"):
            anomaly["resolved_by"] = alert_row["resolved_by"]
    elif index_entry is not None:
        # No alert row but the index says we scored this. Keep it minimal.
        if index_entry.ml_score is not None:
            anomaly["anomaly_score"] = float(index_entry.ml_score)
        if index_entry.ml_reason:
            anomaly["explanation"] = index_entry.ml_reason

    return anomaly


def _count_by_severity(entries: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in entries:
        severity = (entry.get("anomaly") or {}).get("severity", "unknown")
        counts[severity] = counts.get(severity, 0) + 1
    return counts


def _count_by_status(entries: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in entries:
        status = entry.get("overall_status", "UNKNOWN")
        counts[status] = counts.get(status, 0) + 1
    return counts
