import type { AxiosResponse } from "axios";

import { ApiError, type ApiSuccess, type PaginationMeta, type PaginationQuery } from "../types/api";

export function toPaginationParams(query?: PaginationQuery): Record<string, number> {
  if (!query) {
    return {};
  }

  const params: Record<string, number> = {};
  if (query.page !== undefined) {
    params.page = query.page;
  }
  if (query.perPage !== undefined) {
    params.per_page = query.perPage;
  }
  return params;
}

export function unwrapApiData<T>(response: AxiosResponse<ApiSuccess<T>>): T {
  const payload = response.data.data;
  if (payload === undefined) {
    throw new ApiError({
      message: "Response payload is missing 'data'.",
      status_code: response.status,
      code: "INVALID_RESPONSE",
    });
  }
  return payload;
}

export function unwrapApiDataOptional<T>(response: AxiosResponse<ApiSuccess<T>>): T | null {
  if (response.data.data === undefined) {
    return null;
  }
  return response.data.data;
}

export interface PaginatedResult<T> {
  data: T;
  pagination: PaginationMeta;
}

export function unwrapPaginatedData<T>(response: AxiosResponse<ApiSuccess<T>>): PaginatedResult<T> {
  const data = unwrapApiData(response);
  const pagination = response.data.pagination;

  if (!pagination) {
    throw new ApiError({
      message: "Response payload is missing 'pagination'.",
      status_code: response.status,
      code: "INVALID_RESPONSE",
    });
  }

  return { data, pagination };
}


