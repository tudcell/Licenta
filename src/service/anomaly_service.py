"""Anomaly detection use-cases: training, retraining, alerts."""

from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

from src.domain.authorization import Principal, Role
from src.domain.entities.blockchain import Blockchain
from src.domain.errors import InternalError, NotFoundError, ValidationError
from src.domain.ml.anomaly_detector import AnomalyDetector
from src.infrastructure.persistence import PickleModelStore
from src.infrastructure.persistence.sqlite import AlertRepository, TransactionIndexRepository
from src.service.detector_training_service import DetectorTrainingService
from src.service.transaction_audit_service import TransactionAuditService
from src.utils.pagination import build_pagination_metadata
from src.utils.training_data_generator import TrainingDataGenerator

logger = logging.getLogger("blockchain_audit")

ALLOWED_TRAINING_MODES = {"blockchain", "synthetic"}
RETRAIN_WINDOW_SIZE = 2000


class AnomalyService:
    def __init__(
            self,
            detector: AnomalyDetector,
            training: DetectorTrainingService,
            audit: TransactionAuditService,
            blockchain: Blockchain,
            alerts: AlertRepository,
            transactions: TransactionIndexRepository,
            model_store: PickleModelStore,
    ):
        self._detector = detector
        self._training = training
        self._audit = audit
        self._blockchain = blockchain
        self._alerts = alerts
        self._transactions = transactions
        self._model_store = model_store

    @staticmethod
    def _resolve_training_mode(payload: Dict[str, Any]) -> str:
        mode = str(payload.get("mode") or ("synthetic" if payload.get("use_synthetic") else "blockchain")).lower()
        if mode not in ALLOWED_TRAINING_MODES:
            raise ValidationError("Invalid training mode. Use 'blockchain' or 'synthetic'.", error_code="INVALID_MODE")
        return mode

    def train_detector(self, principal: Principal, payload: Dict[str, Any]) -> Tuple[dict, str]:
        principal.require(Role.ADMIN, Role.OPERATOR)
        mode = self._resolve_training_mode(payload)

        try:
            if mode == "synthetic":
                sample_count = max(100, min(int(payload.get("sample_count", 800)), 5000))
                logger.info("Training detector with %s synthetic normal sample(s)", sample_count)
                generator = TrainingDataGenerator(num_users=20)
                transactions = generator.generate_only_normal(count=sample_count)
                self._detector.fit(transactions)
                message = f"Detector trained with {len(transactions)} synthetic normal samples"
            else:
                all_transactions = self._blockchain.get_all_transactions()
                clean_transactions = self._training.get_clean_training_transactions(all_transactions)
                min_samples = self._training.min_training_samples
                if len(clean_transactions) < min_samples:
                    raise ValidationError(
                        f"At least {min_samples} clean transactions required (have {len(clean_transactions)} clean out of {len(all_transactions)} total)",
                        error_code="INSUFFICIENT_DATA",
                    )
                self._training.train_detector(all_transactions)
                transactions = clean_transactions
                message = f"Detector trained with {len(clean_transactions)} clean blockchain transactions"

            self._model_store.save(self._detector)
            return {
                "training_mode": mode,
                "training_samples": len(transactions),
                "stats": self._detector.training_stats,
                "model_saved": self._model_store.filepath,
                "detector_fitted": self._detector.is_fitted,
            }, message
        except ValidationError:
            raise
        except Exception as exc:
            logger.exception("Error training detector")
            raise InternalError(f"Training error: {exc}", error_code="TRAINING_ERROR") from exc

    def get_anomaly_stats(self) -> dict:
        analyzer_stats = self._audit.get_statistics()
        return {**analyzer_stats, "persistent_alerts": self._alerts.stats()}

    def get_alerts(self, page: int, per_page: int, severity: str = None, resolved_param: str = None) -> Tuple[
        dict, dict]:
        is_resolved = self._parse_resolved_filter(resolved_param)
        alerts, total = self._alerts.list(
            page=page,
            per_page=per_page,
            severity=severity,
            is_resolved=is_resolved,
        )
        return {"alerts": alerts, "count": len(alerts)}, build_pagination_metadata(page, per_page, total)

    def resolve_alert(self, principal: Principal, alert_id: int) -> None:
        principal.require(Role.ADMIN, Role.OPERATOR)
        if not self._alerts.resolve(alert_id, principal.username):
            raise NotFoundError(f"Alert #{alert_id} not found or already resolved", error_code="ALERT_NOT_FOUND")

    def retrain_detector(self, principal: Principal) -> Tuple[dict, str]:
        principal.require(Role.ADMIN, Role.OPERATOR)

        entries, _ = self._transactions.search(
            flagged=False,
            page=1,
            per_page=RETRAIN_WINDOW_SIZE,
        )

        chain_transactions = self._blockchain.get_all_transactions()
        mempool_transactions = self._blockchain.get_mempool_transactions()
        tx_by_id = {tx.transaction_id: tx for tx in chain_transactions}
        tx_by_id.update({tx.transaction_id: tx for tx in mempool_transactions})

        ordered_transactions = []
        for entry in entries:
            tx = tx_by_id.get(entry.transaction_id)
            if tx:
                ordered_transactions.append(tx)

        clean_transactions = self._training.get_clean_training_transactions(ordered_transactions)
        min_samples = self._training.min_training_samples
        if len(clean_transactions) < min_samples:
            raise ValidationError(
                f"At least {min_samples} clean transactions required for retraining (have {len(clean_transactions)})",
                error_code="INSUFFICIENT_DATA",
            )

        self._detector.fit(clean_transactions)
        self._model_store.save(self._detector)

        return {
            "training_mode": "sliding_window_retrain",
            "window_size": RETRAIN_WINDOW_SIZE,
            "indexed_non_flagged": len(entries),
            "matched_transactions": len(ordered_transactions),
            "training_samples": len(clean_transactions),
            "stats": self._detector.training_stats,
            "model_saved": self._model_store.filepath,
            "detector_fitted": self._detector.is_fitted,
        }, f"Detector retrained with {len(clean_transactions)} clean recent transactions"

    @staticmethod
    def _parse_resolved_filter(resolved_param: str | None) -> bool | None:
        if resolved_param is None:
            return None
        return resolved_param.lower() in ("true", "1", "yes")
