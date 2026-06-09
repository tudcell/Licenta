"""Reproducible evaluation of the hybrid anomaly detector.

Trains an AnomalyDetector on synthetic normal traffic, then scores a held-out
mix of normal and anomalous events and prints the confusion matrix plus
precision, recall and F1.

The run is fully deterministic. Three sources of non-determinism are pinned:
the standard ``random`` module and NumPy are seeded, the Isolation Forest uses a
fixed ``random_state``, and the synthetic data generator (which otherwise
anchors every event timestamp to the current wall-clock time) is frozen to a
fixed reference instant. Without that last step the hour/day/weekend/night
features shift with the date the script is run on. With it, the reported
confusion matrix is identical on every run and every machine.

Usage (from the repository root):
    python -m src.utils.evaluate_detector
"""

from __future__ import annotations

import datetime as _dt
import random

import numpy as np

SEED = 42
TRAIN_NORMAL = 1000
TEST_NORMAL = 200
TEST_ANOMALOUS = 50

# Fixed reference instant: a regular weekday afternoon (Monday, 14:00 UTC).
# The synthetic generator builds every timestamp relative to "now", so pinning
# it keeps the time-derived features stable across runs and machines.
_FROZEN_NOW = _dt.datetime(2025, 6, 2, 14, 0, 0, tzinfo=_dt.timezone.utc)


class _FrozenDateTime(_dt.datetime):
    """datetime subclass whose now() always returns the fixed reference instant."""

    @classmethod
    def now(cls, tz=None):
        return _FROZEN_NOW if tz is None else _FROZEN_NOW.astimezone(tz)


def main() -> None:
    # App-order imports to avoid the entities<->ml circular-import edge.
    import src.domain.entities.transaction  # noqa: F401
    import src.domain.entities.audit_report  # noqa: F401
    from src.domain.ml.anomaly_detector import AnomalyDetector
    from src.utils import training_data_generator as tdg
    from src.utils.data_generator import DataGenerator

    # Freeze the generator's clock, then seed both RNGs. With timestamps pinned
    # and the random state fixed, the whole generate -> fit -> evaluate pipeline
    # is deterministic regardless of when or where it runs.
    tdg.datetime = _FrozenDateTime
    random.seed(SEED)
    np.random.seed(SEED)

    gen = DataGenerator()

    train = gen.generate_normal_transactions(TRAIN_NORMAL)
    detector = AnomalyDetector()  # contamination=0.02, n_estimators=300, random_state=42
    detector.fit(train)

    # The generator removes duplicate events, so the distinct test-normal count
    # can be slightly below the request; the denominators below use the actual
    # counts.
    test_normal = gen.generate_normal_transactions(TEST_NORMAL)
    test_anomalous = gen.generate_anomalies(TEST_ANOMALOUS)
    transactions = test_normal + test_anomalous
    labels = ["normal"] * len(test_normal) + ["anomaly"] * len(test_anomalous)

    metrics = detector.evaluate_dataset(transactions, labels)

    tp = metrics["true_positives"]
    tn = metrics["true_negatives"]
    fp = metrics["false_positives"]
    fn = metrics["false_negatives"]

    n_anom = len(test_anomalous)
    n_norm = len(test_normal)
    print(f"seed                 = {SEED}")
    print(f"train normal         = {TRAIN_NORMAL}")
    print(f"test normal          = {n_norm}")
    print(f"test anomalous       = {n_anom}")
    print("-" * 40)
    print(f"true positives  (TP) = {tp} / {n_anom}")
    print(f"false negatives (FN) = {fn} / {n_anom}")
    print(f"false positives (FP) = {fp} / {n_norm}")
    print(f"true negatives  (TN) = {tn} / {n_norm}")
    print("-" * 40)
    print(f"precision            = {metrics['precision']:.3f}")
    print(f"recall               = {metrics['recall']:.3f}")
    print(f"f1_score             = {metrics['f1_score']:.3f}")
    print(f"accuracy             = {metrics['accuracy']:.3f}")


if __name__ == "__main__":
    main()
