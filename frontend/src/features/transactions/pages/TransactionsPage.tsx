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

type TransactionFieldDefinition = {
  name: string;
  label: string;
  inputType?: "text" | "number";
  placeholder?: string;
};

type TransactionTemplate = {
  fields: TransactionFieldDefinition[];
  defaults: Record<string, string>;
  metadata: Record<string, unknown>;
};

function getTemplateByType(transactionType: string): TransactionTemplate {
  switch (transactionType) {
    case "TRANSFER":
      return {
        fields: [
          { name: "recipient", label: "Recipient wallet", placeholder: "wallet_bob" },
          { name: "amount", label: "Amount", inputType: "number", placeholder: "1000" },
          { name: "currency", label: "Currency", placeholder: "RON" },
        ],
        defaults: { recipient: "", amount: "1000", currency: "RON" },
        metadata: { category: "financial", source: "ui_demo" },
      };
    case "LOGIN":
    case "LOGIN_FAILED":
      return {
        fields: [
          { name: "user_id", label: "User ID", placeholder: "alice" },
          { name: "ip_address", label: "IP address", placeholder: "127.0.0.1" },
          { name: "user_agent", label: "User agent", placeholder: "Mozilla/5.0" },
        ],
        defaults: { user_id: "", ip_address: "127.0.0.1", user_agent: "BrowserDemo/1.0" },
        metadata: { category: "authentication", source: "ui_demo" },
      };
    case "DATA_READ":
    case "DATA_WRITE":
    case "DATA_DELETE":
    case "DATA_MODIFY":
      return {
        fields: [
          { name: "user_id", label: "User ID", placeholder: "alice" },
          { name: "resource_id", label: "Resource", placeholder: "patient_123" },
          { name: "action", label: "Action", placeholder: "read/write/delete/modify" },
        ],
        defaults: { user_id: "", resource_id: "", action: transactionType.replace("DATA_", "").toLowerCase() },
        metadata: { category: "data_access", source: "ui_demo" },
      };
    case "ACCESS_GRANTED":
    case "ACCESS_DENIED":
      return {
        fields: [
          { name: "user_id", label: "User ID", placeholder: "alice" },
          { name: "resource_id", label: "Resource", placeholder: "secure_area_1" },
          { name: "reason", label: "Reason", placeholder: "Role check" },
        ],
        defaults: { user_id: "", resource_id: "", reason: "" },
        metadata: { category: "access_control", source: "ui_demo" },
      };
    default:
      return {
        fields: [
          { name: "event", label: "Event description", placeholder: "What happened?" },
          { name: "details", label: "Details", placeholder: "Extra context" },
        ],
        defaults: { event: "", details: "" },
        metadata: { category: "generic", source: "ui_demo" },
      };
  }
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
  const [templateValues, setTemplateValues] = useState<Record<string, string>>(() => getTemplateByType("LOGIN").defaults);
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

  const selectedTemplate = useMemo(() => getTemplateByType(txType), [txType]);

  useEffect(() => {
    setTemplateValues(selectedTemplate.defaults);
  }, [selectedTemplate]);

  const updateTemplateValue = (name: string, value: string) => {
    setTemplateValues((previous) => ({
      ...previous,
      [name]: value,
    }));
  };

  const buildTransactionData = () => {
    const data = selectedTemplate.fields.reduce<Record<string, unknown>>((acc, field) => {
      const raw = (templateValues[field.name] ?? "").trim();
      if (!raw.length) {
        return acc;
      }
      if (field.inputType === "number") {
        acc[field.name] = Number(raw);
        return acc;
      }
      acc[field.name] = raw;
      return acc;
    }, {});

    if (txType === "LOGIN" || txType === "LOGIN_FAILED") {
      data.success = txType === "LOGIN";
    }
    if (txType === "ACCESS_GRANTED" || txType === "ACCESS_DENIED") {
      data.success = txType === "ACCESS_GRANTED";
    }
    if (txType.startsWith("DATA_")) {
      data.success = true;
    }

    return data;
  };

  const dataPreview = useMemo(() => JSON.stringify(buildTransactionData(), null, 2), [templateValues, txType]);
  const metadataPreview = useMemo(() => JSON.stringify(selectedTemplate.metadata, null, 2), [selectedTemplate]);

  const onCreateTransaction = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitError(null);
    setSubmitResult(null);
    setSubmitLoading(true);

    try {
      const data = buildTransactionData();
      const missingRequired = selectedTemplate.fields.some((field) => {
        const value = (templateValues[field.name] ?? "").trim();
        return !value.length;
      });
      if (missingRequired) {
        throw new Error("Please complete all required fields for this transaction type.");
      }

      const created = await transactionsService.create({
        wallet_name: walletName.trim() || undefined,
        transaction_type: txType,
        data,
        metadata: selectedTemplate.metadata,
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

          <div className="template-grid">
            {selectedTemplate.fields.map((field) => (
              <label key={field.name} className="field">
                <span>{field.label}</span>
                <input
                  type={field.inputType ?? "text"}
                  value={templateValues[field.name] ?? ""}
                  placeholder={field.placeholder}
                  onChange={(event) => updateTemplateValue(field.name, event.target.value)}
                  required
                />
              </label>
            ))}
          </div>

          <div className="template-preview-grid">
            <label className="field">
              <span>Transaction payload preview</span>
              <pre className="json-block">{dataPreview}</pre>
            </label>
            <label className="field">
              <span>Auto metadata preview</span>
              <pre className="json-block">{metadataPreview}</pre>
            </label>
          </div>

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
