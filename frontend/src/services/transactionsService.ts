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
    const normalizedType = filters.type.trim().toUpperCase();
    if (normalizedType) {
      params.type = normalizedType;
    }
  }
  if (filters.sender) {
    const normalizedSender = filters.sender.trim();
    if (normalizedSender) {
      params.sender = normalizedSender;
    }
  }
  if (filters.status) {
    const normalizedStatus = filters.status.trim().toUpperCase();
    if (normalizedStatus) {
      params.status = normalizedStatus;
    }
  }
  if (filters.flagged !== undefined) {
    params.flagged = filters.flagged;
  }
  if (filters.transaction_id) {
    const normalizedId = filters.transaction_id.trim();
    if (normalizedId) {
      params.transaction_id = normalizedId;
    }
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

