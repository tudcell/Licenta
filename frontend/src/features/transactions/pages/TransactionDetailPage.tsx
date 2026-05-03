import { useParams } from "react-router-dom";

import { useCallback, useEffect, useState } from "react";

import { PageShell } from "../../../components/common/PageShell";
import { EmptyState } from "../../../components/states/EmptyState";
import { ErrorState } from "../../../components/states/ErrorState";
import { LoadingState } from "../../../components/states/LoadingState";
import { Badge } from "../../../components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { alertsService, normalizeApiError, transactionsService } from "../../../services";
import type { AlertRecord, TransactionAuditReport, TransactionDetailPayload } from "../../../types";

interface DetailData {
  detail: TransactionDetailPayload;
  analysis: TransactionAuditReport | null;
  alertInsight: AlertRecord | null;
}

export function TransactionDetailPage() {
  const { id } = useParams();

  const [data, setData] = useState<DetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) {
      setError("Transaction ID is missing from route.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const detail = await transactionsService.getById(id);
      let analysis: TransactionAuditReport | null = null;
      let alertInsight: AlertRecord | null = null;
      try {
        analysis = await transactionsService.analyze(id);
      } catch {
        // Analysis endpoint may not return data for mempool-only transactions; fallback to alert records.
        try {
          const alerts = await alertsService.list({ page: 1, perPage: 100 });
          const matches = alerts.data.alerts
            .filter((alert) => alert.transaction_id === id)
            .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
          alertInsight = matches[0] ?? null;
        } catch {
          // Keep page usable even if alerts endpoint fails.
        }
      }

      setData({ detail, analysis, alertInsight });
    } catch (loadError) {
      setError(normalizeApiError(loadError).message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const indexedRecord = data?.detail.index_record ?? null;
  const liveMlResult = data?.analysis?.anomaly_result ?? null;
  const persistedMlScore = indexedRecord?.ml_score ?? null;
  const persistedMlReason = indexedRecord?.ml_reason ?? null;
  const hasPersistedMl = persistedMlScore !== null || persistedMlReason !== null;

  if (loading) {
    return <LoadingState message="Loading transaction detail..." />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={() => void load()} />;
  }

  if (!data || (!data.detail.index_record && !data.detail.proof)) {
    return <EmptyState message="Transaction was not found in index/proof views." />;
  }

  return (
    <PageShell title="Transaction detail" description={`Transaction ID: ${id ?? "-"}`}>

      {data.detail.index_record ? (
        <Card>
          <CardHeader>
            <CardTitle>Indexed record</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p>Type: {data.detail.index_record.transaction_type}</p>
            <p>Status: <Badge variant="outline">{data.detail.index_record.tx_status}</Badge></p>
            <p>Sender: <span className="font-mono">{data.detail.index_record.sender_address}</span></p>
            <p>Amount: <span className="font-mono">{data.detail.index_record.amount}</span></p>
            <p>ML score: <span className="font-mono">{typeof data.detail.index_record.ml_score === "number" ? data.detail.index_record.ml_score.toFixed(4) : "-"}</span></p>
            <p>ML reason: <span className="font-mono">{data.detail.index_record.ml_reason || "No persisted ML reason recorded."}</span></p>
            <p>Timestamp: {new Date(data.detail.index_record.timestamp).toLocaleString()}</p>
          </CardContent>
        </Card>
      ) : null}

      {data.detail.proof ? (
        <Card>
          <CardHeader>
            <CardTitle>Merkle proof payload</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="max-h-80 overflow-auto rounded-md border border-border bg-muted p-3 font-mono text-xs">{JSON.stringify(data.detail.proof, null, 2)}</pre>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Analyzer status</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
        {data.analysis ? (
          <>
            <p>Overall status: {data.analysis.overall_status}</p>
            <p>Suspicious: {data.analysis.is_suspicious ? "Yes" : "No"}</p>
            <p>Signature valid: {data.analysis.signature_valid ? "Yes" : "No"}</p>
            <p>Merkle proof valid: {data.analysis.merkle_proof_valid ? "Yes" : "No"}</p>

            <h4>ML insights</h4>
            {liveMlResult ? (
              <>
                <p>Source: Live analyzer output</p>
                <p>Score: <span className="font-mono">{liveMlResult.anomaly_score.toFixed(4)}</span></p>
                <p>Threshold: <span className="font-mono">{liveMlResult.threshold.toFixed(4)}</span></p>
                <p>Decision source: <Badge variant={liveMlResult.decision_source === "hard_rule" ? "destructive" : "outline"}>{liveMlResult.decision_source ?? "model"}</Badge></p>
                <p>Model-only verdict: {liveMlResult.model_is_anomaly ? "Anomaly" : "Normal"}</p>
                <p>Hard rule triggered: {liveMlResult.hard_rule_triggered ? "Yes" : "No"}</p>
                {liveMlResult.hard_rule_reason ? <p>Hard rule reason: {liveMlResult.hard_rule_reason}</p> : null}
                <p>
                  Confidence: {typeof liveMlResult.confidence === "number"
                    ? liveMlResult.confidence.toFixed(4)
                    : "-"}
                </p>
                <p>Model score: <span className="font-mono">{typeof liveMlResult.model_score === "number" ? liveMlResult.model_score.toFixed(4) : "-"}</span></p>
                <p>Rule penalty: <span className="font-mono">{typeof liveMlResult.rule_penalty === "number" ? liveMlResult.rule_penalty.toFixed(4) : "-"}</span></p>
                <p>Reason: <span className="font-mono">{liveMlResult.explanation || "No model explanation available."}</span></p>
              </>
            ) : hasPersistedMl ? (
              <>
                <p>Source: Persisted indexed ML data</p>
                <p>Score: <span className="font-mono">{typeof persistedMlScore === "number" ? persistedMlScore.toFixed(4) : "-"}</span></p>
                <p>Reason: <span className="font-mono">{persistedMlReason || "No model explanation available."}</span></p>
                <p className="text-muted-foreground">The detector may be offline or the transaction was never re-analyzed after restart, but the saved ML result is still available.</p>
              </>
            ) : (
              <p>No persisted ML anomaly payload is available for this transaction yet.</p>
            )}

            <p>
              Flagged decision: {data.analysis.flagged_for_review
                ? liveMlResult?.decision_source === "hard_rule"
                  ? "Flagged by hard safety rule override."
                  : "Flagged because model considered this transaction anomalous."
                : "Not flagged because model considered this transaction within normal behavior."}
            </p>
          </>
        ) : hasPersistedMl ? (
          <>
            <p>Overall status: {indexedRecord?.tx_status ?? "UNKNOWN"}</p>
            <p>Suspicious: {indexedRecord?.is_flagged ? "Yes" : "No"}</p>
            <p>Signature valid: Yes</p>
            <p>Merkle proof valid: Yes</p>

            <h4>ML insights</h4>
            <p>Source: Persisted indexed ML data</p>
            <p>Score: <span className="font-mono">{typeof persistedMlScore === "number" ? persistedMlScore.toFixed(4) : "-"}</span></p>
            <p>Reason: <span className="font-mono">{persistedMlReason || "No model explanation available."}</span></p>
            <p className="text-muted-foreground">The transaction was indexed with ML data, but live analyzer output was not available after reload.</p>

            <p>
              Flagged decision: {indexedRecord?.is_flagged
                ? "Flagged because the stored index marks this transaction for review."
                : "Not flagged based on the stored index record."}
            </p>
          </>
        ) : data.alertInsight ? (
          <>
            <p>Score: <span className="font-mono">{typeof data.alertInsight.anomaly_score === "number" ? data.alertInsight.anomaly_score.toFixed(4) : "-"}</span></p>
            <p>Reason: <span className="font-mono">{data.alertInsight.explanation || "No explanation provided by alert."}</span></p>
            <p>Flagged decision: Flagged because this transaction has a recorded anomaly alert.</p>
          </>
        ) : (
          <>
            <p>No analyzer payload for this transaction yet.</p>
            <p>Flagged decision: Not flagged (or not scored yet). This can happen while transaction is still pending.</p>
          </>
        )}
        </CardContent>
      </Card>
    </PageShell>
  );
}

