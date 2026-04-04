import type { PaginationMeta } from "./api";
import type { IndexedTransaction } from "./transactions";

export interface WalletRecord {
  name: string;
  address: string;
  public_key: string;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface WalletListPayload {
  wallets: WalletRecord[];
  count: number;
}

export interface WalletListResponse {
  data: WalletListPayload;
  pagination: PaginationMeta;
}

export interface CreateWalletPayload {
  name: string;
  assign_to_user?: string;
}

export interface CreateWalletResult {
  wallet: WalletRecord;
  assigned_to: string;
}

export interface WalletDetailPayload {
  wallet: WalletRecord;
  transactions: IndexedTransaction[];
  transaction_count: number;
}

export interface WalletDetailResponse {
  data: WalletDetailPayload;
  pagination: PaginationMeta;
}

