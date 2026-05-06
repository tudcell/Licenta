"""JSON-on-disk persistence adapters."""

from .blockchain_repository import JsonBlockchainRepository
from .wallet_repository import JsonWalletRepository

__all__ = ["JsonBlockchainRepository", "JsonWalletRepository"]
