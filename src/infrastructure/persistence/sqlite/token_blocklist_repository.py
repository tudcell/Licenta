"""Persistence for revoked JWT identifiers."""

from __future__ import annotations

from .connection import SqliteConnection


class TokenBlocklistRepository:
    def __init__(self, connection: SqliteConnection):
        self._connection = connection

    def revoke(self, jti: str) -> None:
        with self._connection.open() as conn:
            conn.execute("INSERT OR IGNORE INTO revoked_tokens (jti) VALUES (?)", (jti,))
            conn.commit()

    def is_revoked(self, jti: str) -> bool:
        with self._connection.open() as conn:
            row = conn.execute("SELECT 1 FROM revoked_tokens WHERE jti = ?", (jti,)).fetchone()
            return row is not None
