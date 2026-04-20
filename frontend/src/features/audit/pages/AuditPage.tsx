import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

import { PageShell } from "../../../components/common/PageShell";
import { EmptyState } from "../../../components/states/EmptyState";
import { ErrorState } from "../../../components/states/ErrorState";
import { LoadingState } from "../../../components/states/LoadingState";
import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../../components/ui/table";
import { auditService, normalizeApiError } from "../../../services";
import type { BackupCreatePayload, BackupRestorePayload, IntegrityPayload, SnapshotRecord } from "../../../types/audit";

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
    <PageShell title="Audit" description="Integrity checks, backup lifecycle, and export operations.">
      <Card>
        <CardHeader><CardTitle>Integrity</CardTitle></CardHeader>
        <CardContent>
          {integrity ? (
            <div className="space-y-2 text-sm">
              <p><strong>Chain valid:</strong> <Badge variant={integrity.chain_valid ? "secondary" : "destructive"}>{integrity.chain_valid ? "Yes" : "No"}</Badge></p>
              <p><strong>Total blocks:</strong> {integrity.total_blocks}</p>
              <p><strong>Total transactions:</strong> {integrity.total_transactions}</p>
              {integrity.error ? <p><strong>Error:</strong> {integrity.error}</p> : null}
            </div>
          ) : (
            <EmptyState message="No integrity data available." />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Actions</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" disabled={actionLoading} onClick={() => void load()}>Refresh</Button>
            <Button type="button" disabled={actionLoading} onClick={() => void onCreateBackup()}>Create backup</Button>
            <Button type="button" variant="outline" disabled={actionLoading} onClick={() => void onExportAudit()}>Export audit log</Button>
          </div>
          {actionError ? <ErrorState message={actionError} /> : null}
          {lastCreated ? (
            <Card>
              <CardContent className="space-y-2 pt-6 text-sm">
                <p><strong>Backup created:</strong> {lastCreated.snapshot_name}</p>
                {lastCreated.pruned_snapshots.length > 0 ? <p><strong>Pruned:</strong> {lastCreated.pruned_snapshots.join(", ")}</p> : null}
              </CardContent>
            </Card>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Restore backup</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <form className="space-y-3" onSubmit={(event) => void onRestore(event)}>
            <div className="grid gap-2">
              <Label htmlFor="snapshotName">Snapshot name</Label>
              <Input id="snapshotName" value={restoreName} onChange={(event) => setRestoreName(event.target.value)} placeholder="snapshot_...zip" required />
            </div>
            <Button type="submit" variant="destructive" disabled={actionLoading}>
              {actionLoading ? "Restoring..." : "Restore snapshot"}
            </Button>
          </form>
          {lastRestore ? (
            <Card>
              <CardContent className="space-y-2 pt-6 text-sm">
                <p><strong>Restored:</strong> {lastRestore.restored_snapshot}</p>
                <p><strong>Components:</strong> {lastRestore.restored_components.join(", ")}</p>
                <p><strong>Restart required:</strong> {lastRestore.restart_required ? "Yes" : "No"}</p>
              </CardContent>
            </Card>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Snapshots</CardTitle></CardHeader>
        <CardContent>
          {snapshots.length === 0 ? (
            <EmptyState message="No snapshots available." />
          ) : (
            <Table>
              <TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Size (bytes)</TableHead><TableHead>Modified</TableHead><TableHead>Action</TableHead></TableRow></TableHeader>
              <TableBody>
                {snapshots.map((snapshot) => (
                  <TableRow key={snapshot.name}>
                    <TableCell>{snapshot.name}</TableCell>
                    <TableCell>{snapshot.size_bytes}</TableCell>
                    <TableCell>{new Date(snapshot.modified_at).toLocaleString()}</TableCell>
                    <TableCell>
                      <Button type="button" variant="outline" size="sm" disabled={actionLoading} onClick={() => void onDownloadBackup(snapshot.name)}>
                        Download
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </PageShell>
  );
}

