import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { EmptyState } from "../../../components/states/EmptyState";
import { ErrorState } from "../../../components/states/ErrorState";
import { LoadingState } from "../../../components/states/LoadingState";
import { blockchainService, normalizeApiError } from "../../../services";
import { useAuthStore } from "../../../stores/authStore";
import type { PaginationMeta } from "../../../types/api";
import type { BlockchainListPayload, BlockchainStats, BlockchainValidation, MempoolPayload } from "../../../types/blockchain";
import "../../../styles/pages/blockchain.css";

export function BlockchainPage() {
  const role = useAuthStore((state) => state.user?.role);
  const canMine = role === "admin" || role === "operator";

  const [stats, setStats] = useState<BlockchainStats | null>(null);
  const [chain, setChain] = useState<BlockchainListPayload | null>(null);
  const [chainPagination, setChainPagination] = useState<PaginationMeta | null>(null);
  const [mempool, setMempool] = useState<MempoolPayload | null>(null);
  const [mempoolPagination, setMempoolPagination] = useState<PaginationMeta | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [validateResult, setValidateResult] = useState<BlockchainValidation | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const load = useCallback(async (chainPage = 1, mempoolPage = 1) => {
    setLoading(true);
    setError(null);
    try {
      const [statsResult, chainResult, mempoolResult] = await Promise.all([
        blockchainService.getStats(),
        blockchainService.getBlockchain({ page: chainPage, perPage: 10 }),
        blockchainService.getMempool({ page: mempoolPage, perPage: 10 }),
      ]);

      setStats(statsResult);
      setChain(chainResult.data);
      setChainPagination(chainResult.pagination);
      setMempool(mempoolResult.data);
      setMempoolPagination(mempoolResult.pagination);
    } catch (loadError) {
      setError(normalizeApiError(loadError).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const onValidate = async () => {
    setActionLoading(true);
    setActionError(null);
    try {
      setValidateResult(await blockchainService.validate());
    } catch (validateError) {
      setActionError(normalizeApiError(validateError).message);
    } finally {
      setActionLoading(false);
    }
  };

  const onMine = async () => {
    setActionLoading(true);
    setActionError(null);
    try {
      await blockchainService.mine();
      await load(1, 1);
    } catch (mineError) {
      setActionError(normalizeApiError(mineError).message);
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return <LoadingState message="Loading blockchain data..." />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={() => void load()} />;
  }

  if (!stats || !chain || !mempool) {
    return <EmptyState message="No blockchain data available." />;
  }

  return (
    <section className="page-panel page-blockchain">
      <h1>Blockchain</h1>

      <div className="kpi-grid">
        <article className="kpi-card"><h3>Height</h3><strong>{stats.height}</strong></article>
        <article className="kpi-card"><h3>Total Blocks</h3><strong>{stats.total_blocks}</strong></article>
        <article className="kpi-card"><h3>Total Tx</h3><strong>{stats.total_transactions}</strong></article>
        <article className="kpi-card"><h3>Mempool</h3><strong>{stats.mempool_size}</strong></article>
      </div>

      <div className="quick-actions">
        <button type="button" className="btn btn-secondary" onClick={onValidate} disabled={actionLoading}>Validate chain</button>
        <button type="button" className="btn btn-primary" onClick={onMine} disabled={actionLoading || !canMine}>Mine block</button>
      </div>

      {validateResult ? (
        <div className="state-card">
          <h3>Validation result</h3>
          <p>Valid: {validateResult.is_valid ? "Yes" : "No"}</p>
          {validateResult.error ? <p>Error: {validateResult.error}</p> : null}
        </div>
      ) : null}
      {actionError ? <ErrorState message={actionError} /> : null}

      <section>
        <h2>Blocks</h2>
        {chain.chain.length === 0 ? (
          <EmptyState message="No blocks found." />
        ) : (
          <>
            <table className="data-table">
              <thead><tr><th>Index</th><th>Hash</th><th>Previous</th><th>Tx</th><th>Timestamp</th></tr></thead>
              <tbody>
                {chain.chain.map((block) => (
                  <tr key={block.index}>
                    <td><Link to={`/blockchain/${block.index}`}>{block.index}</Link></td>
                    <td>{block.block_hash.slice(0, 12)}...</td>
                    <td>{block.previous_hash.slice(0, 12)}...</td>
                    <td>{block.transactions.length}</td>
                    <td>{new Date(block.timestamp).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {chainPagination ? (
              <div className="pagination-bar">
                <button className="btn btn-secondary" disabled={!chainPagination.has_prev} onClick={() => void load(chainPagination.page - 1, mempoolPagination?.page ?? 1)}>Previous</button>
                <span>Page {chainPagination.page}/{chainPagination.total_pages}</span>
                <button className="btn btn-secondary" disabled={!chainPagination.has_next} onClick={() => void load(chainPagination.page + 1, mempoolPagination?.page ?? 1)}>Next</button>
              </div>
            ) : null}
          </>
        )}
      </section>

      <section>
        <h2>Mempool</h2>
        {mempool.transactions.length === 0 ? (
          <EmptyState message="No pending transactions in mempool." />
        ) : (
          <>
            <table className="data-table">
              <thead><tr><th>ID</th><th>Type</th><th>Sender</th><th>Timestamp</th></tr></thead>
              <tbody>
                {mempool.transactions.map((tx) => (
                  <tr key={tx.transaction_id}>
                    <td><Link to={`/transactions/${tx.transaction_id}`}>{tx.transaction_id.slice(0, 12)}...</Link></td>
                    <td>{tx.transaction_type}</td>
                    <td>{tx.sender_address.slice(0, 12)}...</td>
                    <td>{new Date(tx.timestamp).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {mempoolPagination ? (
              <div className="pagination-bar">
                <button className="btn btn-secondary" disabled={!mempoolPagination.has_prev} onClick={() => void load(chainPagination?.page ?? 1, mempoolPagination.page - 1)}>Previous</button>
                <span>Page {mempoolPagination.page}/{mempoolPagination.total_pages}</span>
                <button className="btn btn-secondary" disabled={!mempoolPagination.has_next} onClick={() => void load(chainPagination?.page ?? 1, mempoolPagination.page + 1)}>Next</button>
              </div>
            ) : null}
          </>
        )}
      </section>
    </section>
  );
}

