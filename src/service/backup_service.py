"""Snapshot create / list / restore / download use-cases."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

from src.domain.authorization import Principal, Role
from src.domain.errors import InternalError, NotFoundError, ValidationError
from src.utils.snapshot_manager import (
    create_snapshot,
    get_snapshot_path,
    list_snapshots,
    restore_snapshot,
)

logger = logging.getLogger("blockchain_audit")


class BackupService:
    def __init__(
            self,
            snapshot_dir: Path,
            backup_sources: Dict[str, Path],
            snapshot_retention_count: int,
    ):
        self._snapshot_dir = snapshot_dir
        self._backup_sources = backup_sources
        self._retention = snapshot_retention_count

    def list_backups(self, principal: Principal) -> list[dict]:
        principal.require(Role.ADMIN)
        return list_snapshots(self._snapshot_dir)

    def create_backup(self, principal: Principal) -> dict:
        principal.require(Role.ADMIN)
        created_snapshot = create_snapshot(
            self._snapshot_dir,
            self._backup_sources,
            retention_count=self._retention,
        )
        logger.info("Snapshot created by %s: %s", principal.username, created_snapshot["name"])
        return {
            "snapshot_name": created_snapshot["name"],
            "manifest": created_snapshot["manifest"],
            "pruned_snapshots": created_snapshot.get("pruned", []),
        }

    def restore_backup(self, principal: Principal, snapshot_name: str) -> dict:
        principal.require(Role.ADMIN)
        if not snapshot_name:
            raise ValidationError("Field 'snapshot_name' is required")

        pre_restore_snapshot = create_snapshot(
            self._snapshot_dir,
            self._backup_sources,
            retention_count=self._retention,
        )

        try:
            restore_result = restore_snapshot(self._snapshot_dir, snapshot_name, self._backup_sources)
        except FileNotFoundError as exc:
            raise NotFoundError(str(exc), error_code="SNAPSHOT_NOT_FOUND") from exc
        except ValueError as exc:
            raise ValidationError(str(exc), error_code="INVALID_SNAPSHOT") from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception("Snapshot restore failed")
            raise InternalError(f"Restore failed: {exc}", error_code="RESTORE_FAILED") from exc

        logger.warning(
            "Snapshot restored by %s: target=%s pre_restore=%s",
            principal.username,
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

    def get_backup_download_path(self, principal: Principal, snapshot_name: str) -> Path:
        principal.require(Role.ADMIN)
        try:
            return get_snapshot_path(self._snapshot_dir, snapshot_name)
        except FileNotFoundError as exc:
            raise NotFoundError(str(exc), error_code="SNAPSHOT_NOT_FOUND") from exc
        except ValueError as exc:
            raise ValidationError(str(exc), error_code="INVALID_SNAPSHOT") from exc
