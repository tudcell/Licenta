import { apiClient } from "./http";
import { toPaginationParams, unwrapApiDataOptional, unwrapPaginatedData, type PaginatedResult } from "./apiUtils";
import type { ApiSuccess, PaginationQuery } from "../types/api";
import type { AlertFilters, AlertsListPayload } from "../types/alerts";

const toAlertFilterParams = (filters?: AlertFilters): Record<string, string | boolean> => {
  if (!filters) {
    return {};
  }

  const params: Record<string, string | boolean> = {};
  if (filters.severity) {
    params.severity = filters.severity;
  }
  if (filters.resolved !== undefined) {
    params.resolved = filters.resolved;
  }
  return params;
};

export const alertsService = {
  async list(query?: PaginationQuery & AlertFilters): Promise<PaginatedResult<AlertsListPayload>> {
    const response = await apiClient.get<ApiSuccess<AlertsListPayload>>("/api/alerts", {
      params: {
        ...toPaginationParams(query),
        ...toAlertFilterParams(query),
      },
    });
    return unwrapPaginatedData(response);
  },

  async resolve(alertId: number): Promise<void> {
    const response = await apiClient.put<ApiSuccess<Record<string, never>>>(`/api/alerts/${alertId}/resolve`, {});
    unwrapApiDataOptional(response);
  },
};


