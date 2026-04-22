import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

import { PageShell } from "../../../components/common/PageShell";
import { PaginationBar } from "../../../components/common/PaginationBar";
import { EmptyState } from "../../../components/states/EmptyState";
import { ErrorState } from "../../../components/states/ErrorState";
import { LoadingState } from "../../../components/states/LoadingState";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";
import { Label } from "../../../components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../../../components/ui/table";
import { normalizeApiError, walletsService } from "../../../services";
import { useAuthStore } from "../../../stores/authStore";
import type { PaginationMeta } from "../../../types/api";
import type { WalletDetailPayload, WalletListPayload } from "../../../types/wallets";

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
  const [detailPage, setDetailPage] = useState(1);
  const [detailPagination, setDetailPagination] = useState<PaginationMeta | null>(null);

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

  const loadDetail = async (name: string, targetPage = 1) => {
    setDetailLoading(true);
    setDetailError(null);
    try {
      const result = await walletsService.getByName(name, { page: targetPage, perPage: 10 });
      setDetail(result.data);
      setDetailPagination(result.pagination);
      setDetailPage(result.pagination.page);
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
    <PageShell title="Wallets" description="Manage wallets and inspect indexed transactions per wallet.">
      <Card>
        <CardHeader>
          <CardTitle>Create wallet</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <form className="space-y-4" onSubmit={(event) => void onCreateWallet(event)}>
            <div className="grid gap-2">
              <Label htmlFor="walletName">Wallet name</Label>
              <Input
                id="walletName"
                value={walletName}
                onChange={(event) => setWalletName(event.target.value)}
                required
                minLength={2}
              />
            </div>

            {canAssignToUser ? (
              <div className="grid gap-2">
                <Label htmlFor="assignToUser">Assign to user (optional)</Label>
                <Input id="assignToUser" value={assignToUser} onChange={(event) => setAssignToUser(event.target.value)} />
              </div>
            ) : null}

            <Button type="submit" disabled={createLoading}>
              {createLoading ? "Creating..." : "Create wallet"}
            </Button>
          </form>
          {createError ? <ErrorState title="Create wallet failed" message={createError} /> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Wallet list</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {!wallets || wallets.wallets.length === 0 ? (
            <EmptyState message="No wallets available." />
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Address</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead>Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {wallets.wallets.map((wallet) => (
                    <TableRow key={wallet.name}>
                      <TableCell>{wallet.name}</TableCell>
                      <TableCell>{wallet.address.slice(0, 16)}...</TableCell>
                      <TableCell>{new Date(wallet.created_at).toLocaleString()}</TableCell>
                      <TableCell>
                        <Button type="button" variant="outline" size="sm" onClick={() => void loadDetail(wallet.name)}>
                          Details
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {pagination ? (
                <PaginationBar
                  page={pagination.page}
                  totalPages={pagination.total_pages}
                  total={pagination.total}
                  hasPrevious={pagination.has_prev}
                  hasNext={pagination.has_next}
                  onPrevious={() => void loadWallets(pagination.page - 1)}
                  onNext={() => void loadWallets(pagination.page + 1)}
                />
              ) : null}
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Selected wallet details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {detailLoading ? <LoadingState message="Loading wallet details..." /> : null}
          {detailError ? <ErrorState message={detailError} /> : null}
          {!detailLoading && !detailError && !detail ? <EmptyState message="Select a wallet to inspect transactions." /> : null}

          {detail ? (
            <>
              <Card>
                <CardContent className="space-y-2 pt-6 text-sm">
                  <p><strong>Name:</strong> {detail.wallet.name}</p>
                  <p><strong>Address:</strong> {detail.wallet.address}</p>
                  <p><strong>Transactions indexed:</strong> {detail.transaction_count}</p>
                </CardContent>
              </Card>

              {detail.transactions.length === 0 ? (
                <EmptyState message="No indexed transactions for this wallet." />
              ) : (
                <>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>ID</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Amount</TableHead>
                        <TableHead>Timestamp</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {detail.transactions.map((tx) => (
                        <TableRow key={tx.transaction_id}>
                          <TableCell>{tx.transaction_id.slice(0, 12)}...</TableCell>
                          <TableCell>{tx.transaction_type}</TableCell>
                          <TableCell>{tx.tx_status}</TableCell>
                          <TableCell>{tx.amount}</TableCell>
                          <TableCell>{new Date(tx.timestamp).toLocaleString()}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>

                  {detailPagination ? (
                    <PaginationBar
                      page={detailPagination.page}
                      totalPages={detailPagination.total_pages}
                      total={detailPagination.total}
                      hasPrevious={detailPagination.has_prev}
                      hasNext={detailPagination.has_next}
                      onPrevious={() => detail && void loadDetail(detail.wallet.name, detailPage - 1)}
                      onNext={() => detail && void loadDetail(detail.wallet.name, detailPage + 1)}
                    />
                  ) : null}
                </>
              )}
            </>
          ) : null}
        </CardContent>
      </Card>
    </PageShell>
  );
}

