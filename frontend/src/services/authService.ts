import { apiClient } from "./http";
import type { ApiSuccess } from "../types/api";
import type { AuthUser, LoginPayload, LoginResponse } from "../types/auth";

interface LoginApiUser {
  username: string;
  role: AuthUser["role"];
  wallet_name?: string | null;
}

interface LoginApiPayload {
  access_token: string;
  refresh_token: string;
  user: LoginApiUser;
}

interface RefreshPayload {
  access_token: string;
}

const mapUser = (user: LoginApiUser): AuthUser => ({
  username: user.username,
  role: user.role,
  walletName: user.wallet_name ?? null,
});

export const authService = {
  async login(payload: LoginPayload): Promise<LoginResponse> {
    const response = await apiClient.post<ApiSuccess<LoginApiPayload>>("/api/auth/login", payload, { skipAuth: true });
    const data = response.data.data;
    if (!data) {
      throw new Error("Login response missing data payload");
    }

    return {
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
      user: mapUser(data.user),
    };
  },

  async refresh(refreshToken: string): Promise<string> {
    const response = await apiClient.post<ApiSuccess<RefreshPayload>>(
      "/api/auth/refresh",
      {},
      {
        headers: { Authorization: `Bearer ${refreshToken}` },
        skipAuth: true,
      },
    );

    const accessToken = response.data.data?.access_token;
    if (!accessToken) {
      throw new Error("Refresh response missing access token");
    }
    return accessToken;
  },

  async logout(): Promise<void> {
    await apiClient.post("/api/auth/logout", {});
  },
};

