import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { EmptyState } from "../../../components/states/EmptyState";
import { ErrorState } from "../../../components/states/ErrorState";
import { LoadingState } from "../../../components/states/LoadingState";
import { alertsService, blockchainService, normalizeApiError, transactionsService } from "../../../services";
import type { AlertRecord } from "../../../types/alerts";
import type { BlockchainStats, HealthPayload } from "../../../types/blockchain";
import type { IndexedTransaction } from "../../../types/transactions";
import "../../../styles/pages/dashboard.css";

interface DashboardData {
  health: HealthPayload;
  stats: BlockchainStats;
  recentTransactions: IndexedTransaction[];
  recentAlerts: AlertRecord[];
}

export function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [health, stats, transactions, alerts] = await Promise.all([
        blockchainService.getHealth(),
        blockchainService.getStats(),
        transactionsService.list({ page: 1, perPage: 5 }),
        alertsService.list({ page: 1, perPage: 5 }),
      ]);

      setData({
        health,
        stats,
        recentTransactions: transactions.data.transactions,
        recentAlerts: alerts.data.alerts,
      });
    } catch (loadError) {
      setError(normalizeApiError(loadError).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  if (loading) {
    return <LoadingState message="Loading dashboard..." />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={() => void load()} />;
  }

  if (!data) {
    return <EmptyState message="No dashboard data available yet." />;
  }

  return (
    <section className="page-panel page-dashboard">
      <h1>Dashboard</h1>
      <p className="muted">System overview from blockchain, transactions, and anomaly alerts.</p>

      <div className="kpi-grid">
        <article className="kpi-card">
          <h3>Chain Height</h3>
          <strong>{data.stats.height}</strong>
        </article>
        <article className="kpi-card">
          <h3>Total Transactions</h3>
          <strong>{data.stats.total_transactions}</strong>
        </article>
        <article className="kpi-card">
          <h3>Mempool</h3>
          <strong>{data.health.mempool_size}</strong>
        </article>
        <article className="kpi-card">
          <h3>Unresolved Alerts</h3>
          <strong>{data.health.alerts_unresolved}</strong>
        </article>
      </div>

      <div className="quick-actions">
        <Link to="/transactions" className="btn btn-primary">Create transaction</Link>
        <Link to="/blockchain" className="btn btn-secondary">View blockchain</Link>
        <Link to="/alerts" className="btn btn-secondary">Review alerts</Link>
      </div>

      <div className="two-col-grid">
        <section>
          <h2>Recent Transactions</h2>
          {data.recentTransactions.length === 0 ? (
            <EmptyState message="No indexed transactions found." />
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {data.recentTransactions.map((tx) => (
                  <tr key={tx.transaction_id}>
                    <td><Link to={`/transactions/${tx.transaction_id}`}>{tx.transaction_id.slice(0, 12)}...</Link></td>
                    <td>{tx.transaction_type}</td>
                    <td>{tx.tx_status}</td>
                    <td>{new Date(tx.timestamp).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section>
          <h2>Recent Alerts</h2>
          {data.recentAlerts.length === 0 ? (
            <EmptyState message="No alerts recorded yet." />
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Severity</th>
                  <th>Transaction</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.recentAlerts.map((alert) => (
                  <tr key={alert.id}>
                    <td>{alert.id}</td>
                    <td>{alert.severity}</td>
                    <td><Link to={`/transactions/${alert.transaction_id}`}>{alert.transaction_id.slice(0, 12)}...</Link></td>
                    <td>{alert.is_resolved ? "Resolved" : "Open"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>
    </section>
  );
}

