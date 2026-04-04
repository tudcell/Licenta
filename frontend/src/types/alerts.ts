import type { PaginationMeta } from "./api";

export interface AlertRecord {
  id: number;
  transaction_id: string;
  alert_type: string;
  severity: string;
  anomaly_score: number | null;
  confidence: number | null;
  explanation: string | null;
  is_resolved: number;
  created_at: string;
  resolved_at: string | null;
  resolved_by: string | null;
}

export interface AlertsListPayload {
  alerts: AlertRecord[];
  count: number;
}

export interface AlertsListResponse {
  data: AlertsListPayload;
  pagination: PaginationMeta;
}

export interface AlertFilters {
  severity?: string;
  resolved?: boolean;
}

