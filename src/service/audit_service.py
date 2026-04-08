"""Audit and backup use-cases for integrity, export, and snapshots."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

from src.repository.analyzer_repository import AnalyzerRepository
from src.repository.snapshot_repository import SnapshotRepository
from src.service.exceptions import ServiceError

logger = logging.getLogger("blockchain_audit")


class AuditService:
    def __init__(self, analyzer_repository: AnalyzerRepository, snapshot_repository: SnapshotRepository):
        self.analyzer_repository = analyzer_repository
        self.snapshot_repository = snapshot_repository

    def require_admin(self, role: str) -> None:
        if role != "admin":
            raise ServiceError("Access forbidden. Required: admin", status_code=403, error_code="FORBIDDEN")

    def check_integrity(self) -> dict:
        return self.analyzer_repository.validate_blockchain_integrity()

    def export_audit_log(self, role: str) -> str:
        self.require_admin(role)
        return self.analyzer_repository.export_audit_log()

    def list_backups(self, role: str, snapshot_dir: Path) -> list[dict]:
        self.require_admin(role)
        return self.snapshot_repository.list_snapshots(snapshot_dir)

    def create_backup(
        self,
        role: str,
        requested_by: str,
        snapshot_dir: Path,
        sources: Dict[str, Path],
        retention_count: int,
    ) -> dict:
        self.require_admin(role)
        snapshot = self.snapshot_repository.create_snapshot(snapshot_dir, sources, retention_count=retention_count)
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
        snapshot_dir: Path,
        targets: Dict[str, Path],
        retention_count: int,
    ) -> dict:
        self.require_admin(role)
        if not snapshot_name:
            raise ServiceError("Field 'snapshot_name' is required", status_code=400, error_code="VALIDATION_ERROR")

        pre_restore_snapshot = self.snapshot_repository.create_snapshot(
            snapshot_dir,
            targets,
            retention_count=retention_count,
        )

        try:
            restore_result = self.snapshot_repository.restore_snapshot(snapshot_dir, snapshot_name, targets)
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

    def get_backup_download_path(self, role: str, snapshot_dir: Path, snapshot_name: str) -> Path:
        self.require_admin(role)
        try:
            return self.snapshot_repository.get_snapshot_path(snapshot_dir, snapshot_name)
        except FileNotFoundError as exc:
            raise ServiceError(str(exc), status_code=404, error_code="SNAPSHOT_NOT_FOUND") from exc
        except ValueError as exc:
            raise ServiceError(str(exc), status_code=400, error_code="INVALID_SNAPSHOT") from exc

