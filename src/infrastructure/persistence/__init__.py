"""Filesystem, pickle, and SQLite adapters live here.

Sub-packages:
    sqlite/   - focused SQLite repositories + connection helper + schema
    json/     - JSON-on-disk adapters for blockchain and wallets

Top-level modules:
    metadata_store.py    - thin facade combining the four sqlite repos
    pickle_model_store.py - pickle adapter for AnomalyDetector state
"""

from .json import JsonBlockchainRepository, JsonWalletRepository
from .metadata_store import MetadataStore
from .pickle_model_store import PickleModelStore

__all__ = [
    "JsonBlockchainRepository",
    "JsonWalletRepository",
    "MetadataStore",
    "PickleModelStore",
]
