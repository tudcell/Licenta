"""Reset runtime blockchain and metadata state for a clean local demo."""

from __future__ import annotations

import shutil
from pathlib import Path

from src.utils.snapshot_manager import create_snapshot


RUNTIME_SUBPATHS = [
    "data/blockchain",
    "data/wallets",
    "data/training_wallets",
    "data/demo_wallets",
    "data/ml_model.pkl",
    "data/audit_metadata.db",
]


def reset_blockchain(project_root: Path | None = None) -> None:
    root = project_root or Path(__file__).resolve().parents[2]
    data_dir = root / "data"
    snapshot_dir = data_dir / "backups"

    sources = {
        "blockchain": data_dir / "blockchain",
        "wallets": data_dir / "wallets",
        "metadata_db": data_dir / "audit_metadata.db",
        "ml_model": data_dir / "ml_model.pkl",
    }
    snapshot = create_snapshot(snapshot_dir, sources)
    print(f"📦 Pre-reset snapshot created: {snapshot['name']}")

    removed: list[str] = []

    for relative_path in RUNTIME_SUBPATHS:
        target = root / relative_path
        if not target.exists():
            continue
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        removed.append(relative_path)
        print(f"✓ Removed: {target}")

    data_dir.mkdir(exist_ok=True)

    if removed:
        print(f"\n🗑️ Removed {len(removed)} runtime path(s)")
    else:
        print("No runtime data found to delete")
    print("✅ Reset complete. Start the app again to recreate runtime state.")


if __name__ == "__main__":
    confirm = input("⚠️ This will delete blockchain, wallets, DB, and saved ML model. Continue? (yes/no): ")
    if confirm.strip().lower() == "yes":
        reset_blockchain()
    else:
        print("Cancelled.")
