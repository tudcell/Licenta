import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { EmptyState } from "../../../components/states/EmptyState";
import { ErrorState } from "../../../components/states/ErrorState";
import { LoadingState } from "../../../components/states/LoadingState";
import { alertsService, anomalyService, blockchainService, normalizeApiError, transactionsService } from "../../../services";
import { useAuthStore } from "../../../stores/authStore";
import type { AlertRecord } from "../../../types/alerts";
import type { AnomalyStatsPayload } from "../../../types/anomaly";
import type { BlockchainStats, HealthPayload } from "../../../types/blockchain";
import type { IndexedTransaction } from "../../../types/transactions";
import "../../../styles/pages/dashboard.css";

interface DashboardData {
  health: HealthPayload;
  stats: BlockchainStats;
  anomaly: AnomalyStatsPayload;
  recentTransactions: IndexedTransaction[];
  recentAlerts: AlertRecord[];
}

export function DashboardPage() {
  const role = useAuthStore((state) => state.user?.role);
  const canManageDetector = role === "admin" || role === "operator";

  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [trainLoading, setTrainLoading] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [health, stats, anomaly, transactions, alerts] = await Promise.all([
        blockchainService.getHealth(),
        blockchainService.getStats(),
        anomalyService.getStats(),
        transactionsService.list({ page: 1, perPage: 5 }),
        alertsService.list({ page: 1, perPage: 5 }),
      ]);

      setData({
        health,
        stats,
        anomaly,
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

  const trainWithSynthetic = async () => {
    setTrainLoading(true);
    setActionError(null);
    setActionMessage(null);
    try {
      const result = await anomalyService.train({ mode: "synthetic", sample_count: 500 });
      setActionMessage(`Detector trained with ${result.training_samples} synthetic samples.`);
      await load();
    } catch (actionLoadError) {
      setActionError(normalizeApiError(actionLoadError).message);
    } finally {
      setTrainLoading(false);
    }
  };

  const retrainFromBlockchain = async () => {
    setTrainLoading(true);
    setActionError(null);
    setActionMessage(null);
    try {
      const result = await anomalyService.train({ mode: "blockchain" });
      setActionMessage(`Detector retrained with ${result.training_samples} blockchain samples.`);
      await load();
    } catch (actionLoadError) {
      setActionError(normalizeApiError(actionLoadError).message);
    } finally {
      setTrainLoading(false);
    }
  };

  const generateDemoData = async () => {
    setDemoLoading(true);
    setActionError(null);
    setActionMessage(null);
    try {
      const result = await anomalyService.generateDemo({ count: 60, include_anomalies: true, anomaly_ratio: 0.2 });
      setActionMessage(`Generated ${result.generated} demo tx (${result.anomalies_detected} suspicious).`);
      await load();
    } catch (actionLoadError) {
      setActionError(normalizeApiError(actionLoadError).message);
    } finally {
      setDemoLoading(false);
    }
  };

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
        <article className="kpi-card">
          <h3>Detector</h3>
          <strong>{data.anomaly.analysis.detector_fitted ? "Trained" : "Untrained"}</strong>
        </article>
      </div>

      <div className="quick-actions">
        <Link to="/transactions" className="btn btn-primary">Create transaction</Link>
        <Link to="/blockchain" className="btn btn-secondary">View blockchain</Link>
        <Link to="/alerts" className="btn btn-secondary">Review alerts</Link>
      </div>

      <section className="dashboard-controls">
        <h2>Detector and Demo Controls</h2>
        <p className="muted">
          Detector status: {data.anomaly.analysis.detector_fitted ? "trained" : "not trained"}
          {data.anomaly.analysis.trained_at ? ` (last training: ${new Date(data.anomaly.analysis.trained_at).toLocaleString()})` : ""}
        </p>
        {actionError ? <ErrorState message={actionError} /> : null}
        {actionMessage ? <p className="dashboard-action-message">{actionMessage}</p> : null}
        <div className="quick-actions">
          <button type="button" className="btn btn-secondary" disabled={!canManageDetector || trainLoading} onClick={() => void trainWithSynthetic()}>
            {trainLoading ? "Training..." : "Train detector (synthetic)"}
          </button>
          <button type="button" className="btn btn-secondary" disabled={!canManageDetector || trainLoading} onClick={() => void retrainFromBlockchain()}>
            {trainLoading ? "Training..." : "Train detector (blockchain)"}
          </button>
          <button type="button" className="btn btn-secondary" disabled={!canManageDetector || demoLoading} onClick={() => void generateDemoData()}>
            {demoLoading ? "Generating..." : "Generate demo data"}
          </button>
        </div>
        {!canManageDetector ? <p className="muted">Only admin/operator can train detector or generate demo data.</p> : null}
      </section>

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

