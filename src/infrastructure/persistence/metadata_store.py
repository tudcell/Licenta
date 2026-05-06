"""Facade combining the focused SQLite repositories.

Kept as a single class on the Flask app for compatibility, but the work is
delegated to the dedicated repositories under
`src.infrastructure.persistence.sqlite`.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from src.domain.entities.transaction import Transaction

from .sqlite import (
    AlertRepository,
    SqliteConnection,
    TokenBlocklistRepository,
    TransactionIndexRepository,
    UserRepository,
    init_schema,
)


class MetadataStore:
    def __init__(self, db_path: str = "audit_metadata.db"):
        self.db_path = db_path
        self._connection = SqliteConnection(db_path)
        init_schema(self._connection)

        self.transaction_index = TransactionIndexRepository(self._connection)
        self.alerts = AlertRepository(self._connection)
        self.users = UserRepository(self._connection)
        self.tokens = TokenBlocklistRepository(self._connection)

    # --- transaction index ---------------------------------------------------
    def index_transaction(self, tx: Transaction, block_index: int = None, tx_status: str = "PENDING",
                          is_flagged: bool = False, ml_score: float = None, ml_reason: str = None) -> None:
        self.transaction_index.index(
            tx,
            block_index=block_index,
            tx_status=tx_status,
            is_flagged=is_flagged,
            ml_score=ml_score,
            ml_reason=ml_reason,
        )

    def update_transaction_state(self, transaction_id: str, block_index: int = None,
                                 tx_status: str = None, is_flagged: Optional[bool] = None) -> bool:
        return self.transaction_index.update_state(
            transaction_id,
            block_index=block_index,
            tx_status=tx_status,
            is_flagged=is_flagged,
        )

    def search_transactions(self, sender: str = None, tx_type: str = None, status: str = None,
                            flagged: Optional[bool] = None, page: int = 1,
                            per_page: int = 20) -> Tuple[list, int]:
        return self.transaction_index.search(
            sender=sender,
            tx_type=tx_type,
            status=status,
            flagged=flagged,
            page=page,
            per_page=per_page,
        )

    def get_transaction_index(self, transaction_id: str) -> Optional[Dict]:
        return self.transaction_index.get(transaction_id)

    # --- alerts --------------------------------------------------------------
    def save_alert(self, report) -> int:
        return self.alerts.save(report)

    def get_alerts(self, page: int = 1, per_page: int = 20, severity: str = None,
                   is_resolved: Optional[bool] = None) -> Tuple[list, int]:
        return self.alerts.list(page=page, per_page=per_page, severity=severity, is_resolved=is_resolved)

    def resolve_alert(self, alert_id: int, resolved_by: str) -> bool:
        return self.alerts.resolve(alert_id, resolved_by)

    def get_alert_stats(self) -> Dict:
        return self.alerts.stats()

    # --- users ---------------------------------------------------------------
    def create_user(self, username: str, password_hash: str, role: str = "viewer",
                    wallet_name: str = None) -> bool:
        return self.users.create(username=username, password_hash=password_hash, role=role, wallet_name=wallet_name)

    def get_user(self, username: str) -> Optional[Dict]:
        return self.users.get(username)

    def assign_wallet_to_user(self, username: str, wallet_name: str) -> bool:
        return self.users.assign_wallet(username, wallet_name)

    def update_password_hash(self, username: str, password_hash: str) -> bool:
        return self.users.update_password_hash(username, password_hash)

    def update_last_login(self, username: str) -> None:
        self.users.update_last_login(username)

    # --- tokens --------------------------------------------------------------
    def revoke_token(self, jti: str) -> None:
        self.tokens.revoke(jti)

    def is_token_revoked(self, jti: str) -> bool:
        return self.tokens.is_revoked(jti)
