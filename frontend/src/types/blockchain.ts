export interface TransactionSummary {
  transaction_id: string;
  transaction_type: string;
  sender_address: string;
  timestamp: string;
  data: Record<string, unknown>;
  metadata: Record<string, unknown>;
  signature?: string | null;
  public_key?: string | null;
}

export interface BlockRecord {
  index: number;
  previous_hash: string;
  timestamp: string;
  nonce: number;
  difficulty: number;
  merkle_root: string;
  block_hash: string;
  transactions: TransactionSummary[];
  transaction_count?: number;
}

export interface BlockchainListPayload {
  chain: BlockRecord[];
  height: number;
  is_valid: boolean;
}

export interface BlockchainValidation {
  is_valid: boolean;
  error: string | null;
  height: number;
}

export interface BlockchainStats {
  height: number;
  chain_length: number;
  total_blocks: number;
  total_transactions: number;
  pending_transactions: number;
  mempool_size: number;
  difficulty: number;
  current_difficulty: number;
  max_transactions_per_block: number;
  chain_valid: boolean;
  alerts?: {
    total_alerts: number;
    unresolved: number;
    by_severity: Record<string, number>;
  };
}

export interface MempoolPayload {
  transactions: TransactionSummary[];
  count: number;
  total_mempool: number;
}

export interface MineResult {
  block: BlockRecord;
  anomalies_found: number;
}

export interface HealthPayload {
  status: string;
  blockchain_height: number;
  mempool_size: number;
  detector_trained: boolean;
  alerts_unresolved: number;
}

