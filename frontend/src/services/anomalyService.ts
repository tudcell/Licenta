import { apiClient } from "./http";
import { unwrapApiData } from "./apiUtils";
import type { ApiSuccess } from "../types/api";
import type {
  AnomalyStatsPayload,
  DemoGeneratePayload,
  DemoGenerateResult,
  RetrainDetectorResult,
  TrainDetectorPayload,
  TrainDetectorResult,
} from "../types/anomaly";

export const anomalyService = {
  async getStats(): Promise<AnomalyStatsPayload> {
    const response = await apiClient.get<ApiSuccess<AnomalyStatsPayload>>("/api/anomaly/stats");
    return unwrapApiData(response);
  },

  async train(payload: TrainDetectorPayload): Promise<TrainDetectorResult> {
    const response = await apiClient.post<ApiSuccess<TrainDetectorResult>>("/api/anomaly/train", payload);
    return unwrapApiData(response);
  },

  async retrain(): Promise<RetrainDetectorResult> {
    const response = await apiClient.post<ApiSuccess<RetrainDetectorResult>>("/api/anomaly/retrain");
    return unwrapApiData(response);
  },

  async generateDemo(payload: DemoGeneratePayload): Promise<DemoGenerateResult> {
    const response = await apiClient.post<ApiSuccess<DemoGenerateResult>>("/api/demo/generate", payload);
    return unwrapApiData(response);
  },
};

