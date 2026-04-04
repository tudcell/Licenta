import { useParams } from "react-router-dom";

import { useCallback, useEffect, useState } from "react";

import { EmptyState } from "../../../components/states/EmptyState";
import { ErrorState } from "../../../components/states/ErrorState";
import { LoadingState } from "../../../components/states/LoadingState";
import { alertsService, normalizeApiError, transactionsService } from "../../../services";
import type { AlertRecord } from "../../../types/alerts";
import type { TransactionAuditReport, TransactionDetailPayload } from "../../../types/transactions";
import "../../../styles/pages/transaction-detail.css";

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
    <section className="page-panel page-transaction-detail">
      <h1>Transaction detail</h1>
      <p>Transaction ID: {id}</p>

      {data.detail.index_record ? (
        <div className="state-card">
          <h3>Indexed record</h3>
          <p>Type: {data.detail.index_record.transaction_type}</p>
          <p>Status: {data.detail.index_record.tx_status}</p>
          <p>Sender: {data.detail.index_record.sender_address}</p>
          <p>Amount: {data.detail.index_record.amount}</p>
          <p>Timestamp: {new Date(data.detail.index_record.timestamp).toLocaleString()}</p>
        </div>
      ) : null}

      {data.detail.proof ? (
        <div className="state-card">
          <h3>Merkle proof payload</h3>
          <pre className="json-block">{JSON.stringify(data.detail.proof, null, 2)}</pre>
        </div>
      ) : null}

      <div className="state-card">
        <h3>Analyzer status</h3>
        {data.analysis ? (
          <>
            <p>Overall status: {data.analysis.overall_status}</p>
            <p>Suspicious: {data.analysis.is_suspicious ? "Yes" : "No"}</p>
            <p>Signature valid: {data.analysis.signature_valid ? "Yes" : "No"}</p>
            <p>Merkle proof valid: {data.analysis.merkle_proof_valid ? "Yes" : "No"}</p>

            <h4>ML insights</h4>
            {data.analysis.anomaly_result ? (
              <>
                <p>Score: {data.analysis.anomaly_result.anomaly_score.toFixed(4)}</p>
                <p>Threshold: {data.analysis.anomaly_result.threshold.toFixed(4)}</p>
                <p>
                  Confidence: {typeof data.analysis.anomaly_result.confidence === "number"
                    ? data.analysis.anomaly_result.confidence.toFixed(4)
                    : "-"}
                </p>
                <p>Reason: {data.analysis.anomaly_result.explanation || "No model explanation available."}</p>
              </>
            ) : (
              <p>No ML anomaly payload. Detector may be untrained.</p>
            )}

            <p>
              Flagged decision: {data.analysis.flagged_for_review
                ? "Flagged because model considered this transaction anomalous."
                : "Not flagged because model considered this transaction within normal behavior."}
            </p>
          </>
        ) : data.alertInsight ? (
          <>
            <p>Score: {typeof data.alertInsight.anomaly_score === "number" ? data.alertInsight.anomaly_score.toFixed(4) : "-"}</p>
            <p>Reason: {data.alertInsight.explanation || "No explanation provided by alert."}</p>
            <p>Flagged decision: Flagged because this transaction has a recorded anomaly alert.</p>
          </>
        ) : (
          <>
            <p>No analyzer payload for this transaction yet.</p>
            <p>Flagged decision: Not flagged (or not scored yet). This can happen while transaction is still pending.</p>
          </>
        )}
      </div>
    </section>
  );
}

