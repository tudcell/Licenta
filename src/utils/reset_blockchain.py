"""
Script to delete all blockchain data and reset the system.
"""

import os
from pathlib import Path


def reset_blockchain():
    """Deletes all blockchain data files."""

    # Get project root directory
    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / "data"

    files_to_delete = [
        "blockchain.json",
        "wallets.json",
        "mempool.json",
        "quarantine.json",
        "alerts.json",
        "audit_log.json"
    ]

    deleted = []

    for filename in files_to_delete:
        filepath = data_dir / filename
        if filepath.exists():
            os.remove(filepath)
            deleted.append(filename)
            print(f"✓ Deleted: {filepath}")

    # Also check for any .json files in data directory
    if data_dir.exists():
        for file in data_dir.glob("*.json"):
            if file.name not in files_to_delete:
                os.remove(file)
                deleted.append(file.name)
                print(f"✓ Deleted: {file}")

    if deleted:
        print(f"\n🗑️ Deleted {len(deleted)} file(s)")
    else:
        print("No blockchain data files found to delete")

    print("✅ Blockchain reset complete!")


if __name__ == "__main__":
    confirm = input("⚠️ This will DELETE ALL blockchain data. Continue? (yes/no): ")
    if confirm.lower() == "yes":
        reset_blockchain()
    else:
        print("Cancelled.")
