"""Typed access helpers for custom Flask app attributes."""

from __future__ import annotations

from typing import Protocol, cast

from flask import current_app

from src.infrastructure.persistence import PickleModelStore
from src.infrastructure.persistence.sqlite import (
    TokenBlocklistRepository,
    TransactionIndexRepository,
    UserRepository,
)
from src.service.anomaly_service import AnomalyService
from src.service.auth_service import AuthService
from src.service.backup_service import BackupService
from src.service.blockchain_service import BlockchainService
from src.service.demo_service import DemoService
from src.service.integrity_service import IntegrityService
from src.service.transaction_service import TransactionService
from src.service.wallet_service import WalletService


class AppContext(Protocol):
    """Protocol describing custom attributes attached in create_app()."""

    auth_service: AuthService
    anomaly_service: AnomalyService
    backup_service: BackupService
    blockchain_service: BlockchainService
    demo_service: DemoService
    integrity_service: IntegrityService
    transaction_service: TransactionService
    wallet_service: WalletService
    transaction_index_repo: TransactionIndexRepository
    user_repo: UserRepository
    token_repo: TokenBlocklistRepository
    model_store: PickleModelStore
    snapshot_retention_count: int


def get_app_ctx() -> AppContext:
    return cast(AppContext, cast(object, current_app))
