import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";

import { EmptyState } from "../../../components/states/EmptyState";
import { ErrorState } from "../../../components/states/ErrorState";
import { LoadingState } from "../../../components/states/LoadingState";
import { normalizeApiError, transactionsService } from "../../../services";
import type { PaginationMeta } from "../../../types/api";
import type {
  CreateTransactionResult,
  IndexedTransaction,
  TransactionFilters,
  TransactionListPayload,
} from "../../../types/transactions";
import "../../../styles/pages/transactions.css";

const TRANSACTION_TYPES = [
  "LOGIN",
  "LOGOUT",
  "LOGIN_FAILED",
  "ACCESS_GRANTED",
  "ACCESS_DENIED",
  "DATA_READ",
  "DATA_WRITE",
  "DATA_DELETE",
  "DATA_MODIFY",
  "CONFIG_CHANGE",
  "PERMISSION_CHANGE",
  "USER_CREATED",
  "USER_DELETED",
  "TRANSFER",
  "CUSTOM",
];

type KeyValueField = {
  id: number;
  key: string;
  value: string;
};

const defaultDataFields: KeyValueField[] = [
  { id: 1, key: "ip_address", value: "127.0.0.1" },
];

const defaultMetadataFields: KeyValueField[] = [
  { id: 1, key: "source", value: "ui_form" },
];

function parseFieldValue(rawValue: string): unknown {
  const value = rawValue.trim();
  if (!value.length) {
    return "";
  }

  const lowered = value.toLowerCase();
  if (lowered === "true") {
    return true;
  }
  if (lowered === "false") {
    return false;
  }
  if (lowered === "null") {
    return null;
  }

  const numeric = Number(value);
  if (!Number.isNaN(numeric) && value !== "") {
    return numeric;
  }

  return value;
}

function fieldsToRecord(fields: KeyValueField[]): Record<string, unknown> {
  return fields.reduce<Record<string, unknown>>((acc, field) => {
    const key = field.key.trim();
    if (!key.length) {
      return acc;
    }
    acc[key] = parseFieldValue(field.value);
    return acc;
  }, {});
}

export function TransactionsPage() {
  const [listData, setListData] = useState<TransactionListPayload | null>(null);
  const [pagination, setPagination] = useState<PaginationMeta | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [typeFilter, setTypeFilter] = useState("");
  const [senderFilter, setSenderFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [flaggedFilter, setFlaggedFilter] = useState("all");
  const [page, setPage] = useState(1);

  const [walletName, setWalletName] = useState("");
  const [txType, setTxType] = useState("LOGIN");
  const [dataFields, setDataFields] = useState<KeyValueField[]>(defaultDataFields);
  const [metadataFields, setMetadataFields] = useState<KeyValueField[]>(defaultMetadataFields);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitResult, setSubmitResult] = useState<CreateTransactionResult | null>(null);
  const [analysisById, setAnalysisById] = useState<Record<string, CreateTransactionResult["analysis"]>>({});

  const buildFilters = useCallback((): TransactionFilters => {
    const filters: TransactionFilters = {};
    if (typeFilter.trim()) {
      filters.type = typeFilter.trim();
    }
    if (senderFilter.trim()) {
      filters.sender = senderFilter.trim();
    }
    if (statusFilter.trim()) {
      filters.status = statusFilter.trim();
    }
    if (flaggedFilter === "true") {
      filters.flagged = true;
    }
    if (flaggedFilter === "false") {
      filters.flagged = false;
    }
    return filters;
  }, [typeFilter, senderFilter, statusFilter, flaggedFilter]);

  const loadTransactions = useCallback(async (targetPage = 1) => {
    setLoading(true);
    setError(null);
    try {
      const result = await transactionsService.list({
        page: targetPage,
        perPage: 10,
        ...buildFilters(),
      });
      setListData(result.data);
      setPagination(result.pagination);
      setPage(result.pagination.page);

      const analysisEntries = await Promise.all(
        result.data.transactions.map(async (tx) => {
          try {
            const analysis = await transactionsService.analyze(tx.transaction_id);
            return [tx.transaction_id, analysis] as const;
          } catch {
            return [tx.transaction_id, null] as const;
          }
        }),
      );

      const mapped = analysisEntries.reduce<Record<string, CreateTransactionResult["analysis"]>>((acc, entry) => {
        if (entry[1]) {
          acc[entry[0]] = entry[1];
        }
        return acc;
      }, {});

      setAnalysisById((previous) => ({ ...previous, ...mapped }));
    } catch (loadError) {
      setError(normalizeApiError(loadError).message);
    } finally {
      setLoading(false);
    }
  }, [buildFilters]);

  useEffect(() => {
    void loadTransactions(1);
  }, [loadTransactions]);

  const dataPreview = useMemo(() => JSON.stringify(fieldsToRecord(dataFields), null, 2), [dataFields]);
  const metadataPreview = useMemo(
    () => JSON.stringify(fieldsToRecord(metadataFields), null, 2),
    [metadataFields],
  );

  const updateField = (
    target: "data" | "metadata",
    id: number,
    fieldName: "key" | "value",
    value: string,
  ) => {
    const updater = (field: KeyValueField): KeyValueField => (field.id === id ? { ...field, [fieldName]: value } : field);
    if (target === "data") {
      setDataFields((previous) => previous.map(updater));
      return;
    }
    setMetadataFields((previous) => previous.map(updater));
  };

  const addField = (target: "data" | "metadata") => {
    const newField: KeyValueField = { id: Date.now() + Math.floor(Math.random() * 10_000), key: "", value: "" };
    if (target === "data") {
      setDataFields((previous) => [...previous, newField]);
      return;
    }
    setMetadataFields((previous) => [...previous, newField]);
  };

  const removeField = (target: "data" | "metadata", id: number) => {
    if (target === "data") {
      setDataFields((previous) => previous.filter((field) => field.id !== id));
      return;
    }
    setMetadataFields((previous) => previous.filter((field) => field.id !== id));
  };

  const onCreateTransaction = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitError(null);
    setSubmitResult(null);
    setSubmitLoading(true);

    try {
      const data = fieldsToRecord(dataFields);
      if (Object.keys(data).length === 0) {
        throw new Error("At least one data field is required.");
      }
      const metadata = fieldsToRecord(metadataFields);

      const created = await transactionsService.create({
        wallet_name: walletName.trim() || undefined,
        transaction_type: txType,
        data,
        metadata: Object.keys(metadata).length ? metadata : undefined,
      });

      setSubmitResult(created);
      setAnalysisById((previous) => ({
        ...previous,
        [created.analysis.transaction_id]: created.analysis,
      }));
      await loadTransactions(1);
    } catch (createError) {
      setSubmitError(normalizeApiError(createError).message);
    } finally {
      setSubmitLoading(false);
    }
  };

  const rows: IndexedTransaction[] = listData?.transactions ?? [];

  return (
    <section className="page-panel page-transactions">
      <h1>Transactions</h1>

      <section>
        <h2>Simulation</h2>
        <form className="form" onSubmit={onCreateTransaction}>
          <label className="field">
            <span>Wallet name (optional)</span>
            <input value={walletName} onChange={(event) => setWalletName(event.target.value)} placeholder="admin" />
          </label>

          <label className="field">
            <span>Transaction type</span>
            <select value={txType} onChange={(event) => setTxType(event.target.value)}>
              {TRANSACTION_TYPES.map((type) => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Data fields</span>
            <div className="kv-fields">
              {dataFields.map((field, index) => (
                <div key={field.id} className="kv-row">
                  <input
                    value={field.key}
                    onChange={(event) => updateField("data", field.id, "key", event.target.value)}
                    placeholder={`Field name #${index + 1}`}
                  />
                  <input
                    value={field.value}
                    onChange={(event) => updateField("data", field.id, "value", event.target.value)}
                    placeholder="Value"
                  />
                  <button
                    className="btn btn-secondary"
                    type="button"
                    onClick={() => removeField("data", field.id)}
                    disabled={dataFields.length === 1}
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
            <button className="btn btn-secondary" type="button" onClick={() => addField("data")}>
              Add data field
            </button>
            <pre className="json-block">{dataPreview}</pre>
          </label>

          <label className="field">
            <span>Metadata fields (optional)</span>
            <div className="kv-fields">
              {metadataFields.map((field, index) => (
                <div key={field.id} className="kv-row">
                  <input
                    value={field.key}
                    onChange={(event) => updateField("metadata", field.id, "key", event.target.value)}
                    placeholder={`Metadata key #${index + 1}`}
                  />
                  <input
                    value={field.value}
                    onChange={(event) => updateField("metadata", field.id, "value", event.target.value)}
                    placeholder="Value"
                  />
                  <button
                    className="btn btn-secondary"
                    type="button"
                    onClick={() => removeField("metadata", field.id)}
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
            <button className="btn btn-secondary" type="button" onClick={() => addField("metadata")}>
              Add metadata field
            </button>
            <pre className="json-block">{metadataPreview}</pre>
          </label>

          <button className="btn btn-primary" type="submit" disabled={submitLoading}>
            {submitLoading ? "Submitting..." : "Submit transaction"}
          </button>
        </form>

        {submitError ? <ErrorState title="Create transaction failed" message={submitError} /> : null}
        {submitResult ? (
          <div className="state-card">
            <h3>Transaction created</h3>
            <p>Status: {submitResult.analysis.overall_status}</p>
            <p>
              <Link to={`/transactions/${String(submitResult.transaction.transaction_id ?? "")}`}>Open detail</Link>
            </p>
          </div>
        ) : null}
      </section>

      <section>
        <h2>List and Filters</h2>
        <div className="filters-grid">
          <label className="field">
            <span>Type</span>
            <input value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)} />
          </label>
          <label className="field">
            <span>Sender</span>
            <input value={senderFilter} onChange={(event) => setSenderFilter(event.target.value)} />
          </label>
          <label className="field">
            <span>Status</span>
            <input value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} />
          </label>
          <label className="field">
            <span>Flagged</span>
            <select value={flaggedFilter} onChange={(event) => setFlaggedFilter(event.target.value)}>
              <option value="all">All</option>
              <option value="true">True</option>
              <option value="false">False</option>
            </select>
          </label>
        </div>

        {loading ? <LoadingState message="Loading transactions..." /> : null}
        {error ? <ErrorState message={error} onRetry={() => void loadTransactions(page)} /> : null}

        {!loading && !error && rows.length === 0 ? <EmptyState message="No transactions match current filters." /> : null}

        {!loading && !error && rows.length > 0 ? (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Flagged</th>
                  <th>ML Score</th>
                  <th>ML Reason</th>
                  <th>Amount</th>
                  <th>Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const analysis = analysisById[row.transaction_id];
                  const mlScore = analysis?.anomaly_result ? analysis.anomaly_result.anomaly_score.toFixed(4) : "-";
                  const mlReason = analysis?.anomaly_result?.explanation
                    ? analysis.anomaly_result.explanation
                    : analysis
                      ? (analysis.flagged_for_review
                        ? "Flagged by model"
                        : "No anomaly detected or detector not trained")
                      : "-";

                  return (
                  <tr key={row.transaction_id}>
                    <td><Link to={`/transactions/${row.transaction_id}`}>{row.transaction_id.slice(0, 12)}...</Link></td>
                    <td>{row.transaction_type}</td>
                    <td>{row.tx_status}</td>
                    <td>{row.is_flagged ? "Yes" : "No"}</td>
                    <td>{mlScore}</td>
                    <td title={mlReason}>{mlReason}</td>
                    <td>{row.amount}</td>
                    <td>{new Date(row.timestamp).toLocaleString()}</td>
                  </tr>
                  );
                })}
              </tbody>
            </table>

            {pagination ? (
              <div className="pagination-bar">
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={!pagination.has_prev}
                  onClick={() => void loadTransactions(pagination.page - 1)}
                >
                  Previous
                </button>
                <span>
                  Page {pagination.page} / {pagination.total_pages} (total {pagination.total})
                </span>
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={!pagination.has_next}
                  onClick={() => void loadTransactions(pagination.page + 1)}
                >
                  Next
                </button>
              </div>
            ) : null}
          </>
        ) : null}
      </section>
    </section>
  );
}
