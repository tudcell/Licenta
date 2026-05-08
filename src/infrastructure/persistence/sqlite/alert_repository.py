"""Persistence for anomaly alerts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from .connection import SqliteConnection


def _classify_severity(report) -> str:
    if not report.anomaly_result:
        return "medium"
    result = report.anomaly_result
    hard_rule_triggered = bool(getattr(result, "hard_rule_triggered", False))
    confidence = float(getattr(result, "confidence", 0.0) or 0.0)
    score = float(getattr(result, "anomaly_score", 0.0) or 0.0)
    threshold = float(getattr(result, "threshold", score) or score)
    margin = max(0.0, threshold - score)

    if hard_rule_triggered or confidence >= 0.95 or margin >= 0.20:
        return "critical"
    if confidence >= 0.75 or margin >= 0.08:
        return "high"
    if confidence >= 0.55 or margin >= 0.03:
        return "medium"
    return "low"


class AlertRepository:
    def __init__(self, connection: SqliteConnection):
        self._connection = connection

    def save(self, report) -> int:
        severity = _classify_severity(report)
        with self._connection.open() as conn:
            cursor = conn.execute(
                """
                INSERT INTO alerts
                (transaction_id, alert_type, severity, anomaly_score, confidence, explanation)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    report.transaction_id,
                    report.overall_status,
                    severity,
                    float(report.anomaly_result.anomaly_score) if report.anomaly_result else None,
                    float(report.anomaly_result.confidence) if report.anomaly_result else None,
                    report.anomaly_result.explanation if report.anomaly_result else None,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def list(
            self,
            page: int = 1,
            per_page: int = 20,
            severity: str = None,
            is_resolved: Optional[bool] = None,
    ) -> Tuple[list, int]:
        conditions: list[str] = []
        params: list = []
        if severity:
            conditions.append("severity = ?")
            params.append(severity)
        if is_resolved is not None:
            conditions.append("is_resolved = ?")
            params.append(1 if is_resolved else 0)
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        with self._connection.open() as conn:
            count = conn.execute(
                f"SELECT COUNT(*) FROM alerts WHERE {where_clause}",
                params,
            ).fetchone()[0]
            offset = (page - 1) * per_page
            rows = conn.execute(
                f"""
                SELECT * FROM alerts WHERE {where_clause}
                ORDER BY created_at DESC LIMIT ? OFFSET ?
                """,
                params + [per_page, offset],
            ).fetchall()
            return [dict(row) for row in rows], count

    def resolve(self, alert_id: int, resolved_by: str) -> bool:
        with self._connection.open() as conn:
            cursor = conn.execute(
                """
                UPDATE alerts
                SET is_resolved = 1,
                    resolved_at = ?,
                    resolved_by = ?
                WHERE id = ?
                  AND is_resolved = 0
                """,
                (datetime.now(timezone.utc).isoformat(), resolved_by, alert_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def latest_by_transaction_ids(self, transaction_ids: list[str]) -> Dict[str, dict]:
        """Map of transaction_id -> latest alert row, in one query.

        Used by the audit-log export so we don't N+1 query when emitting one
        line per chain transaction.
        """
        if not transaction_ids:
            return {}
        placeholders = ",".join("?" for _ in transaction_ids)
        with self._connection.open() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM alerts
                WHERE transaction_id IN ({placeholders})
                ORDER BY created_at DESC
                """,
                list(transaction_ids),
            ).fetchall()
        latest: Dict[str, dict] = {}
        for row in rows:
            tx_id = row["transaction_id"]
            if tx_id not in latest:
                latest[tx_id] = dict(row)
        return latest

    def stats(self) -> Dict:
        with self._connection.open() as conn:
            total = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
            unresolved = conn.execute("SELECT COUNT(*) FROM alerts WHERE is_resolved = 0").fetchone()[0]
            by_severity = {
                row["severity"]: row["cnt"]
                for row in conn.execute(
                    "SELECT severity, COUNT(*) as cnt FROM alerts GROUP BY severity"
                ).fetchall()
            }
            return {"total_alerts": total, "unresolved": unresolved, "by_severity": by_severity}
