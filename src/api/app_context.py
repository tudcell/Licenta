"""Typed access helpers for custom Flask app attributes."""

from __future__ import annotations

from typing import Protocol, cast

from flask import current_app

from src.api.database import MetadataStore
from src.domain.entities.blockchain import Blockchain
from src.domain.entities.wallet import WalletManager
from src.service.transaction_analyzer import TransactionAnalyzer
from src.repository.blockchain_repository import BlockchainRepository
from src.repository.metadata_repository import MetadataRepository
from src.repository.model_repository import ModelRepository
from src.repository.snapshot_repository import SnapshotRepository
from src.repository.wallet_repository import WalletRepository
from src.service.anomaly_service import AnomalyService
from src.service.auth_service import AuthService
from src.service.audit_service import AuditService
from src.service.blockchain_service import BlockchainService
from src.service.transaction_service import TransactionService
from src.service.wallet_service import WalletService


class AppContext(Protocol):
    """Protocol describing custom attributes attached in create_app()."""

    blockchain: Blockchain
    wallet_manager: WalletManager
    analyzer: TransactionAnalyzer
    metadata_store: MetadataStore
    blockchain_repository: BlockchainRepository
    metadata_repository: MetadataRepository
    model_repository: ModelRepository
    snapshot_repository: SnapshotRepository
    wallet_repository: WalletRepository
    auth_service: AuthService
    anomaly_service: AnomalyService
    audit_service: AuditService
    transaction_service: TransactionService
    wallet_service: WalletService
    blockchain_service: BlockchainService
    ml_model_path: str
    snapshot_retention_count: int


def get_app_ctx() -> AppContext:
    """Return current Flask app cast to the typed protocol for static analysis."""

    return cast(AppContext, cast(object, current_app))

