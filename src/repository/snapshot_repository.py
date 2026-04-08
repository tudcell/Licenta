"""Repository adapter for snapshot persistence operations."""

from __future__ import annotations

from pathlib import Path

from src.utils.snapshot_manager import create_snapshot, get_snapshot_path, list_snapshots, restore_snapshot


class SnapshotRepository:
    def list_snapshots(self, snapshot_dir: Path) -> list[dict]:
        return list_snapshots(snapshot_dir)

    def create_snapshot(self, snapshot_dir: Path, sources: dict[str, Path], retention_count: int) -> dict:
        return create_snapshot(snapshot_dir, sources, retention_count=retention_count)

    def restore_snapshot(self, snapshot_dir: Path, snapshot_name: str, targets: dict[str, Path]) -> dict:
        return restore_snapshot(snapshot_dir, snapshot_name, targets)

    def get_snapshot_path(self, snapshot_dir: Path, snapshot_name: str) -> Path:
        return get_snapshot_path(snapshot_dir, snapshot_name)

