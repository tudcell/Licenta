"""Persistence for the searchable transaction index."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional, Tuple

from src.domain.entities.transaction import Transaction
from .connection import SqliteConnection


@dataclass(frozen=True)
class TransactionIndexEntry:
    """Typed projection of a `transaction_index` row.

    Booleans are real booleans here; the API layer is responsible for any
    backward-compatible serialization (e.g. emitting `is_flagged` as `1`
    for legacy clients via `to_legacy_dict()`).
    """

    transaction_id: str
    block_index: Optional[int]
    sender_address: str
    transaction_type: str
    amount: float
    tx_status: str
    is_flagged: bool
    ml_score: Optional[float]
    ml_reason: Optional[str]
    timestamp: str
    created_at: Optional[str]

    @classmethod
    def from_row(cls, row) -> "TransactionIndexEntry":
        return cls(
            transaction_id=row["transaction_id"],
            block_index=row["block_index"],
            sender_address=row["sender_address"],
            transaction_type=row["transaction_type"],
            amount=float(row["amount"] or 0.0),
            tx_status=row["tx_status"],
            is_flagged=bool(row["is_flagged"]),
            ml_score=row["ml_score"],
            ml_reason=row["ml_reason"],
            timestamp=row["timestamp"],
            created_at=row["created_at"] if "created_at" in row.keys() else None,
        )

    def to_legacy_dict(self) -> dict:
        """API-shape dict with `is_flagged` as 0/1 for back-compat."""
        out = asdict(self)
        out["is_flagged"] = 1 if self.is_flagged else 0
        return out


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
            transaction_id: Optional[str] = None,
            page: int = 1,
            per_page: int = 20,
    ) -> Tuple[list[TransactionIndexEntry], int]:
        conditions: list[str] = []
        params: list = []

        if transaction_id:
            conditions.append("transaction_id LIKE ?")
            params.append(f"%{transaction_id}%")
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
            return [TransactionIndexEntry.from_row(row) for row in rows], count

    def get(self, transaction_id: str) -> Optional[TransactionIndexEntry]:
        with self._connection.open() as conn:
            row = conn.execute(
                "SELECT * FROM transaction_index WHERE transaction_id = ?",
                (transaction_id,),
            ).fetchone()
            return TransactionIndexEntry.from_row(row) if row else None
