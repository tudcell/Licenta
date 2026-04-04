"""Typed access helpers for custom Flask app attributes."""

from __future__ import annotations

from typing import Protocol, cast

from flask import current_app

from src.api.database import MetadataStore
from src.blockchain.blockchain import Blockchain
from src.blockchain.wallet import WalletManager
from src.ml.transaction_analyzer import TransactionAnalyzer


class AppContext(Protocol):
    """Protocol describing custom attributes attached in create_app()."""

    blockchain: Blockchain
    wallet_manager: WalletManager
    analyzer: TransactionAnalyzer
    metadata_store: MetadataStore
    ml_model_path: str
    snapshot_retention_count: int


def get_app_ctx() -> AppContext:
    """Return current Flask app cast to the typed protocol for static analysis."""

    return cast(AppContext, cast(object, current_app))

