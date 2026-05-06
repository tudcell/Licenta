"""Port for persisting and loading anomaly detector state."""

from __future__ import annotations

from typing import Optional, Protocol

from src.domain.ml.anomaly_detector import AnomalyDetector


class ModelStore(Protocol):
    def load(self) -> Optional[AnomalyDetector]: ...
    def save(self, detector: AnomalyDetector) -> None: ...
    def exists(self) -> bool: ...
