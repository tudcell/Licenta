import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";

import { PageShell } from "../../../components/common/PageShell";
import { PaginationBar } from "../../../components/common/PaginationBar";
import { EmptyState } from "../../../components/states/EmptyState";
import { ErrorState } from "../../../components/states/ErrorState";
import { LoadingState } from "../../../components/states/LoadingState";
import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import { Select } from "../../../components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "../../../components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../../components/ui/table";
import { useDebouncedValue } from "../../../hooks/useDebouncedValue";
import { normalizeApiError, transactionsService } from "../../../services";
import type { PaginationMeta } from "../../../types/api";
import type {
  CreateTransactionResult,
  IndexedTransaction,
  TransactionFilters,
  TransactionListPayload,
} from "../../../types/transactions";

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

function parseDecisionFromMlReason(reason: string | null | undefined): { source: "hard_rule" | "model" | "unknown"; hardRuleReason: string | null } {
  if (!reason) {
    return { source: "unknown", hardRuleReason: null };
  }

  const hardRuleMatch = reason.match(/\[decision=hard_rule:([^\]]+)\]/i);
  if (hardRuleMatch) {
    return { source: "hard_rule", hardRuleReason: hardRuleMatch[1] ?? null };
  }

  if (/\[decision=model\]/i.test(reason)) {
    return { source: "model", hardRuleReason: null };
  }

  return { source: "unknown", hardRuleReason: null };
}

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

  const [typeFilterInput, setTypeFilterInput] = useState("");
  const [senderFilterInput, setSenderFilterInput] = useState("");
  const [statusFilterInput, setStatusFilterInput] = useState("");
  const [flaggedFilter, setFlaggedFilter] = useState("all");
  const [page, setPage] = useState(1);

  const typeFilter = useDebouncedValue(typeFilterInput, 350);
  const senderFilter = useDebouncedValue(senderFilterInput, 350);
  const statusFilter = useDebouncedValue(statusFilterInput, 350);

  const [walletName, setWalletName] = useState("");
  const [txType, setTxType] = useState("LOGIN");
  const [templateValues, setTemplateValues] = useState<Record<string, string>>(() => getTemplateByType("LOGIN").defaults);
  const [showCreateDrawer, setShowCreateDrawer] = useState(false);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitResult, setSubmitResult] = useState<CreateTransactionResult | null>(null);

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

  const buildTransactionData = useCallback(() => {
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
  }, [selectedTemplate.fields, templateValues, txType]);

  const dataPreview = useMemo(() => JSON.stringify(buildTransactionData(), null, 2), [buildTransactionData]);
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
        setSubmitError("Please complete all required fields for this transaction type.");
        setSubmitLoading(false);
        return;
      }

      const created = await transactionsService.create({
        wallet_name: walletName.trim() || undefined,
        transaction_type: txType,
        data,
        metadata: selectedTemplate.metadata,
      });

      setSubmitResult(created);
      setShowCreateDrawer(false);
      await loadTransactions(1);
    } catch (createError) {
      setSubmitError(normalizeApiError(createError).message);
    } finally {
      setSubmitLoading(false);
    }
  };

  const rows: IndexedTransaction[] = listData?.transactions ?? [];

  const typeSuggestions = useMemo(() => {
    const merged = new Set<string>(TRANSACTION_TYPES);
    rows.forEach((row) => merged.add(row.transaction_type));
    const query = typeFilterInput.trim().toLowerCase();
    return Array.from(merged)
      .filter((value) => (query ? value.toLowerCase().includes(query) : true))
      .slice(0, 8);
  }, [rows, typeFilterInput]);

  const senderSuggestions = useMemo(() => {
    const merged = new Set<string>();
    rows.forEach((row) => merged.add(row.sender_address));
    const query = senderFilterInput.trim().toLowerCase();
    return Array.from(merged)
      .filter((value) => (query ? value.toLowerCase().includes(query) : true))
      .slice(0, 8);
  }, [rows, senderFilterInput]);

  const statusSuggestions = useMemo(() => {
    const merged = new Set<string>(["PENDING", "MINED", "FLAGGED", "REJECTED"]);
    rows.forEach((row) => merged.add(row.tx_status));
    const query = statusFilterInput.trim().toLowerCase();
    return Array.from(merged)
      .filter((value) => (query ? value.toLowerCase().includes(query) : true))
      .slice(0, 8);
  }, [rows, statusFilterInput]);

  return (
    <PageShell
      title="Transactions"
      description="Filter indexed transactions and simulate new events for blockchain/ML analysis."
      actions={
        <Button type="button" onClick={() => setShowCreateDrawer(true)}>
          Add transaction
        </Button>
      }
    >
      <Sheet open={showCreateDrawer} onOpenChange={setShowCreateDrawer}>
        <SheetContent side="right" className="overflow-y-auto">
          <SheetHeader>
            <SheetTitle>Create transaction</SheetTitle>
            <SheetDescription>Build payload from typed templates and submit to backend.</SheetDescription>
          </SheetHeader>

          <form className="mt-6 space-y-4" onSubmit={onCreateTransaction}>
            <div className="grid gap-2">
              <Label htmlFor="walletName">Wallet name (optional)</Label>
              <Input
                id="walletName"
                value={walletName}
                onChange={(event) => setWalletName(event.target.value)}
                placeholder="admin"
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="transactionType">Transaction type</Label>
              <Select id="transactionType" value={txType} onChange={(event) => setTxType(event.target.value)}>
                {TRANSACTION_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </Select>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              {selectedTemplate.fields.map((field) => (
                <div key={field.name} className="grid gap-2">
                  <Label htmlFor={`field-${field.name}`}>{field.label}</Label>
                  <Input
                    id={`field-${field.name}`}
                    type={field.inputType ?? "text"}
                    value={templateValues[field.name] ?? ""}
                    placeholder={field.placeholder}
                    onChange={(event) => updateTemplateValue(field.name, event.target.value)}
                    required
                  />
                </div>
              ))}
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <div className="grid gap-2">
                <Label>Transaction payload preview</Label>
                <pre className="max-h-72 overflow-auto rounded-md border bg-muted p-3 text-xs">{dataPreview}</pre>
              </div>
              <div className="grid gap-2">
                <Label>Auto metadata preview</Label>
                <pre className="max-h-72 overflow-auto rounded-md border bg-muted p-3 text-xs">{metadataPreview}</pre>
              </div>
            </div>

            <Button type="submit" disabled={submitLoading}>
              {submitLoading ? "Submitting..." : "Submit transaction"}
            </Button>
          </form>
        </SheetContent>
      </Sheet>

      {submitError ? <ErrorState title="Create transaction failed" message={submitError} /> : null}
      {submitResult ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Transaction created</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p>Status: {submitResult.analysis.overall_status}</p>
            <p>
              <Link className="text-primary hover:underline" to={`/transactions/${String(submitResult.transaction.transaction_id ?? "")}`}>
                Open detail
              </Link>
            </p>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>List and filters</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <div className="grid gap-2">
              <Label htmlFor="typeFilter">Type</Label>
              <Input
                id="typeFilter"
                list="transaction-type-suggestions"
                value={typeFilterInput}
                onChange={(event) => setTypeFilterInput(event.target.value)}
                placeholder="Start typing type..."
              />
              <datalist id="transaction-type-suggestions">
                {typeSuggestions.map((value) => (
                  <option key={value} value={value} />
                ))}
              </datalist>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="senderFilter">Sender</Label>
              <Input
                id="senderFilter"
                list="transaction-sender-suggestions"
                value={senderFilterInput}
                onChange={(event) => setSenderFilterInput(event.target.value)}
                placeholder="Start typing sender..."
              />
              <datalist id="transaction-sender-suggestions">
                {senderSuggestions.map((value) => (
                  <option key={value} value={value} />
                ))}
              </datalist>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="statusFilter">Status</Label>
              <Input
                id="statusFilter"
                list="transaction-status-suggestions"
                value={statusFilterInput}
                onChange={(event) => setStatusFilterInput(event.target.value)}
                placeholder="Start typing status..."
              />
              <datalist id="transaction-status-suggestions">
                {statusSuggestions.map((value) => (
                  <option key={value} value={value} />
                ))}
              </datalist>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="flaggedFilter">Flagged</Label>
              <Select id="flaggedFilter" value={flaggedFilter} onChange={(event) => setFlaggedFilter(event.target.value)}>
                <option value="all">All</option>
                <option value="true">True</option>
                <option value="false">False</option>
              </Select>
            </div>
          </div>
        <div className="min-h-[600px]">
          {loading ? <LoadingState message="Loading transactions..." /> : null}
          {error ? <ErrorState message={error} onRetry={() => void loadTransactions(page)} /> : null}
          {!loading && !error && rows.length === 0 ? <EmptyState message="No transactions match current filters." /> : null}

          {!loading && !error && rows.length > 0 ? (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Flagged</TableHead>
                    <TableHead>ML Score</TableHead>
                    <TableHead>Decision</TableHead>
                    <TableHead>Rule</TableHead>
                    <TableHead>ML Reason</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead>Timestamp</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((row) => {
                    const mlScore = typeof row.ml_score === "number" ? row.ml_score.toFixed(4) : "-";
                    const mlReason = row.ml_reason ?? "No anomaly detected or detector not trained";
                    const decision = parseDecisionFromMlReason(row.ml_reason);

                    return (
                      <TableRow key={row.transaction_id}>
                        <TableCell>
                          <Link className="font-medium text-primary hover:underline" to={`/transactions/${row.transaction_id}`}>
                            {row.transaction_id.slice(0, 12)}...
                          </Link>
                        </TableCell>
                        <TableCell>{row.transaction_type}</TableCell>
                        <TableCell>{row.tx_status}</TableCell>
                        <TableCell>
                          <Badge variant={row.is_flagged ? "destructive" : "secondary"}>{row.is_flagged ? "Yes" : "No"}</Badge>
                        </TableCell>
                        <TableCell>{mlScore}</TableCell>
                        <TableCell>
                          <Badge variant={decision.source === "hard_rule" ? "destructive" : decision.source === "model" ? "outline" : "secondary"}>
                            {decision.source}
                          </Badge>
                        </TableCell>
                        <TableCell>{decision.hardRuleReason ?? "-"}</TableCell>
                        <TableCell className="max-w-[320px] truncate" title={mlReason}>
                          {mlReason}
                        </TableCell>
                        <TableCell>{row.amount}</TableCell>
                        <TableCell>{new Date(row.timestamp).toLocaleString()}</TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>

              {pagination ? (
                <PaginationBar
                  page={pagination.page}
                  totalPages={pagination.total_pages}
                  total={pagination.total}
                  hasPrevious={pagination.has_prev}
                  hasNext={pagination.has_next}
                  onPrevious={() => void loadTransactions(pagination.page - 1)}
                  onNext={() => void loadTransactions(pagination.page + 1)}
                />
              ) : null}
            </>
          ) : null}
        </div>
        </CardContent>
      </Card>
    </PageShell>
  );
}
