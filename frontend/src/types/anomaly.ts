export interface AnomalyStatsPayload {
  blockchain: Record<string, unknown>;
  analysis: {
    total_analyzed: number;
    alerts_count: number;
    blockchain_length: number;
    clean_training_candidates: number;
    detector_fitted: boolean;
    detector_trained: boolean;
    training_samples: number;
    trained_at?: string;
  };
  anomaly_detection: Record<string, unknown>;
  persistent_alerts: {
    total_alerts: number;
    unresolved: number;
    by_severity: Record<string, number>;
  };
}

export interface TrainDetectorPayload {
  mode?: "blockchain" | "synthetic";
  use_synthetic?: boolean;
  sample_count?: number;
}

export interface TrainDetectorResult {
  training_mode: string;
  training_samples: number;
  stats: Record<string, unknown>;
  model_saved: string;
  detector_fitted: boolean;
}

export interface RetrainDetectorResult {
  training_mode: string;
  window_size: number;
  indexed_non_flagged: number;
  matched_transactions: number;
  training_samples: number;
  stats: Record<string, unknown>;
  model_saved: string;
  detector_fitted: boolean;
}

export interface DemoGeneratePayload {
  count?: number;
  include_anomalies?: boolean;
  anomaly_ratio?: number;
}

export interface DemoGenerateResult {
  generated: number;
  anomalies_detected: number;
  flagged: number;
  invalid_signatures: number;
}

