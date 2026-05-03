import { apiClient } from "./http";
import { toPaginationParams, unwrapApiData, unwrapPaginatedData, type PaginatedResult } from "./apiUtils";
import type { ApiSuccess, PaginationQuery } from "../types/api";
import type {
  BlockRecord,
  BlockchainListPayload,
  BlockchainStats,
  BlockchainValidation,
  HealthPayload,
  MempoolPayload,
  MineResult,
} from "../types/blockchain";

export const blockchainService = {
  async getHealth(): Promise<HealthPayload> {
    const response = await apiClient.get<ApiSuccess<HealthPayload>>("/api/health", { skipAuth: true });
    return unwrapApiData(response);
  },

  async getBlockchain(query?: PaginationQuery): Promise<PaginatedResult<BlockchainListPayload>> {
    const response = await apiClient.get<ApiSuccess<BlockchainListPayload>>("/api/blockchain", {
      params: toPaginationParams(query),
    });
    return unwrapPaginatedData(response);
  },

  async getStats(): Promise<BlockchainStats> {
    const response = await apiClient.get<ApiSuccess<BlockchainStats>>("/api/blockchain/stats");
    return unwrapApiData(response);
  },

  async validate(): Promise<BlockchainValidation> {
    const response = await apiClient.get<ApiSuccess<BlockchainValidation>>("/api/blockchain/validate");
    return unwrapApiData(response);
  },

  async getBlock(index: number): Promise<BlockRecord> {
    const response = await apiClient.get<ApiSuccess<BlockRecord>>(`/api/block/${index}`);
    return unwrapApiData(response);
  },

  async mine(): Promise<MineResult> {
    const response = await apiClient.post<ApiSuccess<MineResult>>("/api/mine", {});
    return unwrapApiData(response);
  },

  async getMempool(query?: PaginationQuery): Promise<PaginatedResult<MempoolPayload>> {
    const response = await apiClient.get<ApiSuccess<MempoolPayload>>("/api/mempool", {
      params: toPaginationParams(query),
    });
    return unwrapPaginatedData(response);
  },
};

