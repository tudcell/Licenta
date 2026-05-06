"""Typed access helpers for custom Flask app attributes."""

from __future__ import annotations

from typing import Protocol, cast

from flask import current_app

from src.infrastructure.persistence import MetadataStore
from src.infrastructure.persistence import PickleModelStore
from src.service.anomaly_service import AnomalyService
from src.service.audit_service import AuditService
from src.service.auth_service import AuthService
from src.service.blockchain_service import BlockchainService
from src.service.transaction_analyzer import TransactionAnalyzer
from src.service.transaction_service import TransactionService
from src.service.wallet_service import WalletService


class AppContext(Protocol):
    """Protocol describing custom attributes attached in create_app()."""

    analyzer: TransactionAnalyzer
    auth_service: AuthService
    anomaly_service: AnomalyService
    audit_service: AuditService
    transaction_service: TransactionService
    wallet_service: WalletService
    blockchain_service: BlockchainService
    metadata_store: MetadataStore
    model_store: PickleModelStore
    snapshot_retention_count: int


def get_app_ctx() -> AppContext:
    return cast(AppContext, cast(object, current_app))
