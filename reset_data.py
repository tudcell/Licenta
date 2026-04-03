"""
Reset script - Deletes all data and starts fresh with only genesis block.

Usage:
    python reset_data.py

This will delete:
    - data/blockchain/     (all blocks, quarantine)
    - data/wallets/        (all wallet files)
    - data/ml_model.pkl    (trained ML model)
    - data/audit_metadata.db (SQLite database)

After running this, restart the application to create a fresh genesis block.
"""

import os
import shutil


def reset_data():
    """Deletes all data in the data/ folder."""

    data_dir = "data"

    if not os.path.exists(data_dir):
        print("No data folder found. Nothing to delete.")
        return

    # List what will be deleted
    print("The following will be deleted:")
    for root, dirs, files in os.walk(data_dir):
        for name in files:
            filepath = os.path.join(root, name)
            print(f"  - {filepath}")
        for name in dirs:
            dirpath = os.path.join(root, name)
            print(f"  - {dirpath}/")

    print()
    confirm = input("Are you sure you want to delete ALL data? (yes/no): ")

    if confirm.lower() != 'yes':
        print("Cancelled.")
        return

    # Delete contents of data folder
    for item in os.listdir(data_dir):
        item_path = os.path.join(data_dir, item)
        if os.path.isdir(item_path):
            shutil.rmtree(item_path)
            print(f"Deleted folder: {item_path}")
        else:
            os.remove(item_path)
            print(f"Deleted file: {item_path}")

    print()
    print("All data deleted successfully!")
    print("Restart the application to create a fresh genesis block.")


if __name__ == "__main__":
    reset_data()

