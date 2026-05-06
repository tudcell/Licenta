"""Builds and attaches the application's services to the Flask app."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from flask import Flask

from src.domain.entities.blockchain import Blockchain, BlockchainConfig
from src.domain.entities.wallet import WalletManager
from src.domain.ml.anomaly_detector import AnomalyDetector
from src.infrastructure.metadata_store import MetadataStore
from src.infrastructure.socketio_event_bus import SocketIOEventBus
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
        "ml_model": Path(app.ml_model_path),
    }


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
    app.blockchain = Blockchain(blockchain_config)
    app.wallet_manager = WalletManager(os.path.join(data_dir, "wallets"))
    app.analyzer = TransactionAnalyzer(blockchain=app.blockchain, auto_train=False, min_training_samples=30)
    app.snapshot_retention_count = max(
        1,
        int(os.environ.get("SNAPSHOT_RETENTION_COUNT", app.config.get("SNAPSHOT_RETENTION_COUNT", 20))),
    )
    app.snapshot_dir = os.path.join(data_dir, "backups")

    app.ml_model_path = os.environ.get("ML_MODEL_PATH", os.path.join(data_dir, "ml_model.pkl"))
    if os.path.exists(app.ml_model_path):
        try:
            app.analyzer.detector = AnomalyDetector.load(app.ml_model_path)
            logger.info("ML model loaded from %s", app.ml_model_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not load ML model: %s", exc)

    app.metadata_store = MetadataStore(
        db_path=os.environ.get("METADATA_DB", os.path.join(data_dir, "audit_metadata.db")),
    )

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
        model_path=app.ml_model_path,
    )
    app.audit_service = AuditService(
        analyzer=app.analyzer,
        snapshot_dir=Path(app.snapshot_dir),
        backup_sources=_build_backup_sources(app),
        snapshot_retention_count=app.snapshot_retention_count,
    )
