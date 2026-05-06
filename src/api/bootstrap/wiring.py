"""Builds and attaches the application's services to the Flask app."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from flask import Flask

from src.domain.entities.blockchain import Blockchain, BlockchainConfig
from src.domain.entities.wallet import WalletManager
from src.infrastructure.messaging import SocketIOEventBus
from src.infrastructure.persistence import (
    JsonBlockchainRepository,
    JsonWalletRepository,
    MetadataStore,
    PickleModelStore,
)
from src.service.anomaly_service import AnomalyService
from src.service.audit_service import AuditService
from src.service.auth_service import AuthService
from src.service.blockchain_service import BlockchainService
from src.service.transaction_analyzer import TransactionAnalyzer
from src.service.transaction_service import TransactionService
from src.service.wallet_service import WalletService

logger = logging.getLogger("blockchain_audit")


def _build_backup_sources(app: Flask) -> dict:
    return {
        "blockchain": Path(app.blockchain.config.data_dir),
        "wallets": Path(app.wallet_manager.wallets_dir),
        "metadata_db": Path(app.metadata_store.db_path),
        "ml_model": Path(app.model_store.filepath),
    }


def _load_or_create_blockchain(repository: JsonBlockchainRepository, config: BlockchainConfig) -> Blockchain:
    blockchain = repository.load(config)
    if blockchain is not None:
        return blockchain
    return Blockchain(config)


def build_services(app: Flask, socketio) -> None:
    """Construct domain singletons and services, attaching them to `app`."""
    data_dir = os.environ.get("DATA_DIR", "data")
    os.makedirs(data_dir, exist_ok=True)

    blockchain_config = BlockchainConfig(
        difficulty=3,
        max_transactions_per_block=50,
        data_dir=os.path.join(data_dir, "blockchain"),
        auto_save=True,
    )

    # Persistence adapters
    blockchain_repository = JsonBlockchainRepository(blockchain_config.data_dir)
    wallet_repository = JsonWalletRepository(
        wallets_dir=os.path.join(data_dir, "wallets"),
        encryption_key=os.environ.get("WALLET_ENCRYPTION_KEY"),
    )
    model_store = PickleModelStore(
        filepath=os.environ.get("ML_MODEL_PATH", os.path.join(data_dir, "ml_model.pkl"))
    )

    # Domain singletons (pure)
    app.blockchain = _load_or_create_blockchain(blockchain_repository, blockchain_config)
    app.blockchain.set_persist_hook(blockchain_repository.save)

    app.wallet_manager = WalletManager(repository=wallet_repository)

    app.analyzer = TransactionAnalyzer(blockchain=app.blockchain, auto_train=False, min_training_samples=30)

    loaded_detector = model_store.load()
    if loaded_detector is not None:
        app.analyzer.detector = loaded_detector
        logger.info("ML model loaded from %s", model_store.filepath)

    app.snapshot_retention_count = max(
        1,
        int(os.environ.get("SNAPSHOT_RETENTION_COUNT", app.config.get("SNAPSHOT_RETENTION_COUNT", 20))),
    )
    app.snapshot_dir = os.path.join(data_dir, "backups")

    app.metadata_store = MetadataStore(
        db_path=os.environ.get("METADATA_DB", os.path.join(data_dir, "audit_metadata.db")),
    )
    app.model_store = model_store

    event_bus = SocketIOEventBus(socketio)

    app.auth_service = AuthService(metadata_store=app.metadata_store)
    app.transaction_service = TransactionService(
        wallet_manager=app.wallet_manager,
        metadata_store=app.metadata_store,
        analyzer=app.analyzer,
        event_bus=event_bus,
    )
    app.wallet_service = WalletService(wallet_manager=app.wallet_manager, metadata_store=app.metadata_store)
    app.blockchain_service = BlockchainService(
        blockchain=app.blockchain,
        analyzer=app.analyzer,
        metadata_store=app.metadata_store,
        event_bus=event_bus,
    )
    app.anomaly_service = AnomalyService(
        analyzer=app.analyzer,
        blockchain=app.blockchain,
        metadata_store=app.metadata_store,
        wallet_manager=app.wallet_manager,
        model_store=model_store,
    )
    app.audit_service = AuditService(
        analyzer=app.analyzer,
        snapshot_dir=Path(app.snapshot_dir),
        backup_sources=_build_backup_sources(app),
        snapshot_retention_count=app.snapshot_retention_count,
    )
