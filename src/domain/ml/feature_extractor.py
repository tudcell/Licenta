"""
Feature extraction module for ML transaction analysis.
Transforms transactions into stable numerical vectors for anomaly detection.
"""

import numpy as np
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

from src.domain.entities.transaction import Transaction, TransactionType


@dataclass
class TransactionFeatures:
    """Features extracted from a transaction for ML analysis."""
    transaction_id: str

    # Raw temporal values kept for explanations / debugging
    hour_of_day: int
    day_of_week: int

    # Cyclical temporal encoding used by the model
    hour_sin: float
    hour_cos: float
    day_sin: float
    day_cos: float
    is_weekend: int
    is_night: int

    # Grouped categorical transaction type flags
    is_auth_event: int
    is_data_event: int
    is_transfer_event: int
    is_admin_event: int
    is_failure_event: int

    # Value features
    amount: float
    amount_log: float

    # Behavioral features
    sender_tx_count_last_hour: int
    sender_tx_count_last_day: int
    sender_tx_count_last_hour_log: float
    sender_tx_count_last_day_log: float
    has_prior_tx: int
    time_since_last_tx: float
    time_since_last_tx_log: float

    # Risk features
    is_high_amount: int
    risk_level_encoded: int
    is_failed_attempt: int

    def to_vector(self) -> np.ndarray:
        """Converts features to the model input vector."""
        return np.array([
            self.hour_sin,
            self.hour_cos,
            self.day_sin,
            self.day_cos,
            self.is_weekend,
            self.is_night,
            self.is_auth_event,
            self.is_data_event,
            self.is_transfer_event,
            self.is_admin_event,
            self.is_failure_event,
            self.amount_log,
            self.sender_tx_count_last_hour_log,
            self.sender_tx_count_last_day_log,
            self.has_prior_tx,
            self.time_since_last_tx_log,
            self.is_high_amount,
            self.risk_level_encoded,
            self.is_failed_attempt,
        ], dtype=np.float64)

    @staticmethod
    def get_feature_names() -> List[str]:
        """Returns feature names used by the model."""
        return [
            'hour_sin',
            'hour_cos',
            'day_sin',
            'day_cos',
            'is_weekend',
            'is_night',
            'is_auth_event',
            'is_data_event',
            'is_transfer_event',
            'is_admin_event',
            'is_failure_event',
            'amount_log',
            'sender_tx_count_last_hour_log',
            'sender_tx_count_last_day_log',
            'has_prior_tx',
            'time_since_last_tx_log',
            'is_high_amount',
            'risk_level_encoded',
            'is_failed_attempt',
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Converts to a user-facing dictionary with both raw and transformed values."""
        return {
            'transaction_id': self.transaction_id,
            'hour_of_day': self.hour_of_day,
            'day_of_week': self.day_of_week,
            'hour_sin': round(self.hour_sin, 4),
            'hour_cos': round(self.hour_cos, 4),
            'day_sin': round(self.day_sin, 4),
            'day_cos': round(self.day_cos, 4),
            'is_weekend': self.is_weekend,
            'is_night': self.is_night,
            'is_auth_event': self.is_auth_event,
            'is_data_event': self.is_data_event,
            'is_transfer_event': self.is_transfer_event,
            'is_admin_event': self.is_admin_event,
            'is_failure_event': self.is_failure_event,
            'amount': round(self.amount, 2),
            'amount_log': round(self.amount_log, 4),
            'sender_tx_count_last_hour': self.sender_tx_count_last_hour,
            'sender_tx_count_last_day': self.sender_tx_count_last_day,
            'sender_tx_count_last_hour_log': round(self.sender_tx_count_last_hour_log, 4),
            'sender_tx_count_last_day_log': round(self.sender_tx_count_last_day_log, 4),
            'has_prior_tx': self.has_prior_tx,
            'time_since_last_tx': round(self.time_since_last_tx, 4),
            'time_since_last_tx_log': round(self.time_since_last_tx_log, 4),
            'is_high_amount': self.is_high_amount,
            'risk_level_encoded': self.risk_level_encoded,
            'is_failed_attempt': self.is_failed_attempt,
        }


class FeatureExtractor:
    """Extracts context-aware features from transactions for anomaly detection."""

    RISK_ENCODING = {
        'low': 0,
        'medium': 1,
        'high': 2,
        'critical': 3,
    }

    HIGH_AMOUNT_THRESHOLD = 5000.0

    AUTH_TYPES = {
        TransactionType.LOGIN,
        TransactionType.LOGOUT,
        TransactionType.LOGIN_FAILED,
        TransactionType.ACCESS_GRANTED,
        TransactionType.ACCESS_DENIED,
    }

    DATA_TYPES = {
        TransactionType.DATA_READ,
        TransactionType.DATA_WRITE,
        TransactionType.DATA_DELETE,
        TransactionType.DATA_MODIFY,
    }

    ADMIN_TYPES = {
        TransactionType.CONFIG_CHANGE,
        TransactionType.PERMISSION_CHANGE,
        TransactionType.USER_CREATED,
        TransactionType.USER_DELETED,
    }

    FAILURE_TYPES = {
        TransactionType.LOGIN_FAILED,
        TransactionType.ACCESS_DENIED,
    }

    def _parse_timestamp(self, timestamp: str) -> datetime:
        try:
            return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except Exception:
            return datetime.utcnow()

    def _get_transaction_groups(self, transaction: Transaction) -> Tuple[int, int, int, int, int]:
        tx_type = transaction.transaction_type
        is_auth = 1 if tx_type in self.AUTH_TYPES else 0
        is_data = 1 if tx_type in self.DATA_TYPES else 0
        is_transfer = 1 if tx_type == TransactionType.TRANSFER else 0
        is_admin = 1 if tx_type in self.ADMIN_TYPES else 0
        is_failure = 1 if tx_type in self.FAILURE_TYPES else 0
        return is_auth, is_data, is_transfer, is_admin, is_failure

    def extract_features(
        self,
        transaction: Transaction,
        historical_transactions: List[Transaction] = None,
    ) -> TransactionFeatures:
        """Extracts robust features from a transaction using sender history."""
        historical_transactions = historical_transactions or []
        tx_time = self._parse_timestamp(transaction.timestamp)

        hour_of_day = tx_time.hour
        day_of_week = tx_time.weekday()
        hour_sin = float(np.sin(2 * np.pi * hour_of_day / 24.0))
        hour_cos = float(np.cos(2 * np.pi * hour_of_day / 24.0))
        day_sin = float(np.sin(2 * np.pi * day_of_week / 7.0))
        day_cos = float(np.cos(2 * np.pi * day_of_week / 7.0))
        is_weekend = 1 if day_of_week >= 5 else 0
        is_night = 1 if hour_of_day < 6 else 0

        is_auth_event, is_data_event, is_transfer_event, is_admin_event, is_failure_event = self._get_transaction_groups(transaction)

        amount = 0.0
        if transaction.transaction_type == TransactionType.TRANSFER:
            amount = float(transaction.data.get('amount', 0.0) or 0.0)
        amount_log = float(np.log1p(max(amount, 0.0)))
        is_high_amount = 1 if amount > self.HIGH_AMOUNT_THRESHOLD else 0

        risk_level = str(transaction.metadata.get('risk_level', 'low')).lower()
        risk_level_encoded = self.RISK_ENCODING.get(risk_level, 0)

        is_failed_attempt = 1 if transaction.transaction_type in self.FAILURE_TYPES else 0

        sender_tx_count_last_hour = 0
        sender_tx_count_last_day = 0
        last_tx_time = None
        sender_address = transaction.sender_address
        one_hour_ago = tx_time - timedelta(hours=1)
        one_day_ago = tx_time - timedelta(days=1)

        for hist_tx in historical_transactions:
            if hist_tx.sender_address != sender_address:
                continue

            hist_time = self._parse_timestamp(hist_tx.timestamp)
            if hist_time > tx_time:
                continue

            if hist_time >= one_hour_ago:
                sender_tx_count_last_hour += 1
            if hist_time >= one_day_ago:
                sender_tx_count_last_day += 1
            if last_tx_time is None or hist_time > last_tx_time:
                last_tx_time = hist_time

        has_prior_tx = 1 if last_tx_time is not None else 0
        if last_tx_time is None:
            time_since_last_tx = 0.0
            time_since_last_tx_log = 0.0
        else:
            time_since_last_tx = max(0.0, (tx_time - last_tx_time).total_seconds())
            time_since_last_tx_log = float(np.log1p(time_since_last_tx))

        sender_tx_count_last_hour_log = float(np.log1p(sender_tx_count_last_hour))
        sender_tx_count_last_day_log = float(np.log1p(sender_tx_count_last_day))

        return TransactionFeatures(
            transaction_id=transaction.transaction_id,
            hour_of_day=hour_of_day,
            day_of_week=day_of_week,
            hour_sin=hour_sin,
            hour_cos=hour_cos,
            day_sin=day_sin,
            day_cos=day_cos,
            is_weekend=is_weekend,
            is_night=is_night,
            is_auth_event=is_auth_event,
            is_data_event=is_data_event,
            is_transfer_event=is_transfer_event,
            is_admin_event=is_admin_event,
            is_failure_event=is_failure_event,
            amount=amount,
            amount_log=amount_log,
            sender_tx_count_last_hour=sender_tx_count_last_hour,
            sender_tx_count_last_day=sender_tx_count_last_day,
            sender_tx_count_last_hour_log=sender_tx_count_last_hour_log,
            sender_tx_count_last_day_log=sender_tx_count_last_day_log,
            has_prior_tx=has_prior_tx,
            time_since_last_tx=time_since_last_tx,
            time_since_last_tx_log=time_since_last_tx_log,
            is_high_amount=is_high_amount,
            risk_level_encoded=risk_level_encoded,
            is_failed_attempt=is_failed_attempt,
        )

    def extract_features_batch(self, transactions: List[Transaction]) -> tuple[np.ndarray, List[str]]:
        """Extracts a feature matrix for a chronological batch."""
        if not transactions:
            return np.array([]), []

        sorted_transactions = sorted(transactions, key=lambda tx: tx.timestamp)
        vectors: List[np.ndarray] = []
        transaction_ids: List[str] = []

        for i, tx in enumerate(sorted_transactions):
            features = self.extract_features(tx, sorted_transactions[:i])
            vectors.append(features.to_vector())
            transaction_ids.append(tx.transaction_id)

        return np.array(vectors, dtype=np.float64), transaction_ids

    def normalize_features(self, features: np.ndarray) -> np.ndarray:
        """Retained for compatibility; returns z-score normalized features."""
        if features.size == 0:
            return features
        mean = np.mean(features, axis=0)
        std = np.std(features, axis=0)
        std[std == 0] = 1.0
        return (features - mean) / std

    def get_feature_importance_description(self) -> Dict[str, str]:
        """Returns descriptions for the active model features."""
        return {
            'hour_sin': 'Cyclical hour encoding (sin) for time-of-day behavior.',
            'hour_cos': 'Cyclical hour encoding (cos) for time-of-day behavior.',
            'day_sin': 'Cyclical day-of-week encoding (sin).',
            'day_cos': 'Cyclical day-of-week encoding (cos).',
            'is_weekend': 'Whether the transaction occurred on a weekend.',
            'is_night': 'Whether the transaction occurred during night hours (00:00-05:59).',
            'is_auth_event': 'Authentication-related event flag.',
            'is_data_event': 'Data access/modification event flag.',
            'is_transfer_event': 'Financial transfer event flag.',
            'is_admin_event': 'Administrative/configuration event flag.',
            'is_failure_event': 'Failure or denied event flag.',
            'amount_log': 'Log-scaled transaction amount.',
            'sender_tx_count_last_hour_log': 'Log-scaled sender activity in the last hour.',
            'sender_tx_count_last_day_log': 'Log-scaled sender activity in the last day.',
            'has_prior_tx': 'Whether the sender has prior history before this event.',
            'time_since_last_tx_log': 'Log-scaled time gap since the sender\'s last event.',
            'is_high_amount': 'Whether the amount exceeds the configured high threshold.',
            'risk_level_encoded': 'Risk level encoded from low to critical.',
            'is_failed_attempt': 'Whether the event is a failed login/access attempt.',
        }

