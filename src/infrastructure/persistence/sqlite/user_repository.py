"""Persistence for user accounts."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Dict, Optional

from .connection import SqliteConnection


class UserRepository:
    def __init__(self, connection: SqliteConnection):
        self._connection = connection

    def create(self, username: str, password_hash: str, role: str = "viewer", wallet_name: str = None) -> bool:
        with self._connection.open() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO users (username, password_hash, role, wallet_name)
                    VALUES (?, ?, ?, ?)
                    """,
                    (username, password_hash, role, wallet_name),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def get(self, username: str) -> Optional[Dict]:
        with self._connection.open() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ? AND is_active = 1",
                (username,),
            ).fetchone()
            return dict(row) if row else None

    def assign_wallet(self, username: str, wallet_name: str) -> bool:
        with self._connection.open() as conn:
            cursor = conn.execute(
                "UPDATE users SET wallet_name = ? WHERE username = ? AND is_active = 1",
                (wallet_name, username),
            )
            conn.commit()
            return cursor.rowcount > 0

    def update_password_hash(self, username: str, password_hash: str) -> bool:
        with self._connection.open() as conn:
            cursor = conn.execute(
                "UPDATE users SET password_hash = ? WHERE username = ? AND is_active = 1",
                (password_hash, username),
            )
            conn.commit()
            return cursor.rowcount > 0

    def update_last_login(self, username: str) -> None:
        with self._connection.open() as conn:
            conn.execute(
                "UPDATE users SET last_login = ? WHERE username = ?",
                (datetime.now(timezone.utc).isoformat(), username),
            )
            conn.commit()
