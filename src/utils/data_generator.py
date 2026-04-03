"""Demo data generator built on the same realistic profiles used for ML training."""

import random
from typing import List, Tuple

from src.blockchain.transaction import Transaction
from src.blockchain.wallet import WalletManager
from src.utils.training_data_generator import TrainingDataGenerator


class DataGenerator:
    """Generates realistic normal traffic and contextual anomalies for demos."""

    ANOMALY_TYPES = [
        'high_amount',
        'night_activity',
        'burst_activity',
        'failed_logins',
        'critical_access',
        'weekend_activity',
        'subtle_transfer_shift',
    ]

    def __init__(self, wallet_manager: WalletManager = None, num_users: int = 10):
        self.training_generator = TrainingDataGenerator(num_users=max(num_users, 12))
        self.wallet_manager = wallet_manager or self.training_generator.wallet_manager
        self.users = self.training_generator.users

    def generate_normal_transaction(self) -> Transaction:
        return self.training_generator.generate_normal_transaction()

    def generate_normal_transactions(self, count: int) -> List[Transaction]:
        transactions = self.training_generator.generate_only_normal(count)
        transactions.sort(key=lambda tx: tx.timestamp)
        return transactions

    def generate_anomaly(self, anomaly_type: str = None) -> Transaction:
        anomaly_type = anomaly_type or random.choice(self.ANOMALY_TYPES)
        if anomaly_type == 'high_amount':
            return self.training_generator.generate_anomaly_high_amount()
        if anomaly_type == 'night_activity':
            return self.training_generator.generate_anomaly_night_activity()
        if anomaly_type == 'failed_logins':
            return self.training_generator.generate_anomaly_failed_login()
        if anomaly_type == 'critical_access':
            return self.training_generator.generate_anomaly_critical_access()
        if anomaly_type == 'weekend_activity':
            return self.training_generator.generate_anomaly_weekend()
        if anomaly_type == 'subtle_transfer_shift':
            return self.training_generator.generate_subtle_anomaly()
        burst = self.training_generator.generate_anomaly_burst_sequence(count=8)
        return burst[0]

    def generate_anomalies(self, count: int) -> List[Transaction]:
        transactions, labels = self.training_generator.generate_evaluation_stream(normal_count=0, anomaly_count=max(count, 10))
        anomalies = [tx for tx, label in zip(transactions, labels) if label != 'normal']
        return anomalies[:count]

    def generate_burst_attack(self, user=None, count: int = 10, interval_seconds: int = 5) -> List[Transaction]:
        del interval_seconds
        wallet = user or self.training_generator._get_user()
        return self.training_generator.generate_anomaly_burst_sequence(wallet=wallet, count=count)

    def generate_brute_force_attack(self, target_user=None, attempts: int = 10) -> List[Transaction]:
        wallet = target_user or self.training_generator._get_user()
        profile = self.training_generator._get_profile(wallet)
        txs = []
        base_history = self.training_generator._build_recent_history(wallet, count=6)
        txs.extend(base_history[-2:])
        for i in range(attempts):
            tx = self.training_generator.generate_anomaly_failed_login()
            tx.sender_address = wallet.address
            tx.data['user_id'] = wallet.name
            tx.data['ip_address'] = self.training_generator._pick_ip(profile, suspicious=True)
            tx.metadata['anomaly_type'] = 'brute_force'
            tx.metadata['attempt_number'] = i + 1
            tx.public_key = wallet.public_key
            tx.sign(wallet.private_key)
            txs.append(tx)
        txs.sort(key=lambda tx: tx.timestamp)
        return txs

    def generate_mixed_dataset(self, normal_count: int = 100, anomaly_percentage: float = 0.1) -> Tuple[List[Transaction], List[str]]:
        anomaly_count = max(1, int(normal_count * anomaly_percentage))
        return self.training_generator.generate_evaluation_stream(normal_count=normal_count, anomaly_count=anomaly_count)
