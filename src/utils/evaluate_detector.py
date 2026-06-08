"""Reproducible evaluation of the hybrid anomaly detector.

Trains an AnomalyDetector on synthetic normal traffic, then scores a held-out
mix of normal and anomalous events and prints the confusion matrix plus
precision, recall and F1. The run is deterministic: both the standard `random`
module and NumPy are seeded, and the Isolation Forest itself uses a fixed
random_state. Re-running this script reproduces the reported numbers exactly.

Usage (from the repository root):
    python -m src.utils.evaluate_detector
"""

from __future__ import annotations

import random
import numpy as np

SEED = 42
TRAIN_NORMAL = 1000
TEST_NORMAL = 200
TEST_ANOMALOUS = 50


def main() -> None:
    # Imports happen first, in app order, to avoid the entities<->ml
    # circular-import edge.
    import src.domain.entities.transaction  # noqa: F401
    import src.domain.entities.audit_report  # noqa: F401
    from src.domain.ml.anomaly_detector import AnomalyDetector
    from src.utils.data_generator import DataGenerator

    # Warm up every first-use (lazy) import along the generate -> fit ->
    # evaluate path BEFORE seeding. Some of these imports are triggered only on
    # first use and consume a random draw; if one fired between the seed and the
    # real run it would shift the whole generated sequence by one event and flip
    # a few labels. Running the path once on throwaway data forces those imports
    # to resolve up front, which is what makes the reported numbers reproduce
    # exactly regardless of invocation method or what is already imported.
    _warm = DataGenerator()
    _warm_detector = AnomalyDetector()
    _warm_detector.fit(_warm.generate_normal_transactions(100))
    _warm_normal = _warm.generate_normal_transactions(5)
    _warm_anom = _warm.generate_anomalies(2)
    _warm_detector.evaluate_dataset(
        _warm_normal + _warm_anom,
        ["normal"] * len(_warm_normal) + ["anomaly"] * len(_warm_anom),
    )

    random.seed(SEED)
    np.random.seed(SEED)

    gen = DataGenerator()

    train = gen.generate_normal_transactions(TRAIN_NORMAL)
    detector = AnomalyDetector()  # contamination=0.02, n_estimators=300, random_state=42
    detector.fit(train)

    test_normal = gen.generate_normal_transactions(TEST_NORMAL)
    test_anomalous = gen.generate_anomalies(TEST_ANOMALOUS)
    transactions = test_normal + test_anomalous
    labels = ["normal"] * len(test_normal) + ["anomaly"] * len(test_anomalous)

    metrics = detector.evaluate_dataset(transactions, labels)

    tp = metrics["true_positives"]
    tn = metrics["true_negatives"]
    fp = metrics["false_positives"]
    fn = metrics["false_negatives"]

    print(f"seed                 = {SEED}")
    print(f"train normal         = {TRAIN_NORMAL}")
    print(f"test normal          = {len(test_normal)}")
    print(f"test anomalous       = {len(test_anomalous)}")
    print("-" * 40)
    n_anom = len(test_anomalous)
    n_norm = len(test_normal)
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
