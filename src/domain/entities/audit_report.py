"""Audit report entity for transaction analysis outcomes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.domain.ml.anomaly_detector import AnomalyResult


@dataclass
class AuditReport:
    transaction_id: str
    blockchain_valid: bool
    signature_valid: bool
    anomaly_result: Optional[AnomalyResult]
    block_index: Optional[int]
    merkle_proof_valid: bool
    flagged_for_review: bool = False
    added_to_mempool: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_suspicious(self) -> bool:
        return self.flagged_for_review or not self.signature_valid

    @property
    def overall_status(self) -> str:
        if not self.signature_valid:
            return "SIGNATURE_INVALID"
        if not self.added_to_mempool and self.block_index is None:
            return "MEMPOOL_REJECTED"
        if not self.blockchain_valid:
            return "BLOCKCHAIN_INVALID"
        if not self.merkle_proof_valid:
            return "MERKLE_INVALID"
        if self.flagged_for_review:
            return "ANOMALY_DETECTED"
        return "VALID"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "blockchain_valid": bool(self.blockchain_valid),
            "signature_valid": bool(self.signature_valid),
            "merkle_proof_valid": bool(self.merkle_proof_valid),
            "block_index": self.block_index,
            "overall_status": self.overall_status,
            "is_suspicious": bool(self.is_suspicious),
            "flagged_for_review": bool(self.flagged_for_review),
            "added_to_mempool": bool(self.added_to_mempool),
            "anomaly_result": self.anomaly_result.to_dict() if self.anomaly_result else None,
            "timestamp": self.timestamp,
        }
