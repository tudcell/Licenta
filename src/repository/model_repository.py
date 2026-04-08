"""Repository for ML model save/load persistence."""

from __future__ import annotations

import os
from typing import Optional

from src.domain import AnomalyDetector


class ModelRepository:
    """Persistence-only ML model gateway."""

    def __init__(self, model_path: str):
        self._model_path = model_path

    @property
    def model_path(self) -> str:
        return self._model_path

    def exists(self) -> bool:
        return os.path.exists(self._model_path)

    def load_detector(self) -> Optional[AnomalyDetector]:
        if not self.exists():
            return None
        return AnomalyDetector.load(self._model_path)

    def save_detector(self, detector: AnomalyDetector) -> str:
        detector.save(self._model_path)
        return self._model_path
