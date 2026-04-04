import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { EmptyState } from "../../../components/states/EmptyState";
import { ErrorState } from "../../../components/states/ErrorState";
import { LoadingState } from "../../../components/states/LoadingState";
import { useAlertsSocket } from "../../../hooks/useAlertsSocket";
import { alertsService, normalizeApiError } from "../../../services";
import { useAuthStore } from "../../../stores/authStore";
import type { AlertRecord } from "../../../types/alerts";
import type { PaginationMeta } from "../../../types/api";
import "../../../styles/pages/alerts.css";

export function AlertsPage() {
  const role = useAuthStore((state) => state.user?.role);
  const accessToken = useAuthStore((state) => state.accessToken);
  const canResolve = role === "admin" || role === "operator";

  const [rows, setRows] = useState<AlertRecord[]>([]);
  const [pagination, setPagination] = useState<PaginationMeta | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [severityFilter, setSeverityFilter] = useState("");
  const [resolvedFilter, setResolvedFilter] = useState("all");

  const [actionError, setActionError] = useState<string | null>(null);
  const [resolvingId, setResolvingId] = useState<number | null>(null);

  const load = useCallback(async (targetPage = 1) => {
    setLoading(true);
    setError(null);
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
      setLoading(false);
    }
  }, [resolvedFilter, severityFilter]);

  useEffect(() => {
    void load(1);
  }, [load]);

  useAlertsSocket(accessToken, {
    onAnomalyDetected: () => {
      void load(1);
    },
    onBlockMined: () => {
      void load(1);
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
    <section className="page-panel page-alerts">
      <h1>Alerts</h1>

      <div className="filters-grid">
        <label className="field">
          <span>Severity</span>
          <input value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)} placeholder="high" />
        </label>
        <label className="field">
          <span>Resolved</span>
          <select value={resolvedFilter} onChange={(event) => setResolvedFilter(event.target.value)}>
            <option value="all">All</option>
            <option value="true">Resolved</option>
            <option value="false">Unresolved</option>
          </select>
        </label>
      </div>

      {actionError ? <ErrorState message={actionError} /> : null}

      {rows.length === 0 ? (
        <EmptyState message="No alerts match current filters." />
      ) : (
        <>
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Severity</th>
                <th>Type</th>
                <th>Transaction</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((alert) => (
                <tr key={alert.id}>
                  <td>{alert.id}</td>
                  <td>{alert.severity}</td>
                  <td>{alert.alert_type}</td>
                  <td><Link to={`/transactions/${alert.transaction_id}`}>{alert.transaction_id.slice(0, 12)}...</Link></td>
                  <td>{alert.is_resolved ? "Resolved" : "Open"}</td>
                  <td>
                    {canResolve && !alert.is_resolved ? (
                      <button
                        type="button"
                        className="btn btn-secondary"
                        disabled={resolvingId === alert.id}
                        onClick={() => void onResolve(alert.id)}
                      >
                        {resolvingId === alert.id ? "Resolving..." : "Resolve"}
                      </button>
                    ) : (
                      "-"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {pagination ? (
            <div className="pagination-bar">
              <button type="button" className="btn btn-secondary" disabled={!pagination.has_prev} onClick={() => void load(pagination.page - 1)}>Previous</button>
              <span>Page {pagination.page}/{pagination.total_pages}</span>
              <button type="button" className="btn btn-secondary" disabled={!pagination.has_next} onClick={() => void load(pagination.page + 1)}>Next</button>
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}

