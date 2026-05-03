export interface ApiSuccess<T> {
  success: true;
  timestamp?: string;
  message?: string;
  data?: T;
  pagination?: PaginationMeta;
}

export interface PaginationMeta {
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface PaginationQuery {
  page?: number;
  perPage?: number;
}

export type PaginatedApiData<TListKey extends string, TItem> = {
  [K in TListKey]: TItem[];
} & {
  count?: number;
};

export interface ApiErrorPayload {
  message: string;
  code?: string;
  status_code: number;
  timestamp?: string;
  details?: Array<Record<string, unknown>>;
}

export interface ApiErrorShape {
  success: false;
  error: ApiErrorPayload;
  data?: unknown;
}

export class ApiError extends Error {
  readonly statusCode: number;
  readonly code?: string;
  readonly details?: Array<Record<string, unknown>>;

  constructor(payload: ApiErrorPayload) {
    super(payload.message);
    this.name = "ApiError";
    this.statusCode = payload.status_code;
    this.code = payload.code;
    this.details = payload.details;
  }
}

