"""
Complete blockchain transaction analysis module.
Combines blockchain with anomaly detection for complete audit.

Transactions detected as anomalies are flagged for review, but valid
signed transactions still enter the mempool/blockchain.
"""

import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field

from src.domain.blockchain import Blockchain, BlockchainConfig
from src.domain.transaction import Transaction, TransactionType
from src.domain.ml.anomaly_detector import AnomalyDetector, AnomalyResult


@dataclass
class AuditReport:
    """
    Audit report for a transaction or set of transactions.
    """
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
    def quarantined(self) -> bool:
        return False

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
            'transaction_id': self.transaction_id,
            'blockchain_valid': bool(self.blockchain_valid),
            'signature_valid': bool(self.signature_valid),
            'merkle_proof_valid': bool(self.merkle_proof_valid),
            'block_index': self.block_index,
            'overall_status': self.overall_status,
            'is_suspicious': bool(self.is_suspicious),
            'flagged_for_review': bool(self.flagged_for_review),
            'added_to_mempool': bool(self.added_to_mempool),
            'quarantined': False,
            'anomaly_result': self.anomaly_result.to_dict() if self.anomaly_result else None,
            'timestamp': self.timestamp
        }


class TransactionAnalyzer:
    """
    Complete analyzer for blockchain transactions.

    Provides:
    - Cryptographic validation (signatures, Merkle proofs)
    - Anomaly detection with Isolation Forest
    - Complete audit reports
    - Real-time alerting
    """

    def __init__(
        self,
        blockchain: Blockchain = None,
        detector: AnomalyDetector = None,
        auto_train: bool = False,
        min_training_samples: int = 100
    ):
        self.blockchain = blockchain or Blockchain(BlockchainConfig(auto_save=False))
        self.detector = detector or AnomalyDetector()
        self.auto_train = auto_train
        self.min_training_samples = min_training_samples

        self.alerts: List[AuditReport] = []
        self.analysis_count = 0
        self._historical_transactions: List[Transaction] = []
        self._reports_by_transaction_id: Dict[str, AuditReport] = {}

    def _is_clean_training_candidate(self, transaction: Transaction) -> bool:
        if not transaction.verify_signature():
            return False

        if transaction.metadata.get('anomaly_type'):
            return False

        risk_level = str(transaction.metadata.get('risk_level', 'low')).lower()
        if risk_level in {'high', 'critical'}:
            return False

        if transaction.transaction_type in {
            TransactionType.LOGIN_FAILED,
            TransactionType.ACCESS_DENIED,
            TransactionType.DATA_DELETE
        }:
            return False

        return True

    def _get_clean_training_transactions(
        self,
        transactions: Optional[List[Transaction]] = None
    ) -> List[Transaction]:
        source = transactions if transactions is not None else self._historical_transactions
        return [tx for tx in source if self._is_clean_training_candidate(tx)]

    def add_transaction(self, transaction: Transaction) -> AuditReport:
        """
        Adds a transaction and analyzes it.

        Important:
        - Never mutate the signed transaction before mempool submission.
        - Flagging must live in the report / database layer, not inside signed metadata.
        """
        signature_valid = transaction.verify_signature()
        history_before_current = list(self._historical_transactions)

        if self.auto_train and not self.detector.is_fitted:
            clean_data = self._get_clean_training_transactions(history_before_current)
            if len(clean_data) >= self.min_training_samples:
                self.detector.fit(clean_data)

        anomaly_result = None
        flagged_for_review = False

        if self.detector.is_fitted and signature_valid:
            anomaly_result = self.detector.predict(transaction, history_before_current)
            flagged_for_review = bool(anomaly_result.is_anomaly)

        added_to_mempool = False
        if signature_valid:
            added_to_mempool = self.blockchain.add_transaction(transaction)

        # Keep full history for audit; clean filtering happens during training.
        self._historical_transactions.append(transaction)

        report = AuditReport(
            transaction_id=transaction.transaction_id,
            blockchain_valid=True,
            signature_valid=signature_valid,
            anomaly_result=anomaly_result,
            block_index=None,
            merkle_proof_valid=True,
            flagged_for_review=flagged_for_review,
            added_to_mempool=added_to_mempool
        )

        self.analysis_count += 1

        if report.is_suspicious:
            self.alerts.append(report)

        self._reports_by_transaction_id[transaction.transaction_id] = report

        return report

    def train_detector(self, transactions: List[Transaction] = None):
        """
        Trains the anomaly detector on clean baseline transactions only.
        """
        source = transactions if transactions is not None else self._historical_transactions
        clean_training_data = self._get_clean_training_transactions(source)

        if len(clean_training_data) < self.min_training_samples:
            raise ValueError(
                f"At least {self.min_training_samples} clean transactions are required for training "
                f"(have {len(clean_training_data)} clean out of {len(source)} total)"
            )

        self.detector.fit(clean_training_data)

    def mine_and_analyze(self) -> Optional[Dict[str, Any]]:
        """
        Mines a new block and updates reports with block information.
        """
        new_block = self.blockchain.mine_pending_transactions()
        if not new_block:
            return None

        results: List[AuditReport] = []

        for tx in new_block.transactions:
            merkle_valid = new_block.verify_transaction_inclusion(tx)

            existing_alert = next(
                (a for a in self.alerts if a.transaction_id == tx.transaction_id),
                None
            )

            if existing_alert:
                existing_alert.block_index = new_block.index
                existing_alert.merkle_proof_valid = merkle_valid
                existing_alert.blockchain_valid = True
                existing_alert.added_to_mempool = False
                self._reports_by_transaction_id[tx.transaction_id] = existing_alert
                results.append(existing_alert)
            else:
                mined_report = AuditReport(
                    transaction_id=tx.transaction_id,
                    blockchain_valid=True,
                    signature_valid=tx.verify_signature(),
                    anomaly_result=None,
                    block_index=new_block.index,
                    merkle_proof_valid=merkle_valid,
                    flagged_for_review=False,
                    added_to_mempool=False
                )
                self._reports_by_transaction_id[tx.transaction_id] = mined_report
                results.append(mined_report)

        return {
            'block': new_block.to_dict(),
            'analysis_results': [r.to_dict() for r in results],
            'anomalies_found': sum(1 for r in results if r.is_suspicious)
        }

    def analyze_transaction(self, transaction_id: str) -> Optional[AuditReport]:
        """
        Analyzes an existing transaction in the blockchain.
        """
        cached_report = self._reports_by_transaction_id.get(transaction_id)
        if cached_report:
            return cached_report

        result = self.blockchain.get_transaction(transaction_id)
        if not result:
            return None

        tx, block = result

        signature_valid = tx.verify_signature()
        merkle_valid = block.verify_transaction_inclusion(tx)
        blockchain_valid, _ = self.blockchain.validate_chain()

        anomaly_result = None
        flagged_for_review = False

        if self.detector.is_fitted:
            all_transactions = self.blockchain.get_all_transactions()
            tx_index = next(
                (i for i, t in enumerate(all_transactions) if t.transaction_id == transaction_id),
                -1
            )
            historical = all_transactions[:tx_index] if tx_index > 0 else []
            anomaly_result = self.detector.predict(tx, historical)
            flagged_for_review = bool(anomaly_result.is_anomaly)

        report = AuditReport(
            transaction_id=transaction_id,
            blockchain_valid=blockchain_valid,
            signature_valid=signature_valid,
            anomaly_result=anomaly_result,
            block_index=block.index,
            merkle_proof_valid=merkle_valid,
            flagged_for_review=flagged_for_review,
            added_to_mempool=False
        )
        self._reports_by_transaction_id[transaction_id] = report
        return report

    def get_alerts(
        self,
        limit: int = None,
        severity: str = None
    ) -> List[AuditReport]:
        alerts = self.alerts

        if severity:
            alerts = [a for a in alerts if a.overall_status == severity]

        if limit:
            alerts = alerts[-limit:]

        return alerts

    def get_statistics(self) -> Dict[str, Any]:
        blockchain_stats = self.blockchain.get_statistics()

        anomaly_stats = {}
        detector_trained = bool(self.detector.is_fitted)
        training_stats = self.detector.training_stats if detector_trained else {}

        if self.detector.is_fitted and self.alerts:
            anomaly_results = [a.anomaly_result for a in self.alerts if a.anomaly_result]
            if anomaly_results:
                anomaly_stats = self.detector.get_anomaly_statistics(anomaly_results)

        return {
            'blockchain': blockchain_stats,
            'analysis': {
                'total_analyzed': self.analysis_count,
                'alerts_count': len(self.alerts),
                'blockchain_length': len(self.blockchain.chain),
                'clean_training_candidates': len(self._get_clean_training_transactions()),
                'detector_fitted': detector_trained,
                'detector_trained': detector_trained,
                'training_samples': training_stats.get('n_samples', 0),
                'trained_at': training_stats.get('trained_at')
            },
            'anomaly_detection': anomaly_stats,
        }

    def validate_blockchain_integrity(self) -> Dict[str, Any]:
        is_valid, error = self.blockchain.validate_chain()

        invalid_signatures = []
        for block in self.blockchain:
            for tx in block.transactions:
                if not tx.verify_signature():
                    invalid_signatures.append(tx.transaction_id)

        return {
            'chain_valid': is_valid,
            'error': error,
            'invalid_signatures': invalid_signatures,
            'total_blocks': len(self.blockchain),
            'total_transactions': sum(len(b.transactions) for b in self.blockchain)
        }

    def export_audit_log(self) -> str:
        return json.dumps({
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'statistics': self.get_statistics(),
            'integrity_check': self.validate_blockchain_integrity(),
            'alerts': [a.to_dict() for a in self.alerts],
            'blockchain': {
                'height': self.blockchain.height,
                'blocks': [b.to_dict() for b in self.blockchain]
            }
        }, ensure_ascii=False, indent=2)
