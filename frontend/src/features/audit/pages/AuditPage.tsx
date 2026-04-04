import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

import { EmptyState } from "../../../components/states/EmptyState";
import { ErrorState } from "../../../components/states/ErrorState";
import { LoadingState } from "../../../components/states/LoadingState";
import { auditService, normalizeApiError } from "../../../services";
import type { BackupCreatePayload, BackupRestorePayload, IntegrityPayload, SnapshotRecord } from "../../../types/audit";
import "../../../styles/pages/audit.css";

export function AuditPage() {
  const [integrity, setIntegrity] = useState<IntegrityPayload | null>(null);
  const [snapshots, setSnapshots] = useState<SnapshotRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [lastCreated, setLastCreated] = useState<BackupCreatePayload | null>(null);
  const [lastRestore, setLastRestore] = useState<BackupRestorePayload | null>(null);
  const [restoreName, setRestoreName] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [integrityData, backups] = await Promise.all([
        auditService.getIntegrity(),
        auditService.listBackups(),
      ]);
      setIntegrity(integrityData);
      setSnapshots(backups.snapshots);
    } catch (loadError) {
      setError(normalizeApiError(loadError).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const onCreateBackup = async () => {
    setActionLoading(true);
    setActionError(null);
    try {
      const created = await auditService.createBackup();
      setLastCreated(created);
      await load();
    } catch (actionErr) {
      setActionError(normalizeApiError(actionErr).message);
    } finally {
      setActionLoading(false);
    }
  };

  const onExportAudit = async () => {
    setActionLoading(true);
    setActionError(null);
    try {
      const payload = await auditService.exportAuditLog();
      const blob = new Blob([payload], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "audit_log.json";
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (actionErr) {
      setActionError(normalizeApiError(actionErr).message);
    } finally {
      setActionLoading(false);
    }
  };

  const onDownloadBackup = async (snapshotName: string) => {
    setActionLoading(true);
    setActionError(null);
    try {
      const blob = await auditService.downloadBackup(snapshotName);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = snapshotName;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (actionErr) {
      setActionError(normalizeApiError(actionErr).message);
    } finally {
      setActionLoading(false);
    }
  };

  const onRestore = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const snapshotName = restoreName.trim();
    if (!snapshotName) {
      setActionError("Snapshot name is required.");
      return;
    }

    setActionLoading(true);
    setActionError(null);
    setLastRestore(null);
    try {
      const restored = await auditService.restoreBackup(snapshotName);
      setLastRestore(restored);
      await load();
    } catch (actionErr) {
      setActionError(normalizeApiError(actionErr).message);
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return <LoadingState message="Loading audit data..." />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={() => void load()} />;
  }

  return (
    <section className="page-panel page-audit">
      <h1>Audit</h1>

      <section>
        <h2>Integrity</h2>
        {integrity ? (
          <div className="state-card">
            <p><strong>Chain valid:</strong> {integrity.chain_valid ? "Yes" : "No"}</p>
            <p><strong>Total blocks:</strong> {integrity.total_blocks}</p>
            <p><strong>Total transactions:</strong> {integrity.total_transactions}</p>
            {integrity.error ? <p><strong>Error:</strong> {integrity.error}</p> : null}
          </div>
        ) : (
          <EmptyState message="No integrity data available." />
        )}
      </section>

      <section>
        <h2>Actions</h2>
        <div className="quick-actions">
          <button type="button" className="btn btn-secondary" disabled={actionLoading} onClick={() => void load()}>Refresh</button>
          <button type="button" className="btn btn-primary" disabled={actionLoading} onClick={() => void onCreateBackup()}>Create backup</button>
          <button type="button" className="btn btn-secondary" disabled={actionLoading} onClick={() => void onExportAudit()}>Export audit log</button>
        </div>
        {actionError ? <ErrorState message={actionError} /> : null}
        {lastCreated ? (
          <div className="state-card">
            <p><strong>Backup created:</strong> {lastCreated.snapshot_name}</p>
            {lastCreated.pruned_snapshots.length > 0 ? <p><strong>Pruned:</strong> {lastCreated.pruned_snapshots.join(", ")}</p> : null}
          </div>
        ) : null}
      </section>

      <section>
        <h2>Restore backup</h2>
        <form className="form" onSubmit={(event) => void onRestore(event)}>
          <label className="field">
            <span>Snapshot name</span>
            <input value={restoreName} onChange={(event) => setRestoreName(event.target.value)} placeholder="snapshot_...zip" required />
          </label>
          <button type="submit" className="btn btn-danger" disabled={actionLoading}>
            {actionLoading ? "Restoring..." : "Restore snapshot"}
          </button>
        </form>
        {lastRestore ? (
          <div className="state-card">
            <p><strong>Restored:</strong> {lastRestore.restored_snapshot}</p>
            <p><strong>Components:</strong> {lastRestore.restored_components.join(", ")}</p>
            <p><strong>Restart required:</strong> {lastRestore.restart_required ? "Yes" : "No"}</p>
          </div>
        ) : null}
      </section>

      <section>
        <h2>Snapshots</h2>
        {snapshots.length === 0 ? (
          <EmptyState message="No snapshots available." />
        ) : (
          <table className="data-table">
            <thead><tr><th>Name</th><th>Size (bytes)</th><th>Modified</th><th>Action</th></tr></thead>
            <tbody>
              {snapshots.map((snapshot) => (
                <tr key={snapshot.name}>
                  <td>{snapshot.name}</td>
                  <td>{snapshot.size_bytes}</td>
                  <td>{new Date(snapshot.modified_at).toLocaleString()}</td>
                  <td>
                    <button type="button" className="btn btn-secondary" disabled={actionLoading} onClick={() => void onDownloadBackup(snapshot.name)}>
                      Download
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </section>
  );
}

