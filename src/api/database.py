"""
SQLite metadata storage for performance and persistence.
Stores transaction index, anomaly alerts, users, and revoked tokens.
"""

import sqlite3
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from src.domain.entities.transaction import Transaction

logger = logging.getLogger('blockchain_audit')


class MetadataStore:
    """SQLite metadata storage for performance and persistence."""

    def __init__(self, db_path: str = "audit_metadata.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _column_exists(self, conn: sqlite3.Connection, table: str, column: str) -> bool:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return any(row[1] == column for row in rows)

    def _init_db(self):
        conn = self._get_connection()
        try:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS transaction_index (
                    transaction_id TEXT PRIMARY KEY,
                    block_index INTEGER,
                    sender_address TEXT NOT NULL,
                    transaction_type TEXT NOT NULL,
                    amount REAL DEFAULT 0,
                    tx_status TEXT DEFAULT 'PENDING',
                    is_flagged INTEGER DEFAULT 0,
                    ml_score REAL,
                    ml_reason TEXT,
                    timestamp TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_tx_sender ON transaction_index(sender_address);
                CREATE INDEX IF NOT EXISTS idx_tx_type ON transaction_index(transaction_type);
                CREATE INDEX IF NOT EXISTS idx_tx_block ON transaction_index(block_index);
                CREATE INDEX IF NOT EXISTS idx_tx_timestamp ON transaction_index(timestamp);
                CREATE INDEX IF NOT EXISTS idx_tx_status ON transaction_index(tx_status);
                CREATE INDEX IF NOT EXISTS idx_tx_flagged ON transaction_index(is_flagged);

                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    severity TEXT DEFAULT 'medium',
                    anomaly_score REAL,
                    confidence REAL,
                    explanation TEXT,
                    is_resolved INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now')),
                    resolved_at TEXT,
                    resolved_by TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_alert_tx ON alerts(transaction_id);
                CREATE INDEX IF NOT EXISTS idx_alert_type ON alerts(alert_type);
                CREATE INDEX IF NOT EXISTS idx_alert_resolved ON alerts(is_resolved);
                CREATE INDEX IF NOT EXISTS idx_alert_severity ON alerts(severity);

                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT DEFAULT 'viewer',
                    wallet_name TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT (datetime('now')),
                    last_login TEXT
                );

                CREATE TABLE IF NOT EXISTS revoked_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    jti TEXT UNIQUE NOT NULL,
                    revoked_at TEXT DEFAULT (datetime('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_revoked_jti ON revoked_tokens(jti);
            ''')

            if not self._column_exists(conn, 'transaction_index', 'tx_status'):
                conn.execute("ALTER TABLE transaction_index ADD COLUMN tx_status TEXT DEFAULT 'PENDING'")
            if not self._column_exists(conn, 'transaction_index', 'is_flagged'):
                conn.execute("ALTER TABLE transaction_index ADD COLUMN is_flagged INTEGER DEFAULT 0")
            if not self._column_exists(conn, 'transaction_index', 'ml_score'):
                conn.execute("ALTER TABLE transaction_index ADD COLUMN ml_score REAL")
            if not self._column_exists(conn, 'transaction_index', 'ml_reason'):
                conn.execute("ALTER TABLE transaction_index ADD COLUMN ml_reason TEXT")

            conn.commit()
            logger.info("SQLite metadata store initialized: %s", self.db_path)
        finally:
            conn.close()

    def index_transaction(
        self,
        tx: Transaction,
        block_index: int = None,
        tx_status: str = 'PENDING',
        is_flagged: bool = False,
        ml_score: float = None,
        ml_reason: str = None,
    ):
        conn = self._get_connection()
        try:
            existing = conn.execute(
                "SELECT ml_score, ml_reason FROM transaction_index WHERE transaction_id = ?",
                (tx.transaction_id,)
            ).fetchone()
            if ml_score is None and existing is not None:
                ml_score = existing['ml_score']
            if ml_reason is None and existing is not None:
                ml_reason = existing['ml_reason']

            amount = float(tx.data.get('amount', 0)) if tx.data else 0
            conn.execute('''
                INSERT OR REPLACE INTO transaction_index
                    (transaction_id, block_index, sender_address, transaction_type, amount, tx_status, is_flagged, ml_score, ml_reason, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                tx.transaction_id,
                block_index,
                tx.sender_address,
                tx.transaction_type.value,
                amount,
                tx_status,
                1 if is_flagged else 0,
                ml_score,
                ml_reason,
                tx.timestamp
            ))
            conn.commit()
        finally:
            conn.close()

    def update_transaction_state(self, transaction_id: str, block_index: int = None, tx_status: str = None, is_flagged: Optional[bool] = None) -> bool:
        updates = []
        params = []
        if block_index is not None:
            updates.append("block_index = ?")
            params.append(block_index)
        if tx_status is not None:
            updates.append("tx_status = ?")
            params.append(tx_status)
        if is_flagged is not None:
            updates.append("is_flagged = ?")
            params.append(1 if is_flagged else 0)
        if not updates:
            return False

        conn = self._get_connection()
        try:
            params.append(transaction_id)
            cursor = conn.execute(
                f"UPDATE transaction_index SET {', '.join(updates)} WHERE transaction_id = ?",
                params
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def search_transactions(self, sender: str = None, tx_type: str = None, status: str = None,
                            flagged: Optional[bool] = None, page: int = 1, per_page: int = 20) -> Tuple[list, int]:
        conn = self._get_connection()
        try:
            conditions = []
            params = []

            if sender:
                conditions.append("sender_address LIKE ?")
                params.append(f"%{sender}%")
            if tx_type:
                conditions.append("transaction_type = ?")
                params.append(tx_type)
            if status:
                conditions.append("tx_status = ?")
                params.append(status)
            if flagged is not None:
                conditions.append("is_flagged = ?")
                params.append(1 if flagged else 0)

            where_clause = " AND ".join(conditions) if conditions else "1=1"
            count = conn.execute(f"SELECT COUNT(*) FROM transaction_index WHERE {where_clause}", params).fetchone()[0]
            offset = (page - 1) * per_page
            rows = conn.execute(
                f"""SELECT * FROM transaction_index WHERE {where_clause}
                    ORDER BY timestamp DESC LIMIT ? OFFSET ?""",
                params + [per_page, offset]
            ).fetchall()
            return [dict(row) for row in rows], count
        finally:
            conn.close()

    def get_transaction_index(self, transaction_id: str) -> Optional[Dict]:
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM transaction_index WHERE transaction_id = ?",
                (transaction_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


    def save_alert(self, report) -> int:
        conn = self._get_connection()
        try:
            severity = 'medium'
            if report.anomaly_result:
                result = report.anomaly_result
                hard_rule_triggered = bool(getattr(result, 'hard_rule_triggered', False))
                confidence = float(getattr(result, 'confidence', 0.0) or 0.0)
                score = float(getattr(result, 'anomaly_score', 0.0) or 0.0)
                threshold = float(getattr(result, 'threshold', score) or score)
                margin = max(0.0, threshold - score)

                if hard_rule_triggered or confidence >= 0.95 or margin >= 0.20:
                    severity = 'critical'
                elif confidence >= 0.75 or margin >= 0.08:
                    severity = 'high'
                elif confidence >= 0.55 or margin >= 0.03:
                    severity = 'medium'
                else:
                    severity = 'low'
            cursor = conn.execute('''
                INSERT INTO alerts
                    (transaction_id, alert_type, severity, anomaly_score, confidence, explanation)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                report.transaction_id,
                report.overall_status,
                severity,
                float(report.anomaly_result.anomaly_score) if report.anomaly_result else None,
                float(report.anomaly_result.confidence) if report.anomaly_result else None,
                report.anomaly_result.explanation if report.anomaly_result else None
            ))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_alerts(self, page: int = 1, per_page: int = 20, severity: str = None, is_resolved: bool = None) -> Tuple[list, int]:
        conn = self._get_connection()
        try:
            conditions = []
            params = []
            if severity:
                conditions.append("severity = ?")
                params.append(severity)
            if is_resolved is not None:
                conditions.append("is_resolved = ?")
                params.append(1 if is_resolved else 0)
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            count = conn.execute(f"SELECT COUNT(*) FROM alerts WHERE {where_clause}", params).fetchone()[0]
            offset = (page - 1) * per_page
            rows = conn.execute(
                f"""SELECT * FROM alerts WHERE {where_clause}
                    ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                params + [per_page, offset]
            ).fetchall()
            return [dict(row) for row in rows], count
        finally:
            conn.close()

    def resolve_alert(self, alert_id: int, resolved_by: str) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.execute('''
                UPDATE alerts SET is_resolved = 1, resolved_at = ?, resolved_by = ?
                WHERE id = ? AND is_resolved = 0
            ''', (datetime.now(timezone.utc).isoformat(), resolved_by, alert_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_alert_stats(self) -> Dict:
        conn = self._get_connection()
        try:
            total = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
            unresolved = conn.execute("SELECT COUNT(*) FROM alerts WHERE is_resolved = 0").fetchone()[0]
            by_severity = {}
            for row in conn.execute("SELECT severity, COUNT(*) as cnt FROM alerts GROUP BY severity").fetchall():
                by_severity[row['severity']] = row['cnt']
            return {'total_alerts': total, 'unresolved': unresolved, 'by_severity': by_severity}
        finally:
            conn.close()

    def create_user(self, username: str, password_hash: str, role: str = 'viewer', wallet_name: str = None) -> bool:
        conn = self._get_connection()
        try:
            conn.execute('''
                INSERT INTO users (username, password_hash, role, wallet_name)
                VALUES (?, ?, ?, ?)
            ''', (username, password_hash, role, wallet_name))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def get_user(self, username: str) -> Optional[Dict]:
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ? AND is_active = 1",
                (username,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def assign_wallet_to_user(self, username: str, wallet_name: str) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "UPDATE users SET wallet_name = ? WHERE username = ? AND is_active = 1",
                (wallet_name, username)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def update_password_hash(self, username: str, password_hash: str) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "UPDATE users SET password_hash = ? WHERE username = ? AND is_active = 1",
                (password_hash, username)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def update_last_login(self, username: str):
        conn = self._get_connection()
        try:
            conn.execute(
                "UPDATE users SET last_login = ? WHERE username = ?",
                (datetime.now(timezone.utc).isoformat(), username)
            )
            conn.commit()
        finally:
            conn.close()

    def revoke_token(self, jti: str):
        conn = self._get_connection()
        try:
            conn.execute("INSERT OR IGNORE INTO revoked_tokens (jti) VALUES (?)", (jti,))
            conn.commit()
        finally:
            conn.close()

    def is_token_revoked(self, jti: str) -> bool:
        conn = self._get_connection()
        try:
            row = conn.execute("SELECT 1 FROM revoked_tokens WHERE jti = ?", (jti,)).fetchone()
            return row is not None
        finally:
            conn.close()
