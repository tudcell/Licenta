"""Persistence for the searchable transaction index."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from src.domain.entities.transaction import Transaction

from .connection import SqliteConnection


class TransactionIndexRepository:
    def __init__(self, connection: SqliteConnection):
        self._connection = connection

    def index(
        self,
        tx: Transaction,
        block_index: int = None,
        tx_status: str = "PENDING",
        is_flagged: bool = False,
        ml_score: float = None,
        ml_reason: str = None,
    ) -> None:
        with self._connection.open() as conn:
            existing = conn.execute(
                "SELECT ml_score, ml_reason FROM transaction_index WHERE transaction_id = ?",
                (tx.transaction_id,),
            ).fetchone()
            if ml_score is None and existing is not None:
                ml_score = existing["ml_score"]
            if ml_reason is None and existing is not None:
                ml_reason = existing["ml_reason"]

            amount = float(tx.data.get("amount", 0)) if tx.data else 0
            conn.execute(
                """
                INSERT OR REPLACE INTO transaction_index
                    (transaction_id, block_index, sender_address, transaction_type, amount,
                     tx_status, is_flagged, ml_score, ml_reason, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tx.transaction_id,
                    block_index,
                    tx.sender_address,
                    tx.transaction_type.value,
                    amount,
                    tx_status,
                    1 if is_flagged else 0,
                    ml_score,
                    ml_reason,
                    tx.timestamp,
                ),
            )
            conn.commit()

    def update_state(
        self,
        transaction_id: str,
        block_index: int = None,
        tx_status: str = None,
        is_flagged: Optional[bool] = None,
    ) -> bool:
        updates = []
        params: list = []
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

        with self._connection.open() as conn:
            params.append(transaction_id)
            cursor = conn.execute(
                f"UPDATE transaction_index SET {', '.join(updates)} WHERE transaction_id = ?",
                params,
            )
            conn.commit()
            return cursor.rowcount > 0

    def search(
        self,
        sender: str = None,
        tx_type: str = None,
        status: str = None,
        flagged: Optional[bool] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Tuple[list, int]:
        conditions: list[str] = []
        params: list = []

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
        with self._connection.open() as conn:
            count = conn.execute(
                f"SELECT COUNT(*) FROM transaction_index WHERE {where_clause}",
                params,
            ).fetchone()[0]
            offset = (page - 1) * per_page
            rows = conn.execute(
                f"""
                SELECT * FROM transaction_index WHERE {where_clause}
                ORDER BY timestamp DESC LIMIT ? OFFSET ?
                """,
                params + [per_page, offset],
            ).fetchall()
            return [dict(row) for row in rows], count

    def get(self, transaction_id: str) -> Optional[Dict]:
        with self._connection.open() as conn:
            row = conn.execute(
                "SELECT * FROM transaction_index WHERE transaction_id = ?",
                (transaction_id,),
            ).fetchone()
            return dict(row) if row else None
