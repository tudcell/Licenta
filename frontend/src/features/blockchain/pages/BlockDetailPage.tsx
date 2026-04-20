import { useParams } from "react-router-dom";

import { useCallback, useEffect, useMemo, useState } from "react";

import { PageShell } from "../../../components/common/PageShell";
import { EmptyState } from "../../../components/states/EmptyState";
import { ErrorState } from "../../../components/states/ErrorState";
import { LoadingState } from "../../../components/states/LoadingState";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../../components/ui/table";
import { blockchainService, normalizeApiError } from "../../../services";
import type { BlockRecord } from "../../../types/blockchain";

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
    <PageShell title="Block detail" description={`Block index: ${block.index}`}>
      <Card>
        <CardHeader>
          <CardTitle>Block metadata</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p><strong>Hash:</strong> {block.block_hash}</p>
          <p><strong>Previous hash:</strong> {block.previous_hash}</p>
          <p><strong>Difficulty:</strong> {block.difficulty}</p>
          <p><strong>Nonce:</strong> {block.nonce}</p>
          <p><strong>Merkle root:</strong> {block.merkle_root}</p>
          <p><strong>Timestamp:</strong> {new Date(block.timestamp).toLocaleString()}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Transactions</CardTitle>
        </CardHeader>
        <CardContent>
          {block.transactions.length === 0 ? (
            <EmptyState message="This block has no transactions." />
          ) : (
            <Table>
              <TableHeader><TableRow><TableHead>ID</TableHead><TableHead>Type</TableHead><TableHead>Sender</TableHead><TableHead>Timestamp</TableHead></TableRow></TableHeader>
              <TableBody>
                {block.transactions.map((tx) => (
                  <TableRow key={tx.transaction_id}>
                    <TableCell>{tx.transaction_id.slice(0, 12)}...</TableCell>
                    <TableCell>{tx.transaction_type}</TableCell>
                    <TableCell>{tx.sender_address.slice(0, 16)}...</TableCell>
                    <TableCell>{new Date(tx.timestamp).toLocaleString()}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </PageShell>
  );
}

