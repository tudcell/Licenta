"""Snapshot backup/restore helpers for runtime blockchain state."""

from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


SNAPSHOT_PREFIX = "snapshot_"


def _safe_name(name: str) -> bool:
    return name.startswith(SNAPSHOT_PREFIX) and name.endswith(".zip") and ".." not in name and "/" not in name and "\\" not in name



def get_snapshot_path(snapshot_dir: Path, snapshot_name: str) -> Path:
    if not _safe_name(snapshot_name):
        raise ValueError("Invalid snapshot name")
    archive_path = snapshot_dir / snapshot_name
    if not archive_path.exists() or not archive_path.is_file():
        raise FileNotFoundError(f"Snapshot '{snapshot_name}' not found")
    return archive_path


def list_snapshots(snapshot_dir: Path) -> List[Dict[str, object]]:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    items: List[Dict[str, object]] = []
    for path in sorted(snapshot_dir.glob(f"{SNAPSHOT_PREFIX}*.zip"), key=lambda p: p.stat().st_mtime, reverse=True):
        stat = path.stat()
        items.append(
            {
                "name": path.name,
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            }
        )
    return items


def prune_snapshots(snapshot_dir: Path, keep_count: int) -> List[str]:
    if keep_count < 1:
        raise ValueError("keep_count must be >= 1")

    snapshots = sorted(snapshot_dir.glob(f"{SNAPSHOT_PREFIX}*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    removed: List[str] = []
    for path in snapshots[keep_count:]:
        path.unlink(missing_ok=True)
        removed.append(path.name)
    return removed


def create_snapshot(snapshot_dir: Path, sources: Dict[str, Path], retention_count: int | None = None) -> Dict[str, object]:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    snapshot_name = f"{SNAPSHOT_PREFIX}{timestamp}.zip"
    archive_path = snapshot_dir / snapshot_name

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "entries": {},
    }

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for key, source in sources.items():
            source_path = Path(source)
            if not source_path.exists():
                manifest["entries"][key] = {"exists": False}
                continue

            if source_path.is_dir():
                root_prefix = f"{key}/"
                file_count = 0
                for file_path in source_path.rglob("*"):
                    if file_path.is_file():
                        archive.write(file_path, arcname=f"{root_prefix}{file_path.relative_to(source_path).as_posix()}")
                        file_count += 1
                manifest["entries"][key] = {"exists": True, "type": "dir", "files": file_count}
            else:
                archive.write(source_path, arcname=key)
                manifest["entries"][key] = {"exists": True, "type": "file"}

        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    pruned: List[str] = []
    if retention_count is not None:
        pruned = prune_snapshots(snapshot_dir, retention_count)

    return {
        "name": snapshot_name,
        "path": str(archive_path),
        "manifest": manifest,
        "pruned": pruned,
    }


def restore_snapshot(snapshot_dir: Path, snapshot_name: str, targets: Dict[str, Path]) -> Dict[str, object]:
    archive_path = get_snapshot_path(snapshot_dir, snapshot_name)

    restored: List[str] = []
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        with zipfile.ZipFile(archive_path, "r") as archive:
            for member in archive.namelist():
                member_path = Path(member)
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise ValueError("Snapshot archive contains unsafe paths")
            archive.extractall(temp_path)

        for key, target in targets.items():
            staged = temp_path / key
            target_path = Path(target)

            if not staged.exists():
                continue

            if staged.is_dir():
                if target_path.exists():
                    shutil.rmtree(target_path)
                shutil.copytree(staged, target_path)
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(staged, target_path)
            restored.append(key)

    return {
        "name": snapshot_name,
        "restored": restored,
    }


