import { apiClient } from "./http";
import { toPaginationParams, unwrapApiData, unwrapPaginatedData, type PaginatedResult } from "./apiUtils";
import type { ApiSuccess, PaginationQuery } from "../types/api";
import type {
  CreateTransactionPayload,
  CreateTransactionResult,
  TransactionAuditReport,
  TransactionDetailPayload,
  TransactionFilters,
  TransactionListPayload,
} from "../types/transactions";

const toTransactionFilterParams = (filters?: TransactionFilters): Record<string, string | number | boolean> => {
  if (!filters) {
    return {};
  }

  const params: Record<string, string | number | boolean> = {};
  if (filters.type) {
    params.type = filters.type;
  }
  if (filters.sender) {
    params.sender = filters.sender;
  }
  if (filters.status) {
    params.status = filters.status;
  }
  if (filters.flagged !== undefined) {
    params.flagged = filters.flagged;
  }
  return params;
};

export const transactionsService = {
  async list(query?: PaginationQuery & TransactionFilters): Promise<PaginatedResult<TransactionListPayload>> {
    const response = await apiClient.get<ApiSuccess<TransactionListPayload>>("/api/transactions", {
      params: {
        ...toPaginationParams(query),
        ...toTransactionFilterParams(query),
      },
    });
    return unwrapPaginatedData(response);
  },

  async getById(transactionId: string): Promise<TransactionDetailPayload> {
    const response = await apiClient.get<ApiSuccess<TransactionDetailPayload>>(`/api/transaction/${transactionId}`);
    return unwrapApiData(response);
  },

  async create(payload: CreateTransactionPayload): Promise<CreateTransactionResult> {
    const response = await apiClient.post<ApiSuccess<CreateTransactionResult>>("/api/transaction", payload);
    return unwrapApiData(response);
  },

  async analyze(transactionId: string): Promise<TransactionAuditReport> {
    const response = await apiClient.get<ApiSuccess<TransactionAuditReport>>(`/api/transaction/analyze/${transactionId}`);
    return unwrapApiData(response);
  },
};

