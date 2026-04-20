import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { PageShell } from "../../../components/common/PageShell";
import { PaginationBar } from "../../../components/common/PaginationBar";
import { EmptyState } from "../../../components/states/EmptyState";
import { ErrorState } from "../../../components/states/ErrorState";
import { LoadingState } from "../../../components/states/LoadingState";
import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import { Select } from "../../../components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../../components/ui/table";
import { useDebouncedValue } from "../../../hooks/useDebouncedValue";
import { useAlertsSocket } from "../../../hooks/useAlertsSocket";
import { alertsService, normalizeApiError } from "../../../services";
import { useAuthStore } from "../../../stores/authStore";
import type { AlertRecord } from "../../../types/alerts";
import type { PaginationMeta } from "../../../types/api";

export function AlertsPage() {
  const role = useAuthStore((state) => state.user?.role);
  const accessToken = useAuthStore((state) => state.accessToken);
  const canResolve = role === "admin" || role === "operator";

  const [rows, setRows] = useState<AlertRecord[]>([]);
  const [pagination, setPagination] = useState<PaginationMeta | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [severityFilterInput, setSeverityFilterInput] = useState("");
  const [resolvedFilter, setResolvedFilter] = useState("all");
  const severityFilter = useDebouncedValue(severityFilterInput, 350);

  const [actionError, setActionError] = useState<string | null>(null);
  const [resolvingId, setResolvingId] = useState<number | null>(null);

  const severitySuggestions = useCallback(() => {
    const merged = new Set<string>(["low", "medium", "high"]);
    rows.forEach((row) => merged.add(row.severity));
    const query = severityFilterInput.trim().toLowerCase();
    return Array.from(merged)
      .filter((value) => (query ? value.toLowerCase().includes(query) : true))
      .slice(0, 8);
  }, [rows, severityFilterInput]);

  const load = useCallback(async (targetPage = 1, options?: { background?: boolean }) => {
    const background = options?.background ?? false;
    if (background) {
      setRefreshing(true);
    } else {
      setLoading(true);
      setError(null);
    }

    try {
      const resolved = resolvedFilter === "all" ? undefined : resolvedFilter === "true";
      const result = await alertsService.list({
        page: targetPage,
        perPage: 10,
        severity: severityFilter || undefined,
        resolved,
      });
      setRows(result.data.alerts);
      setPagination(result.pagination);
    } catch (loadError) {
      setError(normalizeApiError(loadError).message);
    } finally {
      if (background) {
        setRefreshing(false);
      } else {
        setLoading(false);
      }
    }
  }, [resolvedFilter, severityFilter]);

  useEffect(() => {
    void load(1);
  }, [load]);

  useAlertsSocket(accessToken, {
    onAnomalyDetected: () => {
      void load(pagination?.page ?? 1, { background: true });
    },
    onBlockMined: () => {
      void load(pagination?.page ?? 1, { background: true });
    },
  });

  const onResolve = async (alertId: number) => {
    setResolvingId(alertId);
    setActionError(null);
    try {
      await alertsService.resolve(alertId);
      await load(pagination?.page ?? 1);
    } catch (resolveError) {
      setActionError(normalizeApiError(resolveError).message);
    } finally {
      setResolvingId(null);
    }
  };

  if (loading) {
    return <LoadingState message="Loading alerts..." />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={() => void load()} />;
  }

  return (
    <PageShell title="Alerts" description="Real-time and indexed anomaly alerts.">
      <div className="grid gap-3 md:grid-cols-2">
        <div className="grid gap-2">
          <Label htmlFor="severity">Severity</Label>
          <Input
            id="severity"
            list="alert-severity-suggestions"
            value={severityFilterInput}
            onChange={(event) => setSeverityFilterInput(event.target.value)}
            placeholder="high"
          />
          <datalist id="alert-severity-suggestions">
            {severitySuggestions().map((value) => (
              <option key={value} value={value} />
            ))}
          </datalist>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="resolved">Resolved</Label>
          <Select id="resolved" value={resolvedFilter} onChange={(event) => setResolvedFilter(event.target.value)}>
            <option value="all">All</option>
            <option value="true">Resolved</option>
            <option value="false">Unresolved</option>
          </Select>
        </div>
      </div>

      {actionError ? <ErrorState message={actionError} /> : null}
      {refreshing ? <p className="text-sm text-muted-foreground">Updating alerts...</p> : null}

      {rows.length === 0 ? (
        <EmptyState message="No alerts match current filters." />
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Severity</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Transaction</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((alert) => (
                <TableRow key={alert.id}>
                  <TableCell>{alert.id}</TableCell>
                  <TableCell>
                    <Badge variant={alert.severity.toLowerCase() === "high" ? "destructive" : "secondary"} className="capitalize">
                      {alert.severity}
                    </Badge>
                  </TableCell>
                  <TableCell>{alert.alert_type}</TableCell>
                  <TableCell>
                    <Link to={`/transactions/${alert.transaction_id}`} className="font-medium text-primary hover:underline">
                      {alert.transaction_id.slice(0, 12)}...
                    </Link>
                  </TableCell>
                  <TableCell>
                    <Badge variant={alert.is_resolved ? "secondary" : "outline"}>{alert.is_resolved ? "Resolved" : "Open"}</Badge>
                  </TableCell>
                  <TableCell>
                    {canResolve && !alert.is_resolved ? (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={resolvingId === alert.id}
                        onClick={() => void onResolve(alert.id)}
                      >
                        {resolvingId === alert.id ? "Resolving..." : "Resolve"}
                      </Button>
                    ) : (
                      "-"
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          {pagination ? (
            <PaginationBar
              page={pagination.page}
              totalPages={pagination.total_pages}
              total={pagination.total}
              hasPrevious={pagination.has_prev}
              hasNext={pagination.has_next}
              onPrevious={() => void load(pagination.page - 1)}
              onNext={() => void load(pagination.page + 1)}
            />
          ) : null}
        </>
      )}
    </PageShell>
  );
}

