"""Builds and attaches the application's services to the Flask app."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from flask import Flask

from src.domain.entities.blockchain import Blockchain, BlockchainConfig
from src.domain.entities.wallet import WalletManager
from src.domain.ml.anomaly_detector import AnomalyDetector
from src.infrastructure.messaging import SocketIOEventBus
from src.infrastructure.persistence import (
    JsonBlockchainRepository,
    JsonWalletRepository,
    PickleModelStore,
)
from src.infrastructure.persistence.sqlite import (
    AlertRepository,
    SqliteConnection,
    TokenBlocklistRepository,
    TransactionIndexRepository,
    UserRepository,
    init_schema,
)
from src.service.analysis_state import AnalysisState
from src.service.anomaly_service import AnomalyService
from src.service.auth_service import AuthService
from src.service.backup_service import BackupService
from src.service.blockchain_service import BlockchainService
from src.service.demo_service import DemoService
from src.service.detector_training_service import DetectorTrainingService
from src.service.integrity_service import IntegrityService
from src.service.mining_analysis_service import MiningAnalysisService
from src.service.transaction_audit_service import TransactionAuditService
from src.service.transaction_ingestion_service import TransactionIngestionService
from src.service.transaction_service import TransactionService
from src.service.wallet_service import WalletService

logger = logging.getLogger("blockchain_audit")


# ---------------------------------------------------------------------------
# Build phase 1: paths
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _Paths:
    data_dir: str
    blockchain_dir: str
    wallets_dir: str
    metadata_db: str
    model: str
    snapshot_dir: Path


def _resolve_paths() -> _Paths:
    data_dir = os.environ.get("DATA_DIR", "data")
    os.makedirs(data_dir, exist_ok=True)
    return _Paths(
        data_dir=data_dir,
        blockchain_dir=os.path.join(data_dir, "blockchain"),
        wallets_dir=os.path.join(data_dir, "wallets"),
        metadata_db=os.environ.get("METADATA_DB", os.path.join(data_dir, "audit_metadata.db")),
        model=os.environ.get("ML_MODEL_PATH", os.path.join(data_dir, "ml_model.pkl")),
        snapshot_dir=Path(os.path.join(data_dir, "backups")),
    )


# ---------------------------------------------------------------------------
# Build phase 2: persistence adapters
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _Adapters:
    blockchain_repo: JsonBlockchainRepository
    wallet_repo: JsonWalletRepository
    model_store: PickleModelStore
    transactions: TransactionIndexRepository
    alerts: AlertRepository
    users: UserRepository
    tokens: TokenBlocklistRepository


def _build_adapters(app: Flask, paths: _Paths) -> _Adapters:
    blockchain_repo = JsonBlockchainRepository(paths.blockchain_dir)
    wallet_repo = JsonWalletRepository(
        wallets_dir=paths.wallets_dir,
        encryption_key=app.config["WALLET_ENCRYPTION_KEY"],
        legacy_keys=app.config.get("WALLET_ENCRYPTION_LEGACY_KEYS", ()),
    )
    model_store = PickleModelStore(filepath=paths.model)

    sqlite_connection = SqliteConnection(paths.metadata_db)
    init_schema(sqlite_connection)

    return _Adapters(
        blockchain_repo=blockchain_repo,
        wallet_repo=wallet_repo,
        model_store=model_store,
        transactions=TransactionIndexRepository(sqlite_connection),
        alerts=AlertRepository(sqlite_connection),
        users=UserRepository(sqlite_connection),
        tokens=TokenBlocklistRepository(sqlite_connection),
    )


# ---------------------------------------------------------------------------
# Build phase 3: domain singletons
# ---------------------------------------------------------------------------
@dataclass
class _Domain:
    blockchain: Blockchain
    wallet_manager: WalletManager
    detector: AnomalyDetector


def _build_domain(adapters: _Adapters) -> _Domain:
    blockchain_config = BlockchainConfig(difficulty=3, max_transactions_per_block=50)
    loaded_chain = adapters.blockchain_repo.load(blockchain_config)
    blockchain = loaded_chain if loaded_chain is not None else Blockchain(blockchain_config)

    wallet_manager = WalletManager(repository=adapters.wallet_repo)

    loaded_detector = adapters.model_store.load()
    if loaded_detector is not None:
        detector = loaded_detector
        logger.info("ML model loaded from %s", adapters.model_store.filepath)
    else:
        detector = AnomalyDetector()

    return _Domain(blockchain=blockchain, wallet_manager=wallet_manager, detector=detector)


# ---------------------------------------------------------------------------
# Build phase 4: analysis sub-services (shared mutable state)
# ---------------------------------------------------------------------------
def _build_analysis(domain: _Domain, adapters: _Adapters) -> Tuple[
    DetectorTrainingService,
    TransactionIngestionService,
    MiningAnalysisService,
    TransactionAuditService,
    AnalysisState,
]:
    state = AnalysisState()
    training = DetectorTrainingService(domain.detector, min_training_samples=30)
    ingestion = TransactionIngestionService(
        blockchain=domain.blockchain,
        blockchain_repo=adapters.blockchain_repo,
        detector=domain.detector,
        state=state,
        training_service=training,
        auto_train=False,
    )
    mining = MiningAnalysisService(
        blockchain=domain.blockchain,
        blockchain_repo=adapters.blockchain_repo,
        state=state,
    )
    audit = TransactionAuditService(
        blockchain=domain.blockchain,
        detector=domain.detector,
        state=state,
        training_service=training,
    )
    return training, ingestion, mining, audit, state


# ---------------------------------------------------------------------------
# Build phase 5: top-level use-case services
# ---------------------------------------------------------------------------
def _attach_services(app: Flask, domain: _Domain, adapters: _Adapters, socketio, paths: _Paths) -> None:
    training, ingestion, mining, audit, _state = _build_analysis(domain, adapters)
    event_bus = SocketIOEventBus(socketio)

    snapshot_retention_count = max(
        1,
        int(os.environ.get("SNAPSHOT_RETENTION_COUNT", app.config.get("SNAPSHOT_RETENTION_COUNT", 20))),
    )
    backup_sources = {
        "blockchain": Path(paths.blockchain_dir),
        "wallets": Path(paths.wallets_dir),
        "metadata_db": Path(paths.metadata_db),
        "ml_model": Path(paths.model),
    }

    app.auth_service = AuthService(users=adapters.users, tokens=adapters.tokens)
    app.transaction_service = TransactionService(
        wallet_manager=domain.wallet_manager,
        blockchain=domain.blockchain,
        ingestion=ingestion,
        audit=audit,
        users=adapters.users,
        transactions=adapters.transactions,
        alerts=adapters.alerts,
        event_bus=event_bus,
    )
    app.wallet_service = WalletService(
        wallet_manager=domain.wallet_manager,
        users=adapters.users,
        transactions=adapters.transactions,
    )
    app.blockchain_service = BlockchainService(
        blockchain=domain.blockchain,
        mining_service=mining,
        transactions=adapters.transactions,
        alerts=adapters.alerts,
        detector_is_fitted_fn=lambda: domain.detector.is_fitted,
        event_bus=event_bus,
    )
    app.anomaly_service = AnomalyService(
        detector=domain.detector,
        training=training,
        audit=audit,
        blockchain=domain.blockchain,
        alerts=adapters.alerts,
        transactions=adapters.transactions,
        model_store=adapters.model_store,
    )
    app.demo_service = DemoService(
        wallet_manager=domain.wallet_manager,
        ingestion=ingestion,
        alerts=adapters.alerts,
        transactions=adapters.transactions,
    )
    app.integrity_service = IntegrityService(
        blockchain=domain.blockchain,
        audit=audit,
        transactions=adapters.transactions,
        alerts=adapters.alerts,
    )
    app.backup_service = BackupService(
        snapshot_dir=paths.snapshot_dir,
        backup_sources=backup_sources,
        snapshot_retention_count=snapshot_retention_count,
    )

    # ---- lightweight references the seeding/JWT layers still need -------
    app.blockchain = domain.blockchain
    app.wallet_manager = domain.wallet_manager
    app.detector = domain.detector
    app.transaction_index_repo = adapters.transactions
    app.user_repo = adapters.users
    app.token_repo = adapters.tokens
    app.snapshot_retention_count = snapshot_retention_count


def build_services(app: Flask, socketio) -> None:
    """Construct domain singletons and services, attaching them to `app`."""
    paths = _resolve_paths()
    adapters = _build_adapters(app, paths)
    domain = _build_domain(adapters)
    _attach_services(app, domain, adapters, socketio, paths)
