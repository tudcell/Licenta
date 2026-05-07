"""Schema bootstrap and lightweight column-add migrations."""

from __future__ import annotations

import logging

from .connection import SqliteConnection

logger = logging.getLogger("blockchain_audit")

_SCHEMA = """
          CREATE TABLE IF NOT EXISTS transaction_index
          (
              transaction_id
              TEXT
              PRIMARY
              KEY,
              block_index
              INTEGER,
              sender_address
              TEXT
              NOT
              NULL,
              transaction_type
              TEXT
              NOT
              NULL,
              amount
              REAL
              DEFAULT
              0,
              tx_status
              TEXT
              DEFAULT
              'PENDING',
              is_flagged
              INTEGER
              DEFAULT
              0,
              ml_score
              REAL,
              ml_reason
              TEXT,
              timestamp
              TEXT
              NOT
              NULL,
              created_at
              TEXT
              DEFAULT (
              datetime
          (
              'now'
          ))
              );

          CREATE INDEX IF NOT EXISTS idx_tx_sender ON transaction_index(sender_address);
          CREATE INDEX IF NOT EXISTS idx_tx_type ON transaction_index(transaction_type);
          CREATE INDEX IF NOT EXISTS idx_tx_block ON transaction_index(block_index);
          CREATE INDEX IF NOT EXISTS idx_tx_timestamp ON transaction_index(timestamp);
          CREATE INDEX IF NOT EXISTS idx_tx_status ON transaction_index(tx_status);
          CREATE INDEX IF NOT EXISTS idx_tx_flagged ON transaction_index(is_flagged);

          CREATE TABLE IF NOT EXISTS alerts
          (
              id
              INTEGER
              PRIMARY
              KEY
              AUTOINCREMENT,
              transaction_id
              TEXT
              NOT
              NULL,
              alert_type
              TEXT
              NOT
              NULL,
              severity
              TEXT
              DEFAULT
              'medium',
              anomaly_score
              REAL,
              confidence
              REAL,
              explanation
              TEXT,
              is_resolved
              INTEGER
              DEFAULT
              0,
              created_at
              TEXT
              DEFAULT (
              datetime
          (
              'now'
          )),
              resolved_at TEXT,
              resolved_by TEXT
              );

          CREATE INDEX IF NOT EXISTS idx_alert_tx ON alerts(transaction_id);
          CREATE INDEX IF NOT EXISTS idx_alert_type ON alerts(alert_type);
          CREATE INDEX IF NOT EXISTS idx_alert_resolved ON alerts(is_resolved);
          CREATE INDEX IF NOT EXISTS idx_alert_severity ON alerts(severity);

          CREATE TABLE IF NOT EXISTS users
          (
              id
              INTEGER
              PRIMARY
              KEY
              AUTOINCREMENT,
              username
              TEXT
              UNIQUE
              NOT
              NULL,
              password_hash
              TEXT
              NOT
              NULL,
              role
              TEXT
              DEFAULT
              'viewer',
              wallet_name
              TEXT,
              is_active
              INTEGER
              DEFAULT
              1,
              created_at
              TEXT
              DEFAULT (
              datetime
          (
              'now'
          )),
              last_login TEXT
              );

          CREATE TABLE IF NOT EXISTS revoked_tokens
          (
              id
              INTEGER
              PRIMARY
              KEY
              AUTOINCREMENT,
              jti
              TEXT
              UNIQUE
              NOT
              NULL,
              revoked_at
              TEXT
              DEFAULT (
              datetime
          (
              'now'
          ))
              );

          CREATE INDEX IF NOT EXISTS idx_revoked_jti ON revoked_tokens(jti); \
          """

_TX_INDEX_COLUMNS = (
    ("tx_status", "TEXT DEFAULT 'PENDING'"),
    ("is_flagged", "INTEGER DEFAULT 0"),
    ("ml_score", "REAL"),
    ("ml_reason", "TEXT"),
)


def init_schema(connection: SqliteConnection) -> None:
    with connection.open() as conn:
        conn.executescript(_SCHEMA)
        existing = {row[1] for row in conn.execute("PRAGMA table_info(transaction_index)").fetchall()}
        for column, definition in _TX_INDEX_COLUMNS:
            if column not in existing:
                conn.execute(f"ALTER TABLE transaction_index ADD COLUMN {column} {definition}")
        conn.commit()
        logger.info("SQLite metadata store initialized: %s", connection.db_path)
