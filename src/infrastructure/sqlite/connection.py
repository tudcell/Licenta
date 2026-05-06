"""Shared SQLite connection helper with sane pragmas."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator


class SqliteConnection:
    """Factory that opens short-lived connections with consistent pragmas."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    @contextmanager
    def open(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()
