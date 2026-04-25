"""Audit and backup use-cases for integrity, export, and snapshots."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

from src.service.exceptions import ServiceError
from src.service.transaction_analyzer import TransactionAnalyzer
from src.utils.snapshot_manager import create_snapshot, get_snapshot_path, list_snapshots, restore_snapshot

logger = logging.getLogger("blockchain_audit")


class AuditService:
    def __init__(
        self,
        analyzer: TransactionAnalyzer,
        snapshot_dir: Path,
        backup_sources: Dict[str, Path],
        snapshot_retention_count: int,
    ):
        self.analyzer = analyzer
        self.snapshot_dir = snapshot_dir
        self.backup_sources = backup_sources
        self.snapshot_retention_count = snapshot_retention_count

    def require_admin(self, role: str) -> None:
        if role != "admin":
            raise ServiceError("Access forbidden. Required: admin", status_code=403, error_code="FORBIDDEN")

    def check_integrity(self) -> dict:
        return self.analyzer.validate_blockchain_integrity()

    def export_audit_log(self, role: str) -> str:
        self.require_admin(role)
        return self.analyzer.export_audit_log()

    def list_backups(self, role: str) -> list[dict]:
        self.require_admin(role)
        return list_snapshots(self.snapshot_dir)

    def create_backup(
        self,
        role: str,
        requested_by: str,
    ) -> dict:
        self.require_admin(role)
        snapshot = create_snapshot(self.snapshot_dir, self.backup_sources, retention_count=self.snapshot_retention_count)
        logger.info("Snapshot created by %s: %s", requested_by, snapshot["name"])
        return {
            "snapshot_name": snapshot["name"],
            "manifest": snapshot["manifest"],
            "pruned_snapshots": snapshot.get("pruned", []),
        }

    def restore_backup(
        self,
        role: str,
        requested_by: str,
        snapshot_name: str,
    ) -> dict:
        self.require_admin(role)
        if not snapshot_name:
            raise ServiceError("Field 'snapshot_name' is required", status_code=400, error_code="VALIDATION_ERROR")

        pre_restore_snapshot = create_snapshot(
            self.snapshot_dir,
            self.backup_sources,
            retention_count=self.snapshot_retention_count,
        )

        try:
            restore_result = restore_snapshot(self.snapshot_dir, snapshot_name, self.backup_sources)
        except FileNotFoundError as exc:
            raise ServiceError(str(exc), status_code=404, error_code="SNAPSHOT_NOT_FOUND") from exc
        except ValueError as exc:
            raise ServiceError(str(exc), status_code=400, error_code="INVALID_SNAPSHOT") from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception("Snapshot restore failed")
            raise ServiceError(f"Restore failed: {exc}", status_code=500, error_code="RESTORE_FAILED") from exc

        logger.warning(
            "Snapshot restored by %s: target=%s pre_restore=%s",
            requested_by,
            snapshot_name,
            pre_restore_snapshot["name"],
        )
        return {
            "restored_snapshot": restore_result["name"],
            "restored_components": restore_result["restored"],
            "pre_restore_snapshot": pre_restore_snapshot["name"],
            "pruned_snapshots": pre_restore_snapshot.get("pruned", []),
            "restart_required": True,
        }

    def get_backup_download_path(self, role: str, snapshot_name: str) -> Path:
        self.require_admin(role)
        try:
            return get_snapshot_path(self.snapshot_dir, snapshot_name)
        except FileNotFoundError as exc:
            raise ServiceError(str(exc), status_code=404, error_code="SNAPSHOT_NOT_FOUND") from exc
        except ValueError as exc:
            raise ServiceError(str(exc), status_code=400, error_code="INVALID_SNAPSHOT") from exc
