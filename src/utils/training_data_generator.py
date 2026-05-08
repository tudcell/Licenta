"""Quality data generation utilities for training and evaluating the anomaly detector."""

import os
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple, Optional

from src.domain.entities.transaction import Transaction, TransactionType
from src.domain.entities.wallet import Wallet, WalletManager
from src.utils.test_factories import TransactionFactory


class _InMemoryWalletRepository:
    """Throwaway wallet store used by training/demo generators.

    Training data lives only for the duration of a fit() call, so the
    wallets it creates don't need disk persistence — and definitely
    don't need to use the production encryption key.
    """

    def __init__(self):
        self._wallets: dict = {}

    def exists(self, name: str) -> bool:
        return name in self._wallets

    def list_names(self):
        return sorted(self._wallets.keys())

    def save(self, wallet: Wallet) -> None:
        self._wallets[wallet.name] = wallet

    def load(self, name: str):
        return self._wallets.get(name)


@dataclass
class UserProfile:
    name: str
    role: str
    department: str
    work_start: int
    work_end: int
    weekend_probability: float
    night_probability: float
    session_ops_range: Tuple[int, int]
    transfer_weights: Tuple[float, float, float, float]
    event_weights: Dict[str, float]
    typical_ip_prefix: str
    is_service_account: bool = False


class TrainingDataGenerator:
    """Generates realistic normal timelines and contextual anomalies."""

    def __init__(self, num_users: int = 20):
        self.wallet_manager = WalletManager(repository=_InMemoryWalletRepository())
        self.users: List[Wallet] = []
        self.user_profiles: Dict[str, UserProfile] = {}

        for i in range(num_users):
            role = random.choices(
                ['employee', 'manager', 'admin', 'service_account'],
                weights=[0.55, 0.20, 0.15, 0.10],
            )[0]
            department = random.choice(['IT', 'HR', 'Finance', 'Sales', 'Operations', 'Security'])
            name = f"train_user_{i:03d}"
            try:
                wallet = self.wallet_manager.create_wallet(name, {'role': role, 'department': department})
            except ValueError:
                wallet = self.wallet_manager.get_wallet(name)
            if wallet:
                self.users.append(wallet)
                self.user_profiles[wallet.address] = self._build_profile(wallet, role, department)

        self.resource_pool = [f"document_{i:03d}" for i in range(1, 151)]
        self.sensitive_resources = [f"confidential_{i:02d}" for i in range(1, 21)]
        self.critical_resources = [f"CRITICAL_SYSTEM_{i}" for i in range(1, 6)]

    def _build_profile(self, wallet: Wallet, role: str, department: str) -> UserProfile:
        if role == 'employee':
            return UserProfile(
                name=wallet.name,
                role=role,
                department=department,
                work_start=random.randint(7, 9),
                work_end=random.randint(16, 18),
                weekend_probability=0.02,
                night_probability=0.005,
                session_ops_range=(3, 8),
                transfer_weights=(0.72, 0.20, 0.07, 0.01),
                event_weights={'transfer': 0.20, 'read': 0.45, 'write': 0.20, 'auth': 0.15},
                typical_ip_prefix=f"192.168.{random.randint(1, 20)}.",
            )
        if role == 'manager':
            return UserProfile(
                name=wallet.name,
                role=role,
                department=department,
                work_start=random.randint(7, 9),
                work_end=random.randint(18, 20),
                weekend_probability=0.05,
                night_probability=0.01,
                session_ops_range=(4, 9),
                transfer_weights=(0.55, 0.25, 0.15, 0.05),
                event_weights={'transfer': 0.30, 'read': 0.30, 'write': 0.20, 'auth': 0.20},
                typical_ip_prefix=f"192.168.{random.randint(21, 40)}.",
            )
        if role == 'admin':
            return UserProfile(
                name=wallet.name,
                role=role,
                department=department,
                work_start=random.randint(6, 9),
                work_end=random.randint(18, 21),
                weekend_probability=0.12,
                night_probability=0.03,
                session_ops_range=(4, 10),
                transfer_weights=(0.65, 0.22, 0.10, 0.03),
                event_weights={'transfer': 0.10, 'read': 0.35, 'write': 0.25, 'auth': 0.20, 'admin': 0.10},
                typical_ip_prefix=f"10.0.{random.randint(1, 10)}.",
            )
        return UserProfile(
            name=wallet.name,
            role=role,
            department=department,
            work_start=0,
            work_end=23,
            weekend_probability=0.25,
            night_probability=0.20,
            session_ops_range=(5, 12),
            transfer_weights=(0.80, 0.16, 0.03, 0.01),
            event_weights={'transfer': 0.05, 'read': 0.55, 'write': 0.25, 'auth': 0.10, 'admin': 0.05},
            typical_ip_prefix=f"172.16.{random.randint(1, 10)}.",
            is_service_account=True,
        )

    def _get_user(self) -> Wallet:
        return random.choice(self.users)

    def _get_profile(self, wallet: Wallet) -> UserProfile:
        return self.user_profiles[wallet.address]

    def _choose_business_day(self, base_date: Optional[datetime] = None, days_back: int = 45,
                             allow_weekend: bool = False) -> datetime:
        base = base_date or datetime.now(timezone.utc)
        for _ in range(200):
            candidate = base - timedelta(days=random.randint(0, days_back))
            if allow_weekend or candidate.weekday() < 5:
                return candidate
        return base

    def _normal_session_start(self, profile: UserProfile, base_date: Optional[datetime] = None) -> datetime:
        now_utc = datetime.now(timezone.utc)
        allow_weekend = random.random() < profile.weekend_probability
        date = self._choose_business_day(base_date=base_date, allow_weekend=allow_weekend)

        if random.random() < profile.night_probability:
            hour = random.choice([0, 1, 2, 3, 4, 5, 22, 23])
        else:
            hour = random.randint(profile.work_start, profile.work_end)

        candidate = date.replace(
            hour=hour,
            minute=random.randint(0, 59),
            second=random.randint(0, 59),
            microsecond=0,
        )
        # Never emit a session start in the future relative to wall-clock now;
        # otherwise demo timestamps would push real user-submitted transactions
        # off the first page.
        if candidate > now_utc:
            candidate = now_utc - timedelta(seconds=random.randint(60, 7200))
        return candidate

    def _sample_amount_for_profile(self, profile: UserProfile) -> float:
        bucket = random.random()
        w_small, w_medium, w_large, w_rare = profile.transfer_weights
        if bucket < w_small:
            return round(random.uniform(20, 300), 2)
        if bucket < w_small + w_medium:
            return round(random.uniform(300, 1500), 2)
        if bucket < w_small + w_medium + w_large:
            return round(random.uniform(1500, 5000), 2)
        return round(random.uniform(5000, 15000), 2)

    def _pick_ip(self, profile: UserProfile, suspicious: bool = False) -> str:
        if suspicious:
            return f"45.{random.randint(1, 254)}.{random.randint(1, 254)}.{random.randint(1, 254)}"
        return f"{profile.typical_ip_prefix}{random.randint(1, 254)}"

    def _sign_transaction(self, tx: Transaction, wallet: Wallet, timestamp: datetime) -> Transaction:
        # Defensive clamp: no demo transaction may carry a timestamp in the
        # future relative to wall-clock UTC. Several anomaly generators build
        # sequences from `datetime.now()` and drift forward; without this
        # clamp those drift past "now" and visually push real user-submitted
        # transactions off the first page of the UI.
        now_utc = datetime.now(timezone.utc)
        if timestamp > now_utc:
            timestamp = now_utc - timedelta(seconds=random.randint(0, 60))
        tx.timestamp = timestamp.isoformat()
        return wallet.sign_transaction(tx)

    def _normal_operation(self, wallet: Wallet, timestamp: datetime) -> Transaction:
        profile = self._get_profile(wallet)
        population = ['transfer', 'read', 'write', 'auth', 'admin']
        weights = [profile.event_weights.get(key, 0.0) for key in population]
        event = random.choices(population, weights=weights, k=1)[0]

        if event == 'transfer':
            recipient = self._get_user()
            while recipient.address == wallet.address:
                recipient = self._get_user()
            tx = TransactionFactory.create_transfer_event(
                sender_address=wallet.address,
                recipient_address=recipient.address,
                amount=self._sample_amount_for_profile(profile),
                currency='RON',
            )
        elif event == 'read':
            tx = TransactionFactory.create_data_access_event(
                user_id=wallet.name,
                sender_address=wallet.address,
                resource_id=random.choice(self.resource_pool),
                action='read',
                success=True,
            )
        elif event == 'write':
            tx = TransactionFactory.create_data_access_event(
                user_id=wallet.name,
                sender_address=wallet.address,
                resource_id=random.choice(self.resource_pool),
                action='write',
                success=True,
            )
        elif event == 'admin' and profile.role in {'admin', 'manager'}:
            tx = Transaction(
                transaction_type=random.choice([TransactionType.CONFIG_CHANGE, TransactionType.PERMISSION_CHANGE]),
                sender_address=wallet.address,
                data={'user_id': wallet.name, 'change_id': f"chg_{random.randint(1000, 9999)}"},
                metadata={'category': 'admin', 'risk_level': 'medium' if profile.role == 'manager' else 'low'},
            )
        else:
            tx = TransactionFactory.create_login_event(
                user_id=wallet.name,
                sender_address=wallet.address,
                ip_address=self._pick_ip(profile),
                user_agent='Mozilla/5.0',
                success=True,
            )

        return self._sign_transaction(tx, wallet, timestamp)

    def _generate_session(self, wallet: Wallet, session_start: datetime) -> List[Transaction]:
        profile = self._get_profile(wallet)
        current_time = session_start
        transactions: List[Transaction] = []

        login = TransactionFactory.create_login_event(
            user_id=wallet.name,
            sender_address=wallet.address,
            ip_address=self._pick_ip(profile),
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            success=True,
        )
        transactions.append(self._sign_transaction(login, wallet, current_time))

        num_operations = random.randint(*profile.session_ops_range)
        for _ in range(num_operations):
            gap_seconds = random.randint(30, 1800 if not profile.is_service_account else 900)
            current_time += timedelta(seconds=gap_seconds)
            transactions.append(self._normal_operation(wallet, current_time))

        current_time += timedelta(seconds=random.randint(10, 300))
        logout = Transaction(
            transaction_type=TransactionType.LOGOUT,
            sender_address=wallet.address,
            data={'user_id': wallet.name, 'session_duration': random.randint(300, 28800)},
            metadata={'category': 'authentication', 'risk_level': 'low'},
        )
        transactions.append(self._sign_transaction(logout, wallet, current_time))
        return transactions

    def _build_recent_history(self, wallet: Wallet, count: int = 12) -> List[Transaction]:
        history: List[Transaction] = []
        session_start = self._normal_session_start(self._get_profile(wallet),
                                                   base_date=datetime.now(timezone.utc) - timedelta(days=7))
        while len(history) < count:
            session = self._generate_session(wallet, session_start)
            history.extend(session)
            session_start += timedelta(hours=random.randint(12, 48))
        history.sort(key=lambda tx: tx.timestamp)
        return history[-count:]

    def generate_normal_transaction(self, timestamp: str = None) -> Transaction:
        wallet = self._get_user()
        profile = self._get_profile(wallet)
        if timestamp is None:
            dt = self._normal_session_start(profile)
        else:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return self._normal_operation(wallet, dt)

    def generate_anomaly_high_amount(self) -> Transaction:
        wallet = self._get_user()
        recipient = self._get_user()
        while recipient.address == wallet.address:
            recipient = self._get_user()
        timestamp = self._normal_session_start(self._get_profile(wallet))
        amount = random.choice([
            random.uniform(20000, 50000),
            random.uniform(50000, 250000),
            random.uniform(250000, 2000000),
        ])
        tx = TransactionFactory.create_transfer_event(wallet.address, recipient.address, round(amount, 2), 'RON')
        tx.metadata['anomaly_type'] = 'high_amount'
        tx.metadata['risk_level'] = 'critical' if amount > 100000 else 'high'
        return self._sign_transaction(tx, wallet, timestamp)

    def generate_anomaly_night_activity(self) -> Transaction:
        wallet = self._get_user()
        base = self._choose_business_day(allow_weekend=True)
        timestamp = base.replace(hour=random.randint(0, 4), minute=random.randint(0, 59), second=random.randint(0, 59),
                                 microsecond=0)
        tx = TransactionFactory.create_data_access_event(
            wallet.name, wallet.address, random.choice(self.sensitive_resources),
            random.choice(['read', 'write', 'delete']), True
        )
        tx.metadata['anomaly_type'] = 'night_activity'
        tx.metadata['risk_level'] = 'high' if tx.transaction_type == TransactionType.DATA_DELETE else 'medium'
        return self._sign_transaction(tx, wallet, timestamp)

    def generate_anomaly_failed_login(self) -> Transaction:
        wallet = self._get_user()
        profile = self._get_profile(wallet)
        timestamp = self._normal_session_start(profile)
        tx = TransactionFactory.create_login_event(
            wallet.name, wallet.address, self._pick_ip(profile, suspicious=True), 'Suspicious-Bot/1.0', success=False
        )
        tx.metadata['anomaly_type'] = 'failed_login'
        tx.metadata['risk_level'] = 'high'
        return self._sign_transaction(tx, wallet, timestamp)

    def generate_anomaly_weekend(self) -> Transaction:
        wallet = self._get_user()
        base = datetime.now(timezone.utc)
        days_until_sat = (5 - base.weekday()) % 7
        weekend = (base + timedelta(days=days_until_sat or 7)) - timedelta(weeks=random.randint(1, 4))
        if random.random() < 0.5:
            weekend += timedelta(days=1)
        timestamp = weekend.replace(hour=random.randint(0, 23), minute=random.randint(0, 59),
                                    second=random.randint(0, 59), microsecond=0)
        tx = TransactionFactory.create_data_access_event(
            wallet.name, wallet.address, random.choice(self.sensitive_resources), random.choice(['read', 'write']), True
        )
        tx.metadata['anomaly_type'] = 'weekend_activity'
        tx.metadata['risk_level'] = 'medium'
        return self._sign_transaction(tx, wallet, timestamp)

    def generate_anomaly_critical_access(self) -> Transaction:
        wallet = self._get_user()
        timestamp = self._normal_session_start(self._get_profile(wallet))
        tx = TransactionFactory.create_data_access_event(
            wallet.name, wallet.address, random.choice(self.critical_resources), 'delete', True
        )
        tx.metadata['risk_level'] = 'critical'
        tx.metadata['anomaly_type'] = 'critical_access'
        return self._sign_transaction(tx, wallet, timestamp)

    def generate_anomaly_burst_sequence(self, wallet: Optional[Wallet] = None, count: int = 12) -> List[Transaction]:
        wallet = wallet or self._get_user()
        recipient = self._get_user()
        while recipient.address == wallet.address:
            recipient = self._get_user()
        # Anchor the burst end at "a few seconds before now" so the entire
        # sequence stays in the past while preserving the rapid 1-3s spacing
        # that defines a burst pattern.
        max_step = 3
        burst_span = count * max_step + 30
        base = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(seconds=burst_span)
        sequence: List[Transaction] = []
        for i in range(count):
            timestamp = base + timedelta(seconds=i * random.choice([1, 2, 3]))
            tx = TransactionFactory.create_transfer_event(wallet.address, recipient.address,
                                                          round(random.uniform(500, 2500), 2), 'RON')
            tx.metadata['anomaly_type'] = 'burst_activity'
            tx.metadata['risk_level'] = 'high'
            tx.metadata['burst_index'] = i
            sequence.append(self._sign_transaction(tx, wallet, timestamp))
        return sequence

    def generate_subtle_anomaly(self) -> Transaction:
        wallet = self._get_user()
        profile = self._get_profile(wallet)
        weekend_bias = profile.role not in {'admin', 'service_account'}
        base = self._normal_session_start(profile)
        if weekend_bias and random.random() < 0.5:
            while base.weekday() < 5:
                base += timedelta(days=1)
        else:
            base = base.replace(hour=min(23, profile.work_end + random.randint(2, 4)))

        recipient = self._get_user()
        while recipient.address == wallet.address:
            recipient = self._get_user()
        tx = TransactionFactory.create_transfer_event(
            wallet.address,
            recipient.address,
            round(random.uniform(8000, 25000), 2),
            'RON',
        )
        tx.metadata['anomaly_type'] = 'subtle_transfer_shift'
        tx.metadata['risk_level'] = 'high'
        return self._sign_transaction(tx, wallet, base)

    def _generate_session_based_normal(self, target_count: int) -> List[Transaction]:
        all_transactions: List[Transaction] = []
        while len(all_transactions) < target_count:
            wallet = self._get_user()
            session_start = self._normal_session_start(self._get_profile(wallet))
            session = self._generate_session(wallet, session_start)
            if len(all_transactions) + len(session) > target_count and all_transactions:
                break
            all_transactions.extend(session)
        all_transactions.sort(key=lambda tx: tx.timestamp)
        return all_transactions

    def generate_only_normal(self, count: int = 800) -> List[Transaction]:
        transactions = self._generate_session_based_normal(count)
        return transactions[:count] if len(transactions) > count + 10 else transactions

    def generate_training_dataset(self, normal_count: int = 800, anomaly_count: int = 60) -> Tuple[
        List[Transaction], List[str]]:
        transactions = list(self.generate_only_normal(normal_count))
        labels = ['normal'] * len(transactions)

        anomaly_generators = [
            ('high_amount', self.generate_anomaly_high_amount),
            ('night_activity', self.generate_anomaly_night_activity),
            ('failed_login', self.generate_anomaly_failed_login),
            ('weekend_activity', self.generate_anomaly_weekend),
            ('critical_access', self.generate_anomaly_critical_access),
            ('subtle_transfer_shift', self.generate_subtle_anomaly),
        ]

        for i in range(anomaly_count):
            label, generator = anomaly_generators[i % len(anomaly_generators)]
            tx = generator()
            transactions.append(tx)
            labels.append(label)

        # add one contextual burst sequence when anomaly_count is large enough
        if anomaly_count >= 12:
            burst_wallet = self._get_user()
            burst_txs = self.generate_anomaly_burst_sequence(burst_wallet, count=min(12, anomaly_count // 2))
            transactions.extend(burst_txs)
            labels.extend(['burst_activity'] * len(burst_txs))

        paired = sorted(zip(transactions, labels), key=lambda x: x[0].timestamp)
        txs, labs = zip(*paired)
        return list(txs), list(labs)

    def generate_evaluation_stream(self, normal_count: int = 600, anomaly_count: int = 50) -> Tuple[
        List[Transaction], List[str]]:
        """Generates a chronological stream with anomalies injected into recent context."""
        transactions = list(self.generate_only_normal(normal_count))
        labels = ['normal'] * len(transactions)

        contextual_sequences: List[Tuple[List[Transaction], List[str]]] = []
        for _ in range(max(1, anomaly_count // 10)):
            wallet = self._get_user()
            history = self._build_recent_history(wallet, count=10)
            burst = self.generate_anomaly_burst_sequence(wallet, count=6)
            contextual_sequences.append((history + burst, ['normal'] * len(history) + ['burst_activity'] * len(burst)))

        anomaly_pool = [
            (self.generate_anomaly_high_amount(), 'high_amount'),
            (self.generate_anomaly_night_activity(), 'night_activity'),
            (self.generate_anomaly_failed_login(), 'failed_login'),
            (self.generate_anomaly_weekend(), 'weekend_activity'),
            (self.generate_anomaly_critical_access(), 'critical_access'),
            (self.generate_subtle_anomaly(), 'subtle_transfer_shift'),
        ]

        while len([l for l in labels if l != 'normal']) < anomaly_count:
            tx, label = random.choice(anomaly_pool)
            transactions.append(tx)
            labels.append(label)
            anomaly_pool = [
                (self.generate_anomaly_high_amount(), 'high_amount'),
                (self.generate_anomaly_night_activity(), 'night_activity'),
                (self.generate_anomaly_failed_login(), 'failed_login'),
                (self.generate_anomaly_weekend(), 'weekend_activity'),
                (self.generate_anomaly_critical_access(), 'critical_access'),
                (self.generate_subtle_anomaly(), 'subtle_transfer_shift'),
            ]

        for seq_txs, seq_labels in contextual_sequences:
            transactions.extend(seq_txs)
            labels.extend(seq_labels)

        paired = sorted(zip(transactions, labels), key=lambda x: x[0].timestamp)
        txs, labs = zip(*paired)
        return list(txs), list(labs)


def train_detector_with_quality_data(detector: 'AnomalyDetector', normal_count: int = 800) -> dict:
    from src.infrastructure.persistence import PickleModelStore

    generator = TrainingDataGenerator(num_users=20)
    transactions = generator.generate_only_normal(count=normal_count)
    detector.fit(transactions)
    data_dir = os.environ.get('DATA_DIR', 'data')
    model_path = os.path.join(data_dir, 'ml_model.pkl')
    PickleModelStore(model_path).save(detector)

    evaluation_transactions, evaluation_labels = generator.generate_evaluation_stream(
        normal_count=max(200, normal_count // 2),
        anomaly_count=max(40, normal_count // 16),
    )
    evaluation = detector.evaluate_dataset(evaluation_transactions, evaluation_labels)

    return {
        'samples': len(transactions),
        'status': 'trained',
        'model_saved': model_path,
        'evaluation': evaluation,
    }


if __name__ == '__main__':
    from src.domain.ml.anomaly_detector import AnomalyDetector

    print('=' * 60)
    print('Training Anomaly Detector with Quality Data')
    print('=' * 60)

    detector = AnomalyDetector(contamination=0.02, n_estimators=300)
    stats = train_detector_with_quality_data(detector, normal_count=800)

    print('\nTraining complete!')
    print(f"Samples: {stats['samples']}")
    print(f"Model saved to: {stats['model_saved']}")
    print('Evaluation:')
    print(f"  f1_score: {stats['evaluation'].get('f1_score', 0.0)}")
    for key, value in stats['evaluation'].items():
        if key == 'f1_score':
            continue
        print(f"  {key}: {value}")
