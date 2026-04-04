import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

import { EmptyState } from "../../../components/states/EmptyState";
import { ErrorState } from "../../../components/states/ErrorState";
import { LoadingState } from "../../../components/states/LoadingState";
import { normalizeApiError, walletsService } from "../../../services";
import { useAuthStore } from "../../../stores/authStore";
import type { PaginationMeta } from "../../../types/api";
import type { WalletDetailPayload, WalletListPayload } from "../../../types/wallets";
import "../../../styles/pages/wallets.css";

export function WalletsPage() {
  const role = useAuthStore((state) => state.user?.role);
  const canAssignToUser = role === "admin";

  const [wallets, setWallets] = useState<WalletListPayload | null>(null);
  const [pagination, setPagination] = useState<PaginationMeta | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [detail, setDetail] = useState<WalletDetailPayload | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const [walletName, setWalletName] = useState("");
  const [assignToUser, setAssignToUser] = useState("");
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const loadWallets = useCallback(async (targetPage = 1) => {
    setLoading(true);
    setError(null);
    try {
      const result = await walletsService.list({ page: targetPage, perPage: 10 });
      setWallets(result.data);
      setPagination(result.pagination);
    } catch (loadError) {
      setError(normalizeApiError(loadError).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadWallets(1);
  }, [loadWallets]);

  const loadDetail = async (name: string) => {
    setDetailLoading(true);
    setDetailError(null);
    try {
      const result = await walletsService.getByName(name, { page: 1, perPage: 10 });
      setDetail(result.data);
    } catch (loadError) {
      setDetailError(normalizeApiError(loadError).message);
    } finally {
      setDetailLoading(false);
    }
  };

  const onCreateWallet = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setCreateError(null);
    setCreateLoading(true);
    try {
      await walletsService.create({
        name: walletName.trim(),
        assign_to_user: canAssignToUser && assignToUser.trim() ? assignToUser.trim() : undefined,
      });
      setWalletName("");
      setAssignToUser("");
      await loadWallets(1);
    } catch (createWalletError) {
      setCreateError(normalizeApiError(createWalletError).message);
    } finally {
      setCreateLoading(false);
    }
  };

  if (loading) {
    return <LoadingState message="Loading wallets..." />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={() => void loadWallets()} />;
  }

  return (
    <section className="page-panel page-wallets">
      <h1>Wallets</h1>

      <section>
        <h2>Create wallet</h2>
        <form className="form" onSubmit={(event) => void onCreateWallet(event)}>
          <label className="field">
            <span>Wallet name</span>
            <input value={walletName} onChange={(event) => setWalletName(event.target.value)} required minLength={2} />
          </label>

          {canAssignToUser ? (
            <label className="field">
              <span>Assign to user (optional)</span>
              <input value={assignToUser} onChange={(event) => setAssignToUser(event.target.value)} />
            </label>
          ) : null}

          <button type="submit" className="btn btn-primary" disabled={createLoading}>
            {createLoading ? "Creating..." : "Create wallet"}
          </button>
        </form>
        {createError ? <ErrorState title="Create wallet failed" message={createError} /> : null}
      </section>

      <section>
        <h2>Wallet list</h2>
        {!wallets || wallets.wallets.length === 0 ? (
          <EmptyState message="No wallets available." />
        ) : (
          <>
            <table className="data-table">
              <thead><tr><th>Name</th><th>Address</th><th>Created</th><th>Action</th></tr></thead>
              <tbody>
                {wallets.wallets.map((wallet) => (
                  <tr key={wallet.name}>
                    <td>{wallet.name}</td>
                    <td>{wallet.address.slice(0, 16)}...</td>
                    <td>{new Date(wallet.created_at).toLocaleString()}</td>
                    <td><button type="button" className="btn btn-secondary" onClick={() => void loadDetail(wallet.name)}>Details</button></td>
                  </tr>
                ))}
              </tbody>
            </table>

            {pagination ? (
              <div className="pagination-bar">
                <button type="button" className="btn btn-secondary" disabled={!pagination.has_prev} onClick={() => void loadWallets(pagination.page - 1)}>Previous</button>
                <span>Page {pagination.page}/{pagination.total_pages}</span>
                <button type="button" className="btn btn-secondary" disabled={!pagination.has_next} onClick={() => void loadWallets(pagination.page + 1)}>Next</button>
              </div>
            ) : null}
          </>
        )}
      </section>

      <section>
        <h2>Selected wallet details</h2>
        {detailLoading ? <LoadingState message="Loading wallet details..." /> : null}
        {detailError ? <ErrorState message={detailError} /> : null}
        {!detailLoading && !detailError && !detail ? <EmptyState message="Select a wallet to inspect transactions." /> : null}

        {detail ? (
          <>
            <div className="state-card">
              <p><strong>Name:</strong> {detail.wallet.name}</p>
              <p><strong>Address:</strong> {detail.wallet.address}</p>
              <p><strong>Transactions indexed:</strong> {detail.transaction_count}</p>
            </div>

            {detail.transactions.length === 0 ? (
              <EmptyState message="No indexed transactions for this wallet." />
            ) : (
              <table className="data-table">
                <thead><tr><th>ID</th><th>Type</th><th>Status</th><th>Amount</th><th>Timestamp</th></tr></thead>
                <tbody>
                  {detail.transactions.map((tx) => (
                    <tr key={tx.transaction_id}>
                      <td>{tx.transaction_id.slice(0, 12)}...</td>
                      <td>{tx.transaction_type}</td>
                      <td>{tx.tx_status}</td>
                      <td>{tx.amount}</td>
                      <td>{new Date(tx.timestamp).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        ) : null}
      </section>
    </section>
  );
}

