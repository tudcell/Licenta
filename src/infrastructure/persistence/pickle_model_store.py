"""Pickle-backed adapter for persisting AnomalyDetector state."""

from __future__ import annotations

import logging
import os
import pickle
from typing import Optional

from src.domain.ml.anomaly_detector import AnomalyDetector

logger = logging.getLogger("blockchain_audit")


class PickleModelStore:
    def __init__(self, filepath: str):
        self.filepath = filepath

    def exists(self) -> bool:
        return os.path.exists(self.filepath)

    def load(self) -> Optional[AnomalyDetector]:
        if not self.exists():
            return None
        try:
            with open(self.filepath, "rb") as f:
                state = pickle.load(f)
            return AnomalyDetector.from_state(state)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to load ML model from %s: %s. Continuing with untrained detector.",
                self.filepath,
                exc,
            )
            return None

    def save(self, detector: AnomalyDetector) -> None:
        directory = os.path.dirname(self.filepath) or "."
        os.makedirs(directory, exist_ok=True)
        with open(self.filepath, "wb") as f:
            pickle.dump(detector.to_state(), f)
        logger.info("ML model saved to %s", self.filepath)
