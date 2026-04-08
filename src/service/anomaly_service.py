"""Anomaly detection use-cases and alert workflows."""

from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

from src.repository.analyzer_repository import AnalyzerRepository
from src.repository.blockchain_repository import BlockchainRepository
from src.repository.metadata_repository import MetadataRepository
from src.repository.model_repository import ModelRepository
from src.repository.wallet_repository import WalletRepository
from src.service.exceptions import ServiceError

logger = logging.getLogger("blockchain_audit")

ALLOWED_TRAINING_MODES = {"blockchain", "synthetic"}


def _pagination(page: int, per_page: int, total: int) -> dict:
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": max(1, (total + per_page - 1) // per_page),
        "has_next": page * per_page < total,
        "has_prev": page > 1,
    }


class AnomalyService:
    def __init__(
        self,
        analyzer_repository: AnalyzerRepository,
        blockchain_repository: BlockchainRepository,
        metadata_repository: MetadataRepository,
        wallet_repository: WalletRepository,
        model_repository: ModelRepository,
    ):
        self.analyzer_repository = analyzer_repository
        self.blockchain_repository = blockchain_repository
        self.metadata_repository = metadata_repository
        self.wallet_repository = wallet_repository
        self.model_repository = model_repository

    def train_detector(self, role: str, payload: Dict[str, Any], model_path: str) -> Tuple[dict, str]:
        if role not in ("admin", "operator"):
            raise ServiceError("Access forbidden. Required: admin, operator", status_code=403, error_code="FORBIDDEN")

        mode = str(payload.get("mode") or ("synthetic" if payload.get("use_synthetic") else "blockchain")).lower()
        if mode not in ALLOWED_TRAINING_MODES:
            raise ServiceError("Invalid training mode. Use 'blockchain' or 'synthetic'.", status_code=400, error_code="INVALID_MODE")

        try:
            if mode == "synthetic":
                from src.utils.training_data_generator import TrainingDataGenerator

                sample_count = max(100, min(int(payload.get("sample_count", 800)), 5000))
                logger.info("Training detector with %s synthetic normal sample(s)", sample_count)
                generator = TrainingDataGenerator(num_users=20)
                transactions = generator.generate_only_normal(count=sample_count)
                self.analyzer_repository.detector.fit(transactions)
                message = f"Detector trained with {len(transactions)} synthetic normal samples"
            else:
                all_transactions = self.blockchain_repository.get_all_transactions()
                clean_transactions = self.analyzer_repository.get_clean_training_transactions(all_transactions)
                min_samples = self.analyzer_repository.min_training_samples
                if len(clean_transactions) < min_samples:
                    raise ServiceError(
                        f"At least {min_samples} clean transactions required (have {len(clean_transactions)} clean out of {len(all_transactions)} total)",
                        status_code=400,
                        error_code="INSUFFICIENT_DATA",
                    )
                self.analyzer_repository.train_detector(all_transactions)
                transactions = clean_transactions
                message = f"Detector trained with {len(clean_transactions)} clean blockchain transactions"

            self.model_repository.save_detector(self.analyzer_repository.detector, model_path)
            logger.info("ML model saved to %s", model_path)
            return {
                "training_mode": mode,
                "training_samples": len(transactions),
                "stats": self.analyzer_repository.detector.training_stats,
                "model_saved": model_path,
                "detector_fitted": self.analyzer_repository.detector.is_fitted,
            }, message
        except ServiceError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error training detector")
            raise ServiceError(f"Training error: {exc}", status_code=500, error_code="TRAINING_ERROR") from exc

    def get_anomaly_stats(self) -> dict:
        analyzer_stats = self.analyzer_repository.get_statistics()
        db_alert_stats = self.metadata_repository.get_alert_stats()
        return {**analyzer_stats, "persistent_alerts": db_alert_stats}

    def get_alerts(self, page: int, per_page: int, severity: str = None, resolved_param: str = None) -> Tuple[dict, dict]:
        is_resolved = None
        if resolved_param is not None:
            is_resolved = resolved_param.lower() in ("true", "1", "yes")

        alerts, total = self.metadata_repository.get_alerts(
            page=page,
            per_page=per_page,
            severity=severity,
            is_resolved=is_resolved,
        )
        return {"alerts": alerts, "count": len(alerts)}, _pagination(page, per_page, total)

    def resolve_alert(self, role: str, alert_id: int, resolved_by: str) -> None:
        if role not in ("admin", "operator"):
            raise ServiceError("Access forbidden. Required: admin, operator", status_code=403, error_code="FORBIDDEN")

        if not self.metadata_repository.resolve_alert(alert_id, resolved_by):
            raise ServiceError(f"Alert #{alert_id} not found or already resolved", status_code=404, error_code="ALERT_NOT_FOUND")

    def generate_demo_data(self, generated_by: str, payload: Dict[str, Any]) -> Tuple[dict, str]:
        count = max(1, min(int(payload.get("count", 50)), 500))
        include_anomalies = bool(payload.get("include_anomalies", True))
        anomaly_ratio = float(payload.get("anomaly_ratio", 0.10 if include_anomalies else 0.0))

        from src.utils.data_generator import DataGenerator

        generator = DataGenerator(self.wallet_repository.raw)
        transactions = generator.generate_normal_transactions(count)
        labels = ["normal"] * len(transactions)

        if include_anomalies:
            anomaly_count = max(1, min(count // 2, int(round(count * anomaly_ratio))))
            anomaly_transactions = generator.generate_anomalies(anomaly_count)
            transactions.extend(anomaly_transactions)
            labels.extend(["anomaly"] * len(anomaly_transactions))

        combined = sorted(zip(transactions, labels), key=lambda item: item[0].timestamp)

        anomalies_detected = 0
        flagged_count = 0
        invalid_signature_count = 0

        for tx, _label in combined:
            report = self.analyzer_repository.add_transaction(tx)
            status = "REJECTED"
            if report.signature_valid:
                status = "FLAGGED" if report.flagged_for_review else "PENDING"
            self.metadata_repository.index_transaction(
                tx,
                block_index=None,
                tx_status=status,
                is_flagged=report.flagged_for_review,
                ml_score=float(report.anomaly_result.anomaly_score) if report.anomaly_result else None,
                ml_reason=report.anomaly_result.explanation if report.anomaly_result else None,
            )

            if report.is_suspicious:
                anomalies_detected += 1
                if report.flagged_for_review:
                    flagged_count += 1
                if not report.signature_valid:
                    invalid_signature_count += 1
                self.metadata_repository.save_alert(report)

        logger.info(
            "Demo data generated by %s: %s transaction(s), %s suspicious, %s flagged, %s invalid-signature",
            generated_by,
            len(combined),
            anomalies_detected,
            flagged_count,
            invalid_signature_count,
        )

        data = {
            "generated": len(combined),
            "anomalies_detected": anomalies_detected,
            "flagged": flagged_count,
            "invalid_signatures": invalid_signature_count,
        }
        return data, f"{len(combined)} transactions generated ({flagged_count} flagged for review)"


