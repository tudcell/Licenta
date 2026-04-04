export interface IntegrityPayload {
  chain_valid: boolean;
  error: string | null;
  invalid_signatures: string[];
  total_blocks: number;
  total_transactions: number;
}

export interface SnapshotRecord {
  name: string;
  size_bytes: number;
  modified_at: string;
}

export interface BackupListPayload {
  snapshots: SnapshotRecord[];
}

export interface BackupCreatePayload {
  snapshot_name: string;
  manifest: Record<string, unknown>;
  pruned_snapshots: string[];
}

export interface BackupRestorePayload {
  restored_snapshot: string;
  restored_components: string[];
  pre_restore_snapshot: string;
  pruned_snapshots: string[];
  restart_required: boolean;
}

