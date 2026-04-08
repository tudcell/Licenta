"""Repository for metadata database access (transactions, alerts, users, tokens)."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from src.api.database import MetadataStore
from src.domain import Transaction


class MetadataRepository:
    """Persistence-only adapter over SQLite metadata store."""

    def __init__(self, store: MetadataStore):
        self._store = store

    @property
    def db_path(self) -> str:
        return self._store.db_path

    def index_transaction(self, tx: Transaction, block_index: int = None, tx_status: str = 'PENDING', is_flagged: bool = False):
        self._store.index_transaction(tx, block_index=block_index, tx_status=tx_status, is_flagged=is_flagged)

    def update_transaction_state(self, transaction_id: str, block_index: int = None, tx_status: str = None, is_flagged: Optional[bool] = None) -> bool:
        return self._store.update_transaction_state(transaction_id, block_index=block_index, tx_status=tx_status, is_flagged=is_flagged)

    def search_transactions(self, sender: str = None, tx_type: str = None, status: str = None, flagged: Optional[bool] = None, page: int = 1, per_page: int = 20) -> Tuple[list, int]:
        return self._store.search_transactions(sender=sender, tx_type=tx_type, status=status, flagged=flagged, page=page, per_page=per_page)

    def get_transaction_index(self, transaction_id: str) -> Optional[Dict]:
        return self._store.get_transaction_index(transaction_id)

    def save_alert(self, report) -> int:
        return self._store.save_alert(report)

    def get_alerts(self, page: int = 1, per_page: int = 20, severity: str = None, is_resolved: bool = None):
        return self._store.get_alerts(page=page, per_page=per_page, severity=severity, is_resolved=is_resolved)

    def resolve_alert(self, alert_id: int, resolved_by: str) -> bool:
        return self._store.resolve_alert(alert_id, resolved_by)

    def get_alert_stats(self) -> Dict[str, Any]:
        return self._store.get_alert_stats()

    def create_user(self, username: str, password_hash: str, role: str = 'viewer', wallet_name: str = None) -> bool:
        return self._store.create_user(username=username, password_hash=password_hash, role=role, wallet_name=wallet_name)

    def get_user(self, username: str) -> Optional[Dict]:
        return self._store.get_user(username)

    def assign_wallet_to_user(self, username: str, wallet_name: str) -> bool:
        return self._store.assign_wallet_to_user(username, wallet_name)

    def update_password_hash(self, username: str, password_hash: str) -> bool:
        return self._store.update_password_hash(username, password_hash)

    def update_last_login(self, username: str):
        self._store.update_last_login(username)

    def revoke_token(self, jti: str):
        self._store.revoke_token(jti)

    def is_token_revoked(self, jti: str) -> bool:
        return self._store.is_token_revoked(jti)
