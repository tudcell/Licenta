import type { PaginationMeta } from "./api";

export interface IndexedTransaction {
  transaction_id: string;
  block_index: number | null;
  sender_address: string;
  transaction_type: string;
  amount: number;
  tx_status: string;
  is_flagged: number;
  timestamp: string;
  created_at: string;
}

export interface TransactionListPayload {
  transactions: IndexedTransaction[];
  count: number;
}

export interface TransactionListResponse {
  data: TransactionListPayload;
  pagination: PaginationMeta;
}

export interface TransactionProofPayload {
  transaction_id: string;
  block_index: number;
  merkle_root: string;
  proof: Record<string, unknown>;
  verified: boolean;
  index_record?: IndexedTransaction;
}

export interface TransactionDetailPayload {
  transaction_id?: string;
  block_index?: number;
  merkle_root?: string;
  verified?: boolean;
  index_record?: IndexedTransaction;
  proof?: Record<string, unknown>;
}

export interface TransactionAuditReport {
  transaction_id: string;
  blockchain_valid: boolean;
  signature_valid: boolean;
  merkle_proof_valid: boolean;
  block_index: number | null;
  overall_status: string;
  is_suspicious: boolean;
  flagged_for_review: boolean;
  added_to_mempool: boolean;
  quarantined: boolean;
  anomaly_result: AnomalyResultPayload | null;
  timestamp: string;
}

export interface AnomalyResultPayload {
  is_anomaly: boolean;
  anomaly_score: number;
  threshold: number;
  confidence?: number;
  explanation?: string;
}

export interface CreateTransactionPayload {
  wallet_name?: string;
  transaction_type: string;
  data: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface CreateTransactionResult {
  transaction: Record<string, unknown>;
  analysis: TransactionAuditReport;
}

export interface TransactionFilters {
  type?: string;
  sender?: string;
  status?: string;
  flagged?: boolean;
}

