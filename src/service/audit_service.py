"""Audit service use-cases."""

from __future__ import annotations

from pathlib import Path

from src.repository import MetadataRepository
from src.utils.snapshot_manager import create_snapshot, get_snapshot_path, list_snapshots, restore_snapshot


class AuditService:
    def __init__(
        self,
        blockchain_repository,
        wallet_repository,
        metadata_repository: MetadataRepository,
        analyzer,
        model_path: str,
        snapshot_retention_count: int = 20,
    ):
        self.blockchain_repository = blockchain_repository
        self.wallet_repository = wallet_repository
        self.metadata_repository = metadata_repository
        self.analyzer = analyzer
        self.model_path = model_path
        self.snapshot_retention_count = snapshot_retention_count

    def check_integrity(self):
        return self.analyzer.validate_blockchain_integrity()

    def export_audit(self):
        return self.analyzer.export_audit_log()

    def _snapshot_paths(self):
        data_dir = Path(self.blockchain_repository.blockchain.config.data_dir).parent
        return data_dir / 'backups', {
            'blockchain': Path(self.blockchain_repository.blockchain.config.data_dir),
            'wallets': Path(self.wallet_repository.wallet_manager.wallets_dir),
            'metadata_db': Path(self.metadata_repository.db_path),
            'ml_model': Path(self.model_path),
        }

    def list_backups(self):
        snapshot_dir, _ = self._snapshot_paths()
        return list_snapshots(snapshot_dir)

    def create_backup(self):
        snapshot_dir, sources = self._snapshot_paths()
        return create_snapshot(snapshot_dir=snapshot_dir, sources=sources, retention_count=self.snapshot_retention_count)

    def get_backup_path(self, snapshot_name: str):
        snapshot_dir, _ = self._snapshot_paths()
        return get_snapshot_path(snapshot_dir, snapshot_name).resolve()

    def restore_backup(self, snapshot_name: str):
        snapshot_dir, targets = self._snapshot_paths()
        return restore_snapshot(snapshot_dir=snapshot_dir, targets=targets, snapshot_name=snapshot_name)
