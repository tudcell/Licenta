"""Repository adapter for ML model persistence."""

from __future__ import annotations

from src.domain.ml.anomaly_detector import AnomalyDetector


class ModelRepository:
    def save_detector(self, detector: AnomalyDetector, model_path: str) -> None:
        detector.save(model_path)

    def load_detector(self, model_path: str) -> AnomalyDetector:
        return AnomalyDetector.load(model_path)

