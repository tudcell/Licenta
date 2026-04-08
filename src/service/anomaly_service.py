"""Anomaly and alert service use-cases."""

from __future__ import annotations

from typing import Any, Dict

from src.repository import BlockchainRepository, MetadataRepository, ModelRepository, WalletRepository


class AnomalyService:
    def __init__(self, blockchain_repository: BlockchainRepository, wallet_repository: WalletRepository, metadata_repository: MetadataRepository, model_repository: ModelRepository, analyzer):
        self.blockchain_repository = blockchain_repository
        self.wallet_repository = wallet_repository
        self.metadata_repository = metadata_repository
        self.model_repository = model_repository
        self.analyzer = analyzer

    def train_detector(self, mode: str, sample_count: int = 800):
        if mode == 'synthetic':
            from src.utils.training_data_generator import TrainingDataGenerator
            count = max(100, min(int(sample_count), 5000))
            generator = TrainingDataGenerator(num_users=20)
            transactions = generator.generate_only_normal(count=count)
            self.analyzer.detector.fit(transactions)
            training_samples = len(transactions)
            message = f"Detector trained with {training_samples} synthetic normal samples"
        else:
            all_transactions = self.blockchain_repository.get_all_transactions()
            clean_transactions = self.analyzer._get_clean_training_transactions(all_transactions)
            min_samples = self.analyzer.min_training_samples
            if len(clean_transactions) < min_samples:
                raise ValueError(
                    f"At least {min_samples} clean transactions required (have {len(clean_transactions)} clean out of {len(all_transactions)} total)"
                )
            self.analyzer.train_detector(all_transactions)
            training_samples = len(clean_transactions)
            message = f"Detector trained with {training_samples} clean blockchain transactions"

        model_path = self.model_repository.save_detector(self.analyzer.detector)
        return {
            'training_mode': mode,
            'training_samples': training_samples,
            'stats': self.analyzer.detector.training_stats,
            'model_saved': model_path,
            'detector_fitted': self.analyzer.detector.is_fitted,
            'message': message,
        }

    def get_anomaly_stats(self):
        analyzer_stats = self.analyzer.get_statistics()
        db_alert_stats = self.metadata_repository.get_alert_stats()
        return {**analyzer_stats, 'persistent_alerts': db_alert_stats}

    def get_alerts(self, page=1, per_page=20, severity=None, is_resolved=None):
        return self.metadata_repository.get_alerts(page=page, per_page=per_page, severity=severity, is_resolved=is_resolved)

    def resolve_alert(self, alert_id: int, resolved_by: str) -> bool:
        return self.metadata_repository.resolve_alert(alert_id, resolved_by)

    def generate_demo_data(self, count: int, include_anomalies: bool, anomaly_ratio: float):
        from src.utils.data_generator import DataGenerator

        generator = DataGenerator(self.wallet_repository.wallet_manager)
        transactions = generator.generate_normal_transactions(count)
        labels = ['normal'] * len(transactions)

        if include_anomalies:
            anomaly_count = max(1, min(count // 2, int(round(count * anomaly_ratio))))
            anomaly_transactions = generator.generate_anomalies(anomaly_count)
            transactions.extend(anomaly_transactions)
            labels.extend(['anomaly'] * len(anomaly_transactions))

        combined = sorted(zip(transactions, labels), key=lambda item: item[0].timestamp)

        anomalies_detected = 0
        flagged_count = 0
        invalid_signature_count = 0

        for tx, _ in combined:
            report = self.analyzer.add_transaction(tx)
            status = 'REJECTED'
            if report.signature_valid:
                status = 'FLAGGED' if report.flagged_for_review else 'PENDING'
            self.metadata_repository.index_transaction(
                tx,
                block_index=None,
                tx_status=status,
                is_flagged=report.flagged_for_review,
            )

            if report.is_suspicious:
                anomalies_detected += 1
                if report.flagged_for_review:
                    flagged_count += 1
                if not report.signature_valid:
                    invalid_signature_count += 1
                self.metadata_repository.save_alert(report)

        return {
            'generated': len(combined),
            'anomalies_detected': anomalies_detected,
            'flagged': flagged_count,
            'invalid_signatures': invalid_signature_count,
        }
