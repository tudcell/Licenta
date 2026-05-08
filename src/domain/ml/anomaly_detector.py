"""Hybrid anomaly detector using Isolation Forest plus lightweight risk penalties."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from src.domain.entities.transaction import Transaction
from src.domain.ml.feature_extractor import FeatureExtractor, TransactionFeatures


# ---------------------------------------------------------------------------
# Penalty predicates
# ---------------------------------------------------------------------------
# The hybrid scoring pipeline adds a small "rule penalty" on top of the
# IsolationForest score. Each predicate below describes a feature pattern
# that historically tended to be anomalous; the *magnitude* of the bump it
# contributes is no longer hand-coded — it's recomputed from the training
# distribution every time the detector is fit. See
# `AnomalyDetector._compute_penalty_weights` for the data-driven formula.
#
# The default weights below are kept only as a fallback for (a) detectors
# that haven't been fit yet and (b) old pickle files persisted under the
# previous, hand-tuned scheme.
PenaltyPredicate = Callable[["TransactionFeatures", "AnomalyDetector"], bool]

_PENALTY_PREDICATES: List[Tuple[str, PenaltyPredicate]] = [
    ("is_night",                  lambda f, d: bool(f.is_night)),
    ("is_weekend",                lambda f, d: bool(f.is_weekend)),
    ("is_failed_attempt",         lambda f, d: bool(f.is_failed_attempt)),
    ("amount_above_high",         lambda f, d: f.amount > d._amount_high_threshold),
    ("amount_above_very_high",    lambda f, d: f.amount > d._amount_very_high_threshold),
    ("moderate_high_amount",      lambda f, d: f.amount <= d._amount_high_threshold and bool(f.is_high_amount)),
    ("risk_level_high",           lambda f, d: f.risk_level_encoded >= 2),
    ("risk_level_critical",       lambda f, d: f.risk_level_encoded >= 3),
    ("hourly_activity_elevated",  lambda f, d: f.sender_tx_count_last_hour > 12),
    ("hourly_activity_high",      lambda f, d: f.sender_tx_count_last_hour > 30),
    ("daily_activity_high",       lambda f, d: f.sender_tx_count_last_day > 80),
    ("rapid_followup",            lambda f, d: bool(f.has_prior_tx) and 0 <= f.time_since_last_tx < 10),
    ("very_rapid_followup",       lambda f, d: bool(f.has_prior_tx) and 0 <= f.time_since_last_tx < 2),
    ("admin_at_night",            lambda f, d: bool(f.is_admin_event) and bool(f.is_night)),
    ("activity_spike",            lambda f, d: f.activity_spike_ratio > 4.0 and f.sender_tx_count_last_hour > 8),
    ("receiver_flooded",          lambda f, d: bool(f.is_transfer_event) and f.receiver_amount_sum_last_day > 50000.0),
    ("receiver_inactive",         lambda f, d: bool(f.is_transfer_event) and f.receiver_tx_count_last_day == 0),
]

# Hand-tuned baseline; preserves the old behaviour for unfit detectors and
# for predicates that don't have enough training samples to estimate.
_DEFAULT_PENALTY_WEIGHTS: Dict[str, float] = {
    "is_night":                 0.08,
    "is_weekend":               0.06,
    "is_failed_attempt":        0.09,
    "amount_above_high":        0.07,
    "amount_above_very_high":   0.08,
    "moderate_high_amount":     0.03,
    "risk_level_high":          0.05,
    "risk_level_critical":      0.07,
    "hourly_activity_elevated": 0.05,
    "hourly_activity_high":     0.07,
    "daily_activity_high":      0.05,
    "rapid_followup":           0.06,
    "very_rapid_followup":      0.08,
    "admin_at_night":           0.04,
    "activity_spike":           0.08,
    "receiver_flooded":         0.06,
    "receiver_inactive":        0.04,
}

# Predicates with fewer than this many positive samples in training data
# can't be reliably weighted; we fall back to the hand-coded default.
_MIN_PENALTY_SAMPLE_COUNT = 5
# Cap individual learned weights to keep one rare predicate from dominating.
_MAX_LEARNED_PENALTY = 0.20


@dataclass
class AnomalyResult:
    """Anomaly analysis result for a transaction."""
    transaction_id: str
    is_anomaly: bool
    anomaly_score: float  # final hybrid score, lower = more anomalous
    confidence: float
    features: Optional[TransactionFeatures] = None
    explanation: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    model_score: float = 0.0
    rule_penalty: float = 0.0
    threshold: float = 0.0
    model_is_anomaly: bool = False
    hard_rule_triggered: bool = False
    hard_rule_reason: Optional[str] = None
    decision_source: str = "model"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'transaction_id': self.transaction_id,
            'is_anomaly': bool(self.is_anomaly),
            'anomaly_score': float(self.anomaly_score),
            'model_score': float(self.model_score),
            'rule_penalty': float(self.rule_penalty),
            'threshold': float(self.threshold),
            'model_is_anomaly': bool(self.model_is_anomaly),
            'hard_rule_triggered': bool(self.hard_rule_triggered),
            'hard_rule_reason': self.hard_rule_reason,
            'decision_source': self.decision_source,
            'confidence': float(self.confidence),
            'explanation': self.explanation,
            'timestamp': self.timestamp,
            'features': self.features.to_dict() if self.features else None,
        }

    def __str__(self) -> str:
        status = "ANOMALY" if self.is_anomaly else "Normal"
        return f"{status} | Final: {self.anomaly_score:.3f} | ML: {self.model_score:.3f} | Confidence: {self.confidence:.2%}"


class AnomalyDetector:
    """Isolation Forest based anomaly detector with calibrated thresholds."""

    def __init__(
            self,
            contamination: float = 0.02,
            n_estimators: int = 300,
            max_samples: str = 'auto',
            random_state: int = 42,
            anomaly_threshold: float = -0.62,
    ):
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.random_state = random_state
        self.anomaly_threshold = anomaly_threshold

        self.model = IsolationForest(
            contamination=contamination,
            n_estimators=n_estimators,
            max_samples=max_samples,
            random_state=random_state,
            n_jobs=-1,
        )
        self.scaler = StandardScaler()
        self.feature_extractor = FeatureExtractor()
        self.is_fitted = False
        self.training_stats: Dict[str, Any] = {}

        # Pre-fit defaults for stats consulted by predict()/_compute_feature_risk_penalty().
        # Keeping them populated here avoids `getattr(self, '_score_p1', default)` ladders later.
        self._model_score_mean = -0.5
        self._model_score_std = 0.05
        self._score_mean = -0.5
        self._score_std = 0.05
        self._score_p1 = anomaly_threshold
        self._score_p5 = anomaly_threshold
        self._score_p10 = anomaly_threshold
        self._adaptive_threshold = anomaly_threshold
        self._effective_threshold = anomaly_threshold
        self._amount_mean = 0.0
        self._amount_std = 0.0
        self._amount_high_threshold = 0.0
        self._amount_very_high_threshold = 0.0

        # Per-predicate penalty weights. Recomputed from training data in
        # `fit()`; the defaults are used for unfit detectors and as a fallback
        # for predicates with too few positive samples to estimate reliably.
        self._penalty_weights: Dict[str, float] = dict(_DEFAULT_PENALTY_WEIGHTS)

    def fit(self, transactions: List[Transaction]) -> 'AnomalyDetector':
        """Trains the detector on clean/mostly-normal chronological transactions."""
        if len(transactions) < 25:
            raise ValueError("At least 25 transactions are required for stable training")

        X, transaction_ids = self.feature_extractor.extract_features_batch(transactions)
        if X.size == 0:
            raise ValueError("No features could be extracted for training")

        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled)

        amounts = [
            float(tx.data.get('amount', 0.0) or 0.0) if tx.transaction_type.value == 'TRANSFER' else 0.0
            for tx in transactions
        ]
        self._amount_mean = float(np.mean(amounts)) if amounts else 0.0
        self._amount_std = float(np.std(amounts)) if amounts else 0.0
        self._amount_high_threshold = self._amount_mean + (3.0 * self._amount_std)
        self._amount_very_high_threshold = self._amount_mean + (4.0 * self._amount_std)

        train_model_scores = self.model.score_samples(X_scaled)

        # Extract per-transaction features once; we need them to (a) learn
        # the data-driven penalty weights and then (b) apply those weights
        # to compute training penalties.
        history: List[Transaction] = []
        train_features: List[TransactionFeatures] = []
        for tx in transactions:
            tx_features = self.feature_extractor.extract_features(tx, history)
            train_features.append(tx_features)
            history.append(tx)

        # Learn penalty weights from the training distribution, then apply them.
        self._penalty_weights = self._compute_penalty_weights(train_features, train_model_scores)
        train_rule_penalties = np.array(
            [self._compute_feature_risk_penalty(f) for f in train_features]
        )

        train_scores = train_model_scores - train_rule_penalties
        adaptive_percentile = max(1.0, min(10.0, self.contamination * 100.0))

        self._model_score_mean = float(np.mean(train_model_scores))
        self._model_score_std = float(np.std(train_model_scores))
        self._score_mean = float(np.mean(train_scores))
        self._score_std = float(np.std(train_scores))
        self._score_p1 = float(np.percentile(train_scores, 1))
        self._score_p5 = float(np.percentile(train_scores, 5))
        self._score_p10 = float(np.percentile(train_scores, 10))
        self._adaptive_threshold = float(np.percentile(train_scores, adaptive_percentile))

        # lower score = more anomalous, so taking the maximum keeps the threshold from becoming too strict
        self._effective_threshold = max(self.anomaly_threshold, self._adaptive_threshold)

        self.training_stats = {
            'n_samples': len(transactions),
            'n_features': int(X.shape[1]),
            'feature_names': TransactionFeatures.get_feature_names(),
            'feature_means': self.scaler.mean_.tolist(),
            'feature_stds': self.scaler.scale_.tolist(),
            'score_distribution': {
                'model_mean': self._model_score_mean,
                'model_std': self._model_score_std,
                'mean': self._score_mean,
                'std': self._score_std,
                'min': float(np.min(train_scores)),
                'max': float(np.max(train_scores)),
                'percentile_1': self._score_p1,
                'percentile_5': self._score_p5,
                'percentile_10': self._score_p10,
                'adaptive_percentile': adaptive_percentile,
                'adaptive_threshold': self._adaptive_threshold,
                'effective_threshold': self._effective_threshold,
            },
            'penalty_distribution': {
                'mean': float(np.mean(train_rule_penalties)) if len(train_rule_penalties) else 0.0,
                'std': float(np.std(train_rule_penalties)) if len(train_rule_penalties) else 0.0,
                'max': float(np.max(train_rule_penalties)) if len(train_rule_penalties) else 0.0,
            },
            'penalty_weights': dict(self._penalty_weights),
            'training_transaction_ids_sample': transaction_ids[:25],
            'anomaly_threshold': self.anomaly_threshold,
            'contamination': self.contamination,
            'trained_at': datetime.now(timezone.utc).isoformat(),
            'amount_distribution': {
                'mean': self._amount_mean,
                'std': self._amount_std,
                'high_threshold': self._amount_high_threshold,
                'very_high_threshold': self._amount_very_high_threshold,
            },
        }

        self.is_fitted = True
        return self

    def _compute_feature_risk_penalty(self, features: TransactionFeatures) -> float:
        """Sum the learned weights for every predicate that fires.

        The set of predicates is fixed (declared in `_PENALTY_PREDICATES`) but
        each predicate's weight is recomputed from training data — see
        `_compute_penalty_weights`. The total is capped at 1.0 so the rule
        layer can never single-handedly override a strong model signal.
        """
        penalty = 0.0
        for name, predicate in _PENALTY_PREDICATES:
            if predicate(features, self):
                penalty += self._penalty_weights.get(name, 0.0)
        return min(penalty, 1.0)

    def _compute_penalty_weights(
            self,
            train_features: List[TransactionFeatures],
            train_model_scores: np.ndarray,
    ) -> Dict[str, float]:
        """Derive a per-predicate penalty from the training distribution.

        For each predicate, the weight is the gap between the population's
        median IsolationForest score and the median score on the subset
        where the predicate holds (clipped at 0 — features that *don't*
        correlate with anomaly contribute nothing).

        Limitations (worth mentioning in the thesis):
          - Predicates that overlap (e.g. `amount_above_high` and
            `amount_above_very_high`) are scored independently, so when both
            fire their weights stack additively. This slightly over-penalises
            correlated patterns, biasing the system toward false positives —
            preferable to false negatives in a security audit context.
          - Predicates with fewer than `_MIN_PENALTY_SAMPLE_COUNT` positive
            occurrences in training data fall back to the hand-coded default
            from `_DEFAULT_PENALTY_WEIGHTS` because the median is unstable
            on tiny groups.
        """
        if len(train_features) == 0 or len(train_model_scores) == 0:
            return dict(_DEFAULT_PENALTY_WEIGHTS)

        baseline = float(np.median(train_model_scores))
        weights: Dict[str, float] = {}

        for name, predicate in _PENALTY_PREDICATES:
            mask = np.fromiter(
                (predicate(f, self) for f in train_features),
                dtype=bool,
                count=len(train_features),
            )
            positive = int(mask.sum())
            if positive < _MIN_PENALTY_SAMPLE_COUNT:
                weights[name] = _DEFAULT_PENALTY_WEIGHTS.get(name, 0.0)
                continue
            median_when_true = float(np.median(train_model_scores[mask]))
            lift = max(0.0, baseline - median_when_true)
            weights[name] = float(min(lift, _MAX_LEARNED_PENALTY))
        return weights

    def _calculate_confidence(self, score: float, threshold: float, score_std: float) -> float:
        """Maps the distance from threshold into a smooth confidence value."""
        std = max(score_std, 1e-6)
        margin = abs(score - threshold) / std
        return float(1.0 - np.exp(-margin))

    def _generate_explanation(
            self,
            features: TransactionFeatures,
            final_score: float,
            model_score: float,
            rule_penalty: float,
            threshold: float,
            is_anomaly: bool,
            decision_source: str,
            hard_rule_reason: Optional[str],
    ) -> str:
        reasons: List[str] = []

        if features.is_night:
            reasons.append(f"night hour ({features.hour_of_day}:00)")
        if features.is_weekend:
            reasons.append("weekend activity")

        # Amount — same dynamic thresholds as _compute_feature_risk_penalty
        if features.amount > self._amount_very_high_threshold:
            reasons.append(
                f"very high amount ({features.amount:.2f}, threshold={self._amount_very_high_threshold:.0f})")
        elif features.amount > self._amount_high_threshold:
            reasons.append(f"high amount ({features.amount:.2f}, threshold={self._amount_high_threshold:.0f})")
        elif features.is_high_amount:
            reasons.append(f"high amount ({features.amount:.2f})")

        if features.is_failed_attempt:
            reasons.append("failed authentication/access")

        # Sender frequency — match both penalty thresholds (>12 and >30)
        if features.sender_tx_count_last_hour > 30:
            reasons.append(f"excessive hourly activity ({features.sender_tx_count_last_hour}/hour)")
        elif features.sender_tx_count_last_hour > 12:
            reasons.append(f"elevated hourly activity ({features.sender_tx_count_last_hour}/hour)")

        if features.sender_tx_count_last_day > 80:
            reasons.append(f"high daily activity ({features.sender_tx_count_last_day}/day)")

        # Time since last tx — match both penalty thresholds (<2s and <10s)
        if features.has_prior_tx and 0 <= features.time_since_last_tx < 2:
            reasons.append(f"extremely short gap since last tx ({features.time_since_last_tx:.1f}s)")
        elif features.has_prior_tx and features.time_since_last_tx < 10:
            reasons.append(f"very short gap since last tx ({features.time_since_last_tx:.1f}s)")

        if features.risk_level_encoded >= 2:
            risk_names = ['low', 'medium', 'high', 'critical']
            reasons.append(f"risk={risk_names[min(features.risk_level_encoded, 3)]}")

        # Admin event at night — has penalty but was missing from explanation
        if features.is_admin_event and features.is_night:
            reasons.append("administrative event during night hours")

        # Burst/Spike
        if features.activity_spike_ratio > 4.0 and features.sender_tx_count_last_hour > 8:
            reasons.append(f"sudden spike in activity ({features.activity_spike_ratio:.1f}x normal rate)")

        # Receiver
        if features.is_transfer_event:
            if features.receiver_amount_sum_last_day > 50000.0:
                reasons.append("recipient accumulated high funds recently")
            if features.receiver_tx_count_last_day == 0:
                reasons.append("transfer to a completely new/inactive recipient")

        if is_anomaly:
            if not reasons:
                reasons.append("isolated by the ML baseline")
            prefix = "Anomaly detected"
        else:
            prefix = "Normal transaction"
            if not reasons:
                reasons.append("within learned user/system baseline")

        explanation = (
            f"{prefix}: {'; '.join(reasons)} "
            f"[final={final_score:.3f}, ml={model_score:.3f}, penalty={rule_penalty:.3f}, threshold={threshold:.3f}]"
        )
        if decision_source == 'hard_rule' and hard_rule_reason:
            explanation += f" [decision=hard_rule:{hard_rule_reason}]"
        else:
            explanation += " [decision=model]"
        return explanation

    def predict(self, transaction: Transaction, historical_transactions: List[Transaction] = None) -> AnomalyResult:
        """Predicts whether a transaction is anomalous using contextual history."""
        if not self.is_fitted:
            raise RuntimeError("Model must be trained before prediction. Call fit() first.")

        features = self.feature_extractor.extract_features(transaction, historical_transactions or [])
        X = features.to_vector().reshape(1, -1)
        X_scaled = self.scaler.transform(X)

        model_score = float(self.model.score_samples(X_scaled)[0])
        rule_penalty = self._compute_feature_risk_penalty(features)
        final_score = model_score - rule_penalty
        threshold = self._effective_threshold
        model_is_anomaly = final_score < threshold
        is_anomaly = model_is_anomaly

        hard_rule_triggered = False
        hard_rule_reason = None
        if features.sender_tx_count_last_hour > 120:
            hard_rule_triggered = True
            hard_rule_reason = "hourly_burst"
        elif features.has_prior_tx and 0 <= features.time_since_last_tx < 0.25:
            hard_rule_triggered = True
            hard_rule_reason = "ultra_short_gap"
        elif features.amount > 1_000_000:
            hard_rule_triggered = True
            hard_rule_reason = "extreme_amount"

        if hard_rule_triggered:
            is_anomaly = True

        decision_source = 'hard_rule' if hard_rule_triggered else 'model'

        confidence = self._calculate_confidence(final_score, threshold, self._score_std)
        if hard_rule_triggered:
            confidence = max(confidence, 0.9)

        explanation = self._generate_explanation(
            features,
            final_score,
            model_score,
            rule_penalty,
            threshold,
            is_anomaly,
            decision_source,
            hard_rule_reason,
        )

        return AnomalyResult(
            transaction_id=transaction.transaction_id,
            is_anomaly=is_anomaly,
            anomaly_score=final_score,
            model_score=model_score,
            rule_penalty=rule_penalty,
            threshold=threshold,
            model_is_anomaly=model_is_anomaly,
            hard_rule_triggered=hard_rule_triggered,
            hard_rule_reason=hard_rule_reason,
            decision_source=decision_source,
            confidence=confidence,
            features=features,
            explanation=explanation,
        )

    def predict_batch(self, transactions: List[Transaction]) -> List[AnomalyResult]:
        """Predicts sequentially over a chronological batch using prior events as history."""
        if not self.is_fitted:
            raise RuntimeError("Model must be trained before prediction")

        results: List[AnomalyResult] = []
        sorted_transactions = sorted(transactions, key=lambda tx: self.feature_extractor._parse_timestamp(tx.timestamp))
        for i, tx in enumerate(sorted_transactions):
            results.append(self.predict(tx, sorted_transactions[:i]))
        return results

    def evaluate_dataset(self, transactions: List[Transaction], labels: List[str]) -> Dict[str, Any]:
        """Sequentially evaluates a labeled chronological dataset."""
        if len(transactions) != len(labels):
            raise ValueError("transactions and labels must have the same length")

        sorted_pairs = sorted(
            zip(transactions, labels),
            key=lambda item: self.feature_extractor._parse_timestamp(item[0].timestamp),
        )
        history: List[Transaction] = []
        results: List[AnomalyResult] = []
        y_true: List[bool] = []

        for tx, label in sorted_pairs:
            result = self.predict(tx, history)
            results.append(result)
            y_true.append(label != 'normal')
            history.append(tx)

        tp = sum(1 for y, r in zip(y_true, results) if y and r.is_anomaly)
        tn = sum(1 for y, r in zip(y_true, results) if not y and not r.is_anomaly)
        fp = sum(1 for y, r in zip(y_true, results) if not y and r.is_anomaly)
        fn = sum(1 for y, r in zip(y_true, results) if y and not r.is_anomaly)

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        accuracy = (tp + tn) / len(results) if results else 0.0
        f1_score = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

        return {
            'total': len(results),
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1_score': f1_score,
            'true_positives': tp,
            'true_negatives': tn,
            'false_positives': fp,
            'false_negatives': fn,
            'threshold': self._effective_threshold,
            'score_mean': float(np.mean([r.anomaly_score for r in results])) if results else 0.0,
            'score_min': float(np.min([r.anomaly_score for r in results])) if results else 0.0,
            'score_max': float(np.max([r.anomaly_score for r in results])) if results else 0.0,
        }

    def get_anomaly_statistics(self, results: List[AnomalyResult]) -> Dict[str, Any]:
        if not results:
            return {}
        anomalies = [r for r in results if r.is_anomaly]
        normal = [r for r in results if not r.is_anomaly]
        scores = [r.anomaly_score for r in results]
        model_scores = [r.model_score for r in results]
        return {
            'total_transactions': len(results),
            'anomalies_count': len(anomalies),
            'normal_count': len(normal),
            'anomaly_rate': len(anomalies) / len(results),
            'score_mean': float(np.mean(scores)),
            'score_std': float(np.std(scores)),
            'score_min': float(np.min(scores)),
            'score_max': float(np.max(scores)),
            'model_score_mean': float(np.mean(model_scores)),
            'avg_anomaly_confidence': float(np.mean([r.confidence for r in anomalies])) if anomalies else 0.0,
            'avg_normal_confidence': float(np.mean([r.confidence for r in normal])) if normal else 0.0,
        }

    def to_state(self) -> Dict[str, Any]:
        """Serializable state. Persistence is the adapter's job."""
        return {
            'model': self.model,
            'scaler': self.scaler,
            'feature_extractor': self.feature_extractor,
            'is_fitted': self.is_fitted,
            'training_stats': self.training_stats,
            'score_stats': {
                'model_mean': self._model_score_mean,
                'model_std': self._model_score_std,
                'mean': self._score_mean,
                'std': self._score_std,
                'p1': self._score_p1,
                'p5': self._score_p5,
                'p10': self._score_p10,
                'adaptive_threshold': self._adaptive_threshold,
                'effective_threshold': self._effective_threshold,
            },
            'amount_stats': {
                'mean': self._amount_mean,
                'std': self._amount_std,
                'high_threshold': self._amount_high_threshold,
                'very_high_threshold': self._amount_very_high_threshold,
            },
            'penalty_weights': dict(self._penalty_weights),
            'config': {
                'contamination': self.contamination,
                'n_estimators': self.n_estimators,
                'max_samples': self.max_samples,
                'random_state': self.random_state,
                'anomaly_threshold': self.anomaly_threshold,
            },
        }

    @classmethod
    def from_state(cls, state: Dict[str, Any]) -> 'AnomalyDetector':
        detector = cls(**state['config'])
        detector.model = state['model']
        detector.scaler = state['scaler']
        detector.feature_extractor = state.get('feature_extractor', FeatureExtractor())
        detector.is_fitted = state['is_fitted']
        detector.training_stats = state['training_stats']
        score_stats = state.get('score_stats', {})
        detector._model_score_mean = score_stats.get('model_mean', -0.5)
        detector._model_score_std = score_stats.get('model_std', 0.05)
        detector._score_mean = score_stats.get('mean', -0.5)
        detector._score_std = score_stats.get('std', 0.05)
        detector._score_p1 = score_stats.get('p1', detector.anomaly_threshold)
        detector._score_p5 = score_stats.get('p5', detector.anomaly_threshold)
        detector._score_p10 = score_stats.get('p10', detector.anomaly_threshold)
        detector._adaptive_threshold = score_stats.get('adaptive_threshold', detector.anomaly_threshold)
        detector._effective_threshold = score_stats.get('effective_threshold', detector._adaptive_threshold)
        amount_stats = state.get('amount_stats') or detector.training_stats.get('amount_distribution', {})
        detector._amount_mean = amount_stats.get('mean', 0.0)
        detector._amount_std = amount_stats.get('std', 0.0)
        detector._amount_high_threshold = amount_stats.get('high_threshold',
                                                           detector._amount_mean + (3.0 * detector._amount_std))
        detector._amount_very_high_threshold = amount_stats.get('very_high_threshold',
                                                                detector._amount_mean + (4.0 * detector._amount_std))
        # Penalty weights: prefer the explicit `penalty_weights` from state,
        # fall back to whatever training_stats persisted, fall back to the
        # hand-coded defaults so older pickle files still load and behave
        # identically to the previous fixed-weight scheme.
        persisted_weights = state.get('penalty_weights') \
            or detector.training_stats.get('penalty_weights') \
            or {}
        merged_weights = dict(_DEFAULT_PENALTY_WEIGHTS)
        merged_weights.update({k: float(v) for k, v in persisted_weights.items() if k in merged_weights})
        detector._penalty_weights = merged_weights
        return detector

    def __str__(self) -> str:
        status = 'trained' if self.is_fitted else 'untrained'
        return f"AnomalyDetector({status}, contamination={self.contamination})"
