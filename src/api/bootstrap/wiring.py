"""Builds and attaches the application's services to the Flask app."""

from __future__ import annotations

import logging
import os
from pathlib import Path

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


def _load_or_create_blockchain(repository: JsonBlockchainRepository, config: BlockchainConfig) -> Blockchain:
    blockchain = repository.load(config)
    return blockchain if blockchain is not None else Blockchain(config)


def build_services(app: Flask, socketio) -> None:
    """Construct domain singletons and services, attaching them to `app`."""
    data_dir = os.environ.get("DATA_DIR", "data")
    os.makedirs(data_dir, exist_ok=True)

    # ---- paths and adapters ---------------------------------------------
    blockchain_dir = os.path.join(data_dir, "blockchain")
    wallets_dir = os.path.join(data_dir, "wallets")
    metadata_db_path = os.environ.get("METADATA_DB", os.path.join(data_dir, "audit_metadata.db"))
    model_path = os.environ.get("ML_MODEL_PATH", os.path.join(data_dir, "ml_model.pkl"))
    snapshot_dir = Path(os.path.join(data_dir, "backups"))

    blockchain_repository = JsonBlockchainRepository(blockchain_dir)
    wallet_repository = JsonWalletRepository(
        wallets_dir=wallets_dir,
        encryption_key=app.config["WALLET_ENCRYPTION_KEY"],
    )
    model_store = PickleModelStore(filepath=model_path)

    sqlite_connection = SqliteConnection(metadata_db_path)
    init_schema(sqlite_connection)
    transaction_index_repo = TransactionIndexRepository(sqlite_connection)
    alert_repo = AlertRepository(sqlite_connection)
    user_repo = UserRepository(sqlite_connection)
    token_repo = TokenBlocklistRepository(sqlite_connection)

    # ---- domain singletons (pure) ---------------------------------------
    blockchain_config = BlockchainConfig(difficulty=3, max_transactions_per_block=50)
    blockchain = _load_or_create_blockchain(blockchain_repository, blockchain_config)
    wallet_manager = WalletManager(repository=wallet_repository)

    detector = model_store.load() or AnomalyDetector()
    if model_store.exists():
        logger.info("ML model loaded from %s", model_store.filepath)

    # ---- analysis sub-services (state shared between them) --------------
    analysis_state = AnalysisState()
    training_service = DetectorTrainingService(detector, min_training_samples=30)
    ingestion_service = TransactionIngestionService(
        blockchain=blockchain,
        blockchain_repo=blockchain_repository,
        detector=detector,
        state=analysis_state,
        training_service=training_service,
        auto_train=False,
    )
    mining_service = MiningAnalysisService(
        blockchain=blockchain,
        blockchain_repo=blockchain_repository,
        state=analysis_state,
    )
    audit_service = TransactionAuditService(
        blockchain=blockchain,
        detector=detector,
        state=analysis_state,
        training_service=training_service,
    )

    snapshot_retention_count = max(
        1,
        int(os.environ.get("SNAPSHOT_RETENTION_COUNT", app.config.get("SNAPSHOT_RETENTION_COUNT", 20))),
    )
    backup_sources = {
        "blockchain": Path(blockchain_dir),
        "wallets": Path(wallets_dir),
        "metadata_db": Path(metadata_db_path),
        "ml_model": Path(model_path),
    }

    event_bus = SocketIOEventBus(socketio)

    # ---- top-level use-case services ------------------------------------
    app.auth_service = AuthService(users=user_repo, tokens=token_repo)
    app.transaction_service = TransactionService(
        wallet_manager=wallet_manager,
        blockchain=blockchain,
        ingestion=ingestion_service,
        audit=audit_service,
        users=user_repo,
        transactions=transaction_index_repo,
        alerts=alert_repo,
        event_bus=event_bus,
    )
    app.wallet_service = WalletService(
        wallet_manager=wallet_manager,
        users=user_repo,
        transactions=transaction_index_repo,
    )
    app.blockchain_service = BlockchainService(
        blockchain=blockchain,
        mining_service=mining_service,
        transactions=transaction_index_repo,
        alerts=alert_repo,
        detector_is_fitted_fn=lambda: detector.is_fitted,
        event_bus=event_bus,
    )
    app.anomaly_service = AnomalyService(
        detector=detector,
        training=training_service,
        audit=audit_service,
        blockchain=blockchain,
        alerts=alert_repo,
        transactions=transaction_index_repo,
        model_store=model_store,
    )
    app.demo_service = DemoService(
        wallet_manager=wallet_manager,
        ingestion=ingestion_service,
        alerts=alert_repo,
        transactions=transaction_index_repo,
    )
    app.integrity_service = IntegrityService(
        blockchain=blockchain,
        detector=detector,
        audit=audit_service,
    )
    app.backup_service = BackupService(
        snapshot_dir=snapshot_dir,
        backup_sources=backup_sources,
        snapshot_retention_count=snapshot_retention_count,
    )

    # ---- lightweight references the seeding/JWT layers still need -------
    app.blockchain = blockchain
    app.wallet_manager = wallet_manager
    app.detector = detector
    app.transaction_index_repo = transaction_index_repo
    app.user_repo = user_repo
    app.token_repo = token_repo
    app.snapshot_retention_count = snapshot_retention_count
