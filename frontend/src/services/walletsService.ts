import { apiClient } from "./http";
import { toPaginationParams, unwrapApiData, unwrapPaginatedData, type PaginatedResult } from "./apiUtils";
import type { ApiSuccess, PaginationQuery } from "../types/api";
import type {
  CreateWalletPayload,
  CreateWalletResult,
  WalletDetailPayload,
  WalletDetailResponse,
  WalletListPayload,
} from "../types/wallets";

export const walletsService = {
  async list(query?: PaginationQuery): Promise<PaginatedResult<WalletListPayload>> {
    const response = await apiClient.get<ApiSuccess<WalletListPayload>>("/api/wallets", {
      params: toPaginationParams(query),
    });
    return unwrapPaginatedData(response);
  },

  async create(payload: CreateWalletPayload): Promise<CreateWalletResult> {
    const response = await apiClient.post<ApiSuccess<CreateWalletResult>>("/api/wallet", payload);
    return unwrapApiData(response);
  },

  async getByName(name: string, query?: PaginationQuery): Promise<WalletDetailResponse> {
    const response = await apiClient.get<ApiSuccess<WalletDetailPayload>>(`/api/wallet/${name}`, {
      params: toPaginationParams(query),
    });
    return unwrapPaginatedData(response);
  },
};

