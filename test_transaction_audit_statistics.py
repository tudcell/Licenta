from types import SimpleNamespace

from src.domain.entities.audit_report import AuditReport
from src.domain.ml.anomaly_detector import AnomalyResult
from src.repository.analysis_state_repository import AnalysisStateRepository
from src.service.transaction_audit_service import TransactionAuditService


class _StubDetector:
    def __init__(self):
        self.is_fitted = True
        self.training_stats = {}
        self.last_results = None

    def get_anomaly_statistics(self, results):
        self.last_results = results
        anomalies = [item for item in results if item.is_anomaly]
        return {
            "total_transactions": len(results),
            "anomalies_count": len(anomalies),
            "normal_count": len(results) - len(anomalies),
            "anomaly_rate": len(anomalies) / len(results),
        }


class _RehydrationDetector:
    def __init__(self):
        self.is_fitted = True
        self.training_stats = {}

    def predict(self, tx, history):
        is_anomaly = tx.transaction_id.endswith("1")
        return _mk_result(tx.transaction_id, is_anomaly)

    def get_anomaly_statistics(self, results):
        anomalies = [item for item in results if item.is_anomaly]
        return {
            "total_transactions": len(results),
            "anomalies_count": len(anomalies),
            "normal_count": len(results) - len(anomalies),
            "anomaly_rate": len(anomalies) / len(results),
        }


class _Tx:
    def __init__(self, tx_id: str):
        self.transaction_id = tx_id

    def verify_signature(self):
        return True


class _Block:
    def __init__(self, index: int, transactions):
        self.index = index
        self.transactions = transactions

    def verify_transaction_inclusion(self, _tx):
        return True


class _BlockchainStub:
    def __init__(self, chain):
        self.chain = chain

    def __iter__(self):
        return iter(self.chain)

    def get_all_transactions(self):
        return [tx for block in self.chain for tx in block.transactions]

    @staticmethod
    def get_statistics():
        return {"total_transactions": 2}

    @staticmethod
    def validate_chain():
        return True, None


def _mk_result(transaction_id: str, is_anomaly: bool) -> AnomalyResult:
    return AnomalyResult(
        transaction_id=transaction_id,
        is_anomaly=is_anomaly,
        anomaly_score=-0.5,
        model_score=-0.4,
        rule_penalty=0.1,
        threshold=-0.6,
        model_is_anomaly=is_anomaly,
        hard_rule_triggered=False,
        hard_rule_reason=None,
        decision_source="model",
        confidence=0.5,
        features=None,
        explanation="",
    )


def test_statistics_use_all_reports_not_only_alerts():
    detector = _StubDetector()
    state = AnalysisStateRepository()

    report_anomaly = AuditReport(
        transaction_id="tx-anom",
        blockchain_valid=True,
        signature_valid=True,
        anomaly_result=_mk_result("tx-anom", True),
        block_index=1,
        merkle_proof_valid=True,
        flagged_for_review=True,
        added_to_mempool=True,
    )
    report_normal = AuditReport(
        transaction_id="tx-normal",
        blockchain_valid=True,
        signature_valid=True,
        anomaly_result=_mk_result("tx-normal", False),
        block_index=1,
        merkle_proof_valid=True,
        flagged_for_review=False,
        added_to_mempool=True,
    )

    state.cache_report(report_anomaly)
    state.save_report(report_normal)

    service = TransactionAuditService(
        blockchain=SimpleNamespace(get_statistics=lambda: {}, chain=[]),
        detector=detector,
        state=state,
        training_service=SimpleNamespace(get_clean_training_transactions=lambda txs: []),
    )

    response = service.get_statistics()
    stats = response["anomaly_detection"]

    assert detector.last_results is not None
    assert len(detector.last_results) == 2
    assert stats["total_transactions"] == 2
    assert stats["anomalies_count"] == 1
    assert stats["normal_count"] == 1
    assert stats["anomaly_rate"] == 0.5


def test_statistics_rehydrate_state_after_restart_when_chain_exists():
    detector = _RehydrationDetector()
    state = AnalysisStateRepository()
    chain_transactions = [_Tx("tx-1"), _Tx("tx-2")]
    blockchain = _BlockchainStub([_Block(1, chain_transactions)])

    service = TransactionAuditService(
        blockchain=blockchain,
        detector=detector,
        state=state,
        training_service=SimpleNamespace(get_clean_training_transactions=lambda txs: txs),
    )

    response = service.get_statistics()
    anomaly_stats = response["anomaly_detection"]
    analysis_stats = response["analysis"]

    assert anomaly_stats["total_transactions"] == 2
    assert anomaly_stats["anomalies_count"] == 1
    assert analysis_stats["total_analyzed"] == 2
    assert analysis_stats["alerts_count"] == 1
