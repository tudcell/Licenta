import { useParams } from "react-router-dom";

import { useCallback, useEffect, useMemo, useState } from "react";

import { EmptyState } from "../../../components/states/EmptyState";
import { ErrorState } from "../../../components/states/ErrorState";
import { LoadingState } from "../../../components/states/LoadingState";
import { blockchainService, normalizeApiError } from "../../../services";
import type { BlockRecord } from "../../../types/blockchain";
import "../../../styles/pages/block-detail.css";

export function BlockDetailPage() {
  const { index } = useParams();

  const numericIndex = useMemo(() => Number(index), [index]);

  const [block, setBlock] = useState<BlockRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!index || Number.isNaN(numericIndex) || numericIndex < 0) {
      setError("Invalid block index in URL.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      setBlock(await blockchainService.getBlock(numericIndex));
    } catch (loadError) {
      setError(normalizeApiError(loadError).message);
    } finally {
      setLoading(false);
    }
  }, [index, numericIndex]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return <LoadingState message="Loading block detail..." />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={() => void load()} />;
  }

  if (!block) {
    return <EmptyState message="Block not found." />;
  }

  return (
    <section className="page-panel page-block-detail">
      <h1>Block detail</h1>
      <p>Block index: {block.index}</p>

      <div className="state-card">
        <p><strong>Hash:</strong> {block.block_hash}</p>
        <p><strong>Previous hash:</strong> {block.previous_hash}</p>
        <p><strong>Difficulty:</strong> {block.difficulty}</p>
        <p><strong>Nonce:</strong> {block.nonce}</p>
        <p><strong>Merkle root:</strong> {block.merkle_root}</p>
        <p><strong>Timestamp:</strong> {new Date(block.timestamp).toLocaleString()}</p>
      </div>

      <h2>Transactions</h2>
      {block.transactions.length === 0 ? (
        <EmptyState message="This block has no transactions." />
      ) : (
        <table className="data-table">
          <thead><tr><th>ID</th><th>Type</th><th>Sender</th><th>Timestamp</th></tr></thead>
          <tbody>
            {block.transactions.map((tx) => (
              <tr key={tx.transaction_id}>
                <td>{tx.transaction_id.slice(0, 12)}...</td>
                <td>{tx.transaction_type}</td>
                <td>{tx.sender_address.slice(0, 16)}...</td>
                <td>{new Date(tx.timestamp).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

