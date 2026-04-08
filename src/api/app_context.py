"""Typed access helpers for custom Flask app attributes."""

from __future__ import annotations

from typing import Protocol, cast

from flask import current_app

from src.domain import Blockchain, WalletManager, TransactionAnalyzer
from src.repository import BlockchainRepository, MetadataRepository, ModelRepository, WalletRepository
from src.service import (
    AnomalyService,
    AuditService,
    AuthService,
    BlockchainService,
    TransactionService,
    WalletService,
)


class AppContext(Protocol):
    """Protocol describing custom attributes attached in create_app()."""

    blockchain: Blockchain
    wallet_manager: WalletManager
    analyzer: TransactionAnalyzer

    blockchain_repository: BlockchainRepository
    wallet_repository: WalletRepository
    metadata_repository: MetadataRepository
    model_repository: ModelRepository

    auth_service: AuthService
    wallet_service: WalletService
    transaction_service: TransactionService
    blockchain_service: BlockchainService
    anomaly_service: AnomalyService
    audit_service: AuditService

    ml_model_path: str
    snapshot_retention_count: int


def get_app_ctx() -> AppContext:
    """Return current Flask app cast to the typed protocol for static analysis."""

    return cast(AppContext, cast(object, current_app))
