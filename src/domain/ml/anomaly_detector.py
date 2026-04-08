"""Hybrid anomaly detector using Isolation Forest plus lightweight risk penalties."""

import os
import pickle
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from src.domain.transaction import Transaction
from src.domain.ml.feature_extractor import FeatureExtractor, TransactionFeatures


@dataclass
class AnomalyResult:
    """Anomaly analysis result for a transaction."""
    transaction_id: str
    is_anomaly: bool
    anomaly_score: float  # final hybrid score, lower = more anomalous
    confidence: float
    features: Optional[TransactionFeatures] = None
    explanation: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    model_score: float = 0.0
    rule_penalty: float = 0.0
    threshold: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'transaction_id': self.transaction_id,
            'is_anomaly': bool(self.is_anomaly),
            'anomaly_score': float(self.anomaly_score),
            'model_score': float(self.model_score),
            'rule_penalty': float(self.rule_penalty),
            'threshold': float(self.threshold),
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

    def fit(self, transactions: List[Transaction]) -> 'AnomalyDetector':
        """Trains the detector on clean/mostly-normal chronological transactions."""
        if len(transactions) < 25:
            raise ValueError("At least 25 transactions are required for stable training")

        X, transaction_ids = self.feature_extractor.extract_features_batch(transactions)
        if X.size == 0:
            raise ValueError("No features could be extracted for training")

        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled)

        train_scores = self.model.score_samples(X_scaled)
        adaptive_percentile = max(1.0, min(10.0, self.contamination * 100.0))

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
            'training_transaction_ids_sample': transaction_ids[:25],
            'anomaly_threshold': self.anomaly_threshold,
            'contamination': self.contamination,
            'trained_at': datetime.utcnow().isoformat(),
        }

        self.is_fitted = True
        return self

    def _compute_feature_risk_penalty(self, features: TransactionFeatures) -> float:
        """Applies small, interpretable penalties for known suspicious patterns."""
        penalty = 0.0

        if features.is_night:
            penalty += 0.08
        if features.is_weekend:
            penalty += 0.06
        if features.is_failed_attempt:
            penalty += 0.09
        if features.is_high_amount:
            penalty += 0.07
            if features.amount > 50000:
                penalty += 0.06
            if features.amount > 500000:
                penalty += 0.08
        if features.risk_level_encoded >= 2:
            penalty += 0.05
        if features.risk_level_encoded >= 3:
            penalty += 0.07
        if features.sender_tx_count_last_hour > 12:
            penalty += 0.05
        if features.sender_tx_count_last_hour > 30:
            penalty += 0.07
        if features.sender_tx_count_last_day > 80:
            penalty += 0.05
        if features.has_prior_tx and 0 <= features.time_since_last_tx < 10:
            penalty += 0.06
        if features.has_prior_tx and 0 <= features.time_since_last_tx < 2:
            penalty += 0.08
        if features.is_admin_event and features.is_night:
            penalty += 0.04

        return penalty

    def _calculate_confidence(self, score: float, threshold: float, score_std: float) -> float:
        """Maps the distance from threshold into a smooth confidence value."""
        std = max(score_std, 1e-6)
        margin = abs(score - threshold) / std
        return float(1.0 / (1.0 + np.exp(-margin)))

    def _generate_explanation(
        self,
        features: TransactionFeatures,
        final_score: float,
        model_score: float,
        rule_penalty: float,
        threshold: float,
        is_anomaly: bool,
    ) -> str:
        reasons: List[str] = []

        if features.is_night:
            reasons.append(f"night hour ({features.hour_of_day}:00)")
        if features.is_weekend:
            reasons.append("weekend activity")
        if features.is_high_amount:
            reasons.append(f"high amount ({features.amount:.2f})")
        if features.is_failed_attempt:
            reasons.append("failed authentication/access")
        if features.sender_tx_count_last_hour > 12:
            reasons.append(f"elevated hourly activity ({features.sender_tx_count_last_hour}/hour)")
        if features.sender_tx_count_last_day > 80:
            reasons.append(f"high daily activity ({features.sender_tx_count_last_day}/day)")
        if features.has_prior_tx and features.time_since_last_tx < 10:
            reasons.append(f"very short gap since last tx ({features.time_since_last_tx:.1f}s)")
        if features.risk_level_encoded >= 2:
            risk_names = ['low', 'medium', 'high', 'critical']
            reasons.append(f"risk={risk_names[min(features.risk_level_encoded, 3)]}")

        if is_anomaly:
            if not reasons:
                reasons.append("isolated by the ML baseline")
            prefix = "Anomaly detected"
        else:
            prefix = "Normal transaction"
            if not reasons:
                reasons.append("within learned user/system baseline")

        return (
            f"{prefix}: {'; '.join(reasons)} "
            f"[final={final_score:.3f}, ml={model_score:.3f}, penalty={rule_penalty:.3f}, threshold={threshold:.3f}]"
        )

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
        threshold = getattr(self, '_effective_threshold', self.anomaly_threshold)
        is_anomaly = final_score < threshold

        if (
            features.sender_tx_count_last_hour > 120
            or (features.has_prior_tx and 0 <= features.time_since_last_tx < 0.25)
            or features.amount > 1_000_000
        ):
            is_anomaly = True

        confidence = self._calculate_confidence(final_score, threshold, getattr(self, '_score_std', 0.05))
        explanation = self._generate_explanation(
            features,
            final_score,
            model_score,
            rule_penalty,
            threshold,
            is_anomaly,
        )

        return AnomalyResult(
            transaction_id=transaction.transaction_id,
            is_anomaly=is_anomaly,
            anomaly_score=final_score,
            model_score=model_score,
            rule_penalty=rule_penalty,
            threshold=threshold,
            confidence=confidence,
            features=features,
            explanation=explanation,
        )

    def predict_batch(self, transactions: List[Transaction]) -> List[AnomalyResult]:
        """Predicts sequentially over a chronological batch using prior events as history."""
        if not self.is_fitted:
            raise RuntimeError("Model must be trained before prediction")

        results: List[AnomalyResult] = []
        sorted_transactions = sorted(transactions, key=lambda tx: tx.timestamp)
        for i, tx in enumerate(sorted_transactions):
            results.append(self.predict(tx, sorted_transactions[:i]))
        return results

    def evaluate_dataset(self, transactions: List[Transaction], labels: List[str]) -> Dict[str, Any]:
        """Sequentially evaluates a labeled chronological dataset."""
        if len(transactions) != len(labels):
            raise ValueError("transactions and labels must have the same length")

        sorted_pairs = sorted(zip(transactions, labels), key=lambda x: x[0].timestamp)
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

        return {
            'total': len(results),
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'true_positives': tp,
            'true_negatives': tn,
            'false_positives': fp,
            'false_negatives': fn,
            'threshold': getattr(self, '_effective_threshold', self.anomaly_threshold),
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

    def save(self, filepath: str):
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
        state = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_extractor': self.feature_extractor,
            'is_fitted': self.is_fitted,
            'training_stats': self.training_stats,
            'score_stats': {
                'mean': getattr(self, '_score_mean', -0.5),
                'std': getattr(self, '_score_std', 0.05),
                'p1': getattr(self, '_score_p1', self.anomaly_threshold),
                'p5': getattr(self, '_score_p5', self.anomaly_threshold),
                'p10': getattr(self, '_score_p10', self.anomaly_threshold),
                'adaptive_threshold': getattr(self, '_adaptive_threshold', self.anomaly_threshold),
                'effective_threshold': getattr(self, '_effective_threshold', self.anomaly_threshold),
            },
            'config': {
                'contamination': self.contamination,
                'n_estimators': self.n_estimators,
                'max_samples': self.max_samples,
                'random_state': self.random_state,
                'anomaly_threshold': self.anomaly_threshold,
            },
        }
        with open(filepath, 'wb') as f:
            pickle.dump(state, f)

    @classmethod
    def load(cls, filepath: str) -> 'AnomalyDetector':
        with open(filepath, 'rb') as f:
            state = pickle.load(f)
        detector = cls(**state['config'])
        detector.model = state['model']
        detector.scaler = state['scaler']
        detector.feature_extractor = state.get('feature_extractor', FeatureExtractor())
        detector.is_fitted = state['is_fitted']
        detector.training_stats = state['training_stats']
        score_stats = state.get('score_stats', {})
        detector._score_mean = score_stats.get('mean', -0.5)
        detector._score_std = score_stats.get('std', 0.05)
        detector._score_p1 = score_stats.get('p1', detector.anomaly_threshold)
        detector._score_p5 = score_stats.get('p5', detector.anomaly_threshold)
        detector._score_p10 = score_stats.get('p10', detector.anomaly_threshold)
        detector._adaptive_threshold = score_stats.get('adaptive_threshold', detector.anomaly_threshold)
        detector._effective_threshold = score_stats.get('effective_threshold', detector._adaptive_threshold)
        return detector

    def __str__(self) -> str:
        status = 'trained' if self.is_fitted else 'untrained'
        return f"AnomalyDetector({status}, contamination={self.contamination})"
