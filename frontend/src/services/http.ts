import axios, { AxiosError } from "axios";

import { env } from "../config/env";
import { ApiError, type ApiErrorShape, type ApiSuccess } from "../types/api";
import { authStorage } from "./storage";

const SESSION_EXPIRED_EVENT = "auth:session-expired";

declare module "axios" {
  export interface AxiosRequestConfig {
    skipAuth?: boolean;
  }

  export interface InternalAxiosRequestConfig {
    skipAuth?: boolean;
    _retry?: boolean;
  }
}

export const apiClient = axios.create({
  baseURL: env.apiBaseUrl,
  timeout: 15000,
});

const refreshClient = axios.create({
  baseURL: env.apiBaseUrl,
  timeout: 15000,
});

apiClient.interceptors.request.use((config) => {
  if (!config.skipAuth) {
    const token = authStorage.getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiErrorShape>) => {
    const originalRequest = error.config;
    if (!originalRequest) {
      throw normalizeApiError(error);
    }

    const requestPath = originalRequest.url ?? "";
    const statusCode = error.response?.status;
    const canRefresh = !originalRequest._retry && statusCode === 401;
    const isAuthEndpoint = requestPath.includes("/api/auth/login") || requestPath.includes("/api/auth/refresh");

    if (canRefresh && !isAuthEndpoint) {
      const refreshToken = authStorage.getRefreshToken();
      if (refreshToken) {
        originalRequest._retry = true;
        try {
          const refreshResponse = await refreshClient.post<ApiSuccess<{ access_token: string }>>(
            "/api/auth/refresh",
            {},
            {
              headers: { Authorization: `Bearer ${refreshToken}` },
              skipAuth: true,
            },
          );

          const newToken = refreshResponse.data.data?.access_token;
          if (newToken) {
            authStorage.setAccessToken(newToken);
            originalRequest.headers.Authorization = `Bearer ${newToken}`;
            return apiClient(originalRequest);
          }
        } catch {
          authStorage.clear();
          window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
        }
      }
    }

    throw normalizeApiError(error);
  },
);

export function normalizeApiError(error: unknown): ApiError {
  if (error instanceof ApiError) {
    return error;
  }

  if (axios.isAxiosError<ApiErrorShape>(error)) {
    const payload = error.response?.data?.error;
    if (payload) {
      return new ApiError(payload);
    }

    if (error.code === "ERR_NETWORK") {
      return new ApiError({
        message: "Cannot reach backend API. Ensure Flask is running at the configured VITE_API_BASE_URL.",
        status_code: 503,
        code: "NETWORK_ERROR",
      });
    }

    return new ApiError({
      message: error.message || "Request failed",
      status_code: error.response?.status ?? 500,
      code: "HTTP_ERROR",
    });
  }

  if (error instanceof Error) {
    return new ApiError({ message: error.message, status_code: 500, code: "UNEXPECTED_ERROR" });
  }

  return new ApiError({ message: "Unexpected error", status_code: 500, code: "UNEXPECTED_ERROR" });
}

export { SESSION_EXPIRED_EVENT };

