import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { PageShell } from "../../../components/common/PageShell";
import { SeverityBadge } from "../../../components/common/SeverityBadge";
import { EmptyState } from "../../../components/states/EmptyState";
import { ErrorState } from "../../../components/states/ErrorState";
import { LoadingState } from "../../../components/states/LoadingState";
import { Alert, AlertDescription, AlertTitle } from "../../../components/ui/alert";
import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../../components/ui/table";
import { alertsService, anomalyService, blockchainService, normalizeApiError, transactionsService } from "../../../services";
import { useAuthStore } from "../../../stores/authStore";
import type { AlertRecord } from "../../../types/alerts";
import type { AnomalyStatsPayload } from "../../../types/anomaly";
import type { BlockchainStats, HealthPayload } from "../../../types/blockchain";
import type { IndexedTransaction } from "../../../types/transactions";

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
      const result = await anomalyService.retrain();
      setActionMessage(`Detector retrained on recent clean window: ${result.training_samples} samples from ${result.matched_transactions} matched indexed transactions.`);
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
    <PageShell title="Dashboard" description="System overview from blockchain, transactions, and anomaly alerts.">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <Card className="bg-gradient-to-b from-card to-card/70">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Chain Height</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold">{data.stats.height}</p>
          </CardContent>
        </Card>
        <Card className="bg-gradient-to-b from-card to-card/70">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Total Transactions</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold">{data.stats.total_transactions}</p>
          </CardContent>
        </Card>
        <Card className="bg-gradient-to-b from-card to-card/70">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Mempool</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold">{data.health.mempool_size}</p>
          </CardContent>
        </Card>
        <Card className="bg-gradient-to-b from-card to-card/70">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Unresolved Alerts</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold">{data.health.alerts_unresolved}</p>
          </CardContent>
        </Card>
        <Card className="bg-gradient-to-b from-card to-card/70">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Detector</CardTitle>
          </CardHeader>
          <CardContent>
            <Badge variant={data.anomaly.analysis.detector_fitted ? "default" : "secondary"}>
              {data.anomaly.analysis.detector_fitted ? "Trained" : "Untrained"}
            </Badge>
          </CardContent>
        </Card>
      </div>

      <div className="flex flex-wrap gap-2 rounded-xl border border-border/70 bg-background/40 p-3">
        <Button asChild>
          <Link to="/transactions">Create transaction</Link>
        </Button>
        <Button asChild variant="outline">
          <Link to="/blockchain">View blockchain</Link>
        </Button>
        <Button asChild variant="outline">
          <Link to="/alerts">Review alerts</Link>
        </Button>
      </div>

      <Card className="border-border/70 bg-card/75">
        <CardHeader>
          <CardTitle>Detector and Demo Controls</CardTitle>
          <p className="text-sm text-muted-foreground">
            Detector status: {data.anomaly.analysis.detector_fitted ? "trained" : "not trained"}
            {data.anomaly.analysis.trained_at
              ? ` (last training: ${new Date(data.anomaly.analysis.trained_at).toLocaleString()})`
              : ""}
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          {actionError ? <ErrorState message={actionError} /> : null}
          {actionMessage ? (
            <Alert>
              <AlertTitle>Action completed</AlertTitle>
              <AlertDescription>{actionMessage}</AlertDescription>
            </Alert>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" disabled={!canManageDetector || trainLoading} onClick={() => void trainWithSynthetic()}>
              {trainLoading ? "Training..." : "Train detector (synthetic)"}
            </Button>
            <Button type="button" variant="outline" disabled={!canManageDetector || trainLoading} onClick={() => void retrainFromBlockchain()}>
              {trainLoading ? "Training..." : "Retrain detector (recent clean window)"}
            </Button>
            <Button type="button" variant="outline" disabled={!canManageDetector || demoLoading} onClick={() => void generateDemoData()}>
              {demoLoading ? "Generating..." : "Generate demo data"}
            </Button>
          </div>
          {!canManageDetector ? (
            <p className="text-sm text-muted-foreground">Only admin/operator can train detector or generate demo data.</p>
          ) : null}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="border-border/70 bg-card/75">
          <CardHeader>
            <CardTitle>Recent Transactions</CardTitle>
          </CardHeader>
          <CardContent>
            {data.recentTransactions.length === 0 ? (
              <EmptyState message="No indexed transactions found." />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Timestamp</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.recentTransactions.map((tx) => (
                    <TableRow key={tx.transaction_id}>
                      <TableCell>
                        <Link to={`/transactions/${tx.transaction_id}`} className="font-medium text-primary hover:underline">
                          {tx.transaction_id.slice(0, 12)}...
                        </Link>
                      </TableCell>
                      <TableCell>{tx.transaction_type}</TableCell>
                      <TableCell>{tx.tx_status}</TableCell>
                      <TableCell>{new Date(tx.timestamp).toLocaleString()}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card className="border-border/70 bg-card/75">
          <CardHeader>
            <CardTitle>Recent Alerts</CardTitle>
          </CardHeader>
          <CardContent>
            {data.recentAlerts.length === 0 ? (
              <EmptyState message="No alerts recorded yet." />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                    <TableHead>Severity</TableHead>
                    <TableHead>Transaction</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.recentAlerts.map((alert) => (
                    <TableRow key={alert.id}>
                      <TableCell>{alert.id}</TableCell>
                      <TableCell><SeverityBadge severity={alert.severity} /></TableCell>
                      <TableCell>
                        <Link to={`/transactions/${alert.transaction_id}`} className="font-medium text-primary hover:underline">
                          {alert.transaction_id.slice(0, 12)}...
                        </Link>
                      </TableCell>
                      <TableCell>{alert.is_resolved ? "Resolved" : "Open"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </PageShell>
  );
}

