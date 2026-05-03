import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { PageShell } from "../../../components/common/PageShell";
import { PaginationBar } from "../../../components/common/PaginationBar";
import { EmptyState } from "../../../components/states/EmptyState";
import { ErrorState } from "../../../components/states/ErrorState";
import { LoadingState } from "../../../components/states/LoadingState";
import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../../components/ui/table";
import { blockchainService, normalizeApiError } from "../../../services";
import { useAuthStore } from "../../../stores/authStore";
import type { PaginationMeta } from "../../../types/api";
import type { BlockchainListPayload, BlockchainStats, BlockchainValidation, MempoolPayload } from "../../../types/blockchain";

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
    <PageShell title="Blockchain" description="Chain status, validation, mining, and mempool visibility.">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card><CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Height</CardTitle></CardHeader><CardContent><p className="text-3xl font-semibold">{stats.height}</p></CardContent></Card>
        <Card><CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Total Blocks</CardTitle></CardHeader><CardContent><p className="text-3xl font-semibold">{stats.total_blocks}</p></CardContent></Card>
        <Card><CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Total Tx</CardTitle></CardHeader><CardContent><p className="text-3xl font-semibold">{stats.total_transactions}</p></CardContent></Card>
        <Card><CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">Mempool</CardTitle></CardHeader><CardContent><p className="text-3xl font-semibold">{stats.mempool_size}</p></CardContent></Card>
      </div>

      <div className="flex flex-wrap gap-4">
        <Button type="button" variant="outline" onClick={onValidate} disabled={actionLoading}>Validate chain</Button>
        <Button type="button" onClick={onMine} disabled={actionLoading || !canMine}>Mine block</Button>
      </div>

      {validateResult ? (
        <Card>
          <CardHeader><CardTitle>Validation result</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p>
              Valid: <Badge variant={validateResult.is_valid ? "secondary" : "destructive"}>{validateResult.is_valid ? "Yes" : "No"}</Badge>
            </p>
            {validateResult.error ? <p>Error: {validateResult.error}</p> : null}
          </CardContent>
        </Card>
      ) : null}
      {actionError ? <ErrorState message={actionError} /> : null}

      <Card>
        <CardHeader><CardTitle>Blocks</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          {chain.chain.length === 0 ? (
            <EmptyState message="No blocks found." />
          ) : (
            <>
              <Table>
                <TableHeader><TableRow><TableHead>Index</TableHead><TableHead>Hash</TableHead><TableHead>Previous</TableHead><TableHead>Tx</TableHead><TableHead>Timestamp</TableHead></TableRow></TableHeader>
                <TableBody>
                  {chain.chain.map((block) => (
                    <TableRow key={block.index}>
                      <TableCell><Link className="font-mono text-primary hover:underline" to={`/blockchain/${block.index}`}>{block.index}</Link></TableCell>
                      <TableCell className="font-mono">{block.block_hash.slice(0, 12)}...</TableCell>
                      <TableCell className="font-mono">{block.previous_hash.slice(0, 12)}...</TableCell>
                      <TableCell className="text-right">{block.transactions.length}</TableCell>
                      <TableCell>{new Date(block.timestamp).toLocaleString()}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              {chainPagination ? (
                <PaginationBar
                  page={chainPagination.page}
                  totalPages={chainPagination.total_pages}
                  total={chainPagination.total}
                  hasPrevious={chainPagination.has_prev}
                  hasNext={chainPagination.has_next}
                  onPrevious={() => void load(chainPagination.page - 1, mempoolPagination?.page ?? 1)}
                  onNext={() => void load(chainPagination.page + 1, mempoolPagination?.page ?? 1)}
                />
              ) : null}
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Mempool</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          {mempool.transactions.length === 0 ? (
            <EmptyState message="No pending transactions in mempool." />
          ) : (
            <>
              <Table>
                <TableHeader><TableRow><TableHead>ID</TableHead><TableHead>Type</TableHead><TableHead>Sender</TableHead><TableHead>Timestamp</TableHead></TableRow></TableHeader>
                <TableBody>
                  {mempool.transactions.map((tx) => (
                    <TableRow key={tx.transaction_id}>
                      <TableCell><Link className="font-mono text-primary hover:underline" to={`/transactions/${tx.transaction_id}`}>{tx.transaction_id.slice(0, 12)}...</Link></TableCell>
                      <TableCell>{tx.transaction_type}</TableCell>
                      <TableCell className="font-mono">{tx.sender_address.slice(0, 12)}...</TableCell>
                      <TableCell>{new Date(tx.timestamp).toLocaleString()}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              {mempoolPagination ? (
                <PaginationBar
                  page={mempoolPagination.page}
                  totalPages={mempoolPagination.total_pages}
                  total={mempoolPagination.total}
                  hasPrevious={mempoolPagination.has_prev}
                  hasNext={mempoolPagination.has_next}
                  onPrevious={() => void load(chainPagination?.page ?? 1, mempoolPagination.page - 1)}
                  onNext={() => void load(chainPagination?.page ?? 1, mempoolPagination.page + 1)}
                />
              ) : null}
            </>
          )}
        </CardContent>
      </Card>
    </PageShell>
  );
}

