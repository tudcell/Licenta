"""Service for detector training orchestration and clean-set selection."""

from __future__ import annotations

from typing import List, Optional

from src.domain.entities.transaction import Transaction
from src.domain.ml.anomaly_detector import AnomalyDetector
from src.domain.policies.training_data_policy import TrainingDataPolicy


class DetectorTrainingService:
    def __init__(self, detector: AnomalyDetector, min_training_samples: int):
        self.detector = detector
        self.min_training_samples = min_training_samples

    def get_clean_training_transactions(self, transactions: Optional[List[Transaction]] = None) -> List[Transaction]:
        source = transactions or []
        return [tx for tx in source if TrainingDataPolicy.is_clean_candidate(tx)]

    def try_auto_train(self, history_before_current: List[Transaction], auto_train: bool) -> None:
        if auto_train and not self.detector.is_fitted:
            clean_data = self.get_clean_training_transactions(history_before_current)
            if len(clean_data) >= self.min_training_samples:
                self.detector.fit(clean_data)

    def train_detector(self, source: List[Transaction]) -> None:
        clean_training_data = self.get_clean_training_transactions(source)
        if len(clean_training_data) < self.min_training_samples:
            raise ValueError(
                f"At least {self.min_training_samples} clean transactions are required for training "
                f"(have {len(clean_training_data)} clean out of {len(source)} total)"
            )
        self.detector.fit(clean_training_data)

