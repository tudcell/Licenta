import { create } from "zustand";

import { authService } from "../services/authService";
import { authStorage } from "../services/storage";
import { normalizeApiError } from "../services/http";
import type { AuthUser, LoginPayload, UserRole } from "../types/auth";

export type AuthStatus = "idle" | "authenticating" | "authenticated" | "refreshing";

interface AuthState {
  status: AuthStatus;
  accessToken: string | null;
  refreshToken: string | null;
  user: AuthUser | null;
  error: string | null;
  isBootstrapped: boolean;
  login: (payload: LoginPayload) => Promise<void>;
  bootstrap: () => Promise<void>;
  logout: () => Promise<void>;
  consumeSessionExpired: () => void;
  hasAnyRole: (roles: UserRole[]) => boolean;
}

const clearAuthState = (): Pick<AuthState, "status" | "accessToken" | "refreshToken" | "user"> => ({
  status: "idle",
  accessToken: null,
  refreshToken: null,
  user: null,
});

export const useAuthStore = create<AuthState>((set, get) => ({
  ...clearAuthState(),
  error: null,
  isBootstrapped: false,

  async login(payload) {
    set({ status: "authenticating", error: null });
    try {
      const result = await authService.login(payload);
      authStorage.setAccessToken(result.accessToken);
      authStorage.setRefreshToken(result.refreshToken);
      authStorage.setUser(result.user);
      set({
        status: "authenticated",
        accessToken: result.accessToken,
        refreshToken: result.refreshToken,
        user: result.user,
        error: null,
        isBootstrapped: true,
      });
    } catch (error) {
      const normalized = normalizeApiError(error);
      authStorage.clear();
      set({ ...clearAuthState(), error: normalized.message, isBootstrapped: true });
      throw normalized;
    }
  },

  async bootstrap() {
    if (get().isBootstrapped) {
      return;
    }

    const storedAccessToken = authStorage.getAccessToken();
    const storedRefreshToken = authStorage.getRefreshToken();
    const storedUser = authStorage.getUser();

    if (!storedRefreshToken || !storedUser) {
      authStorage.clear();
      set({ ...clearAuthState(), isBootstrapped: true });
      return;
    }

    if (storedAccessToken) {
      set({
        status: "authenticated",
        accessToken: storedAccessToken,
        refreshToken: storedRefreshToken,
        user: storedUser,
        isBootstrapped: true,
        error: null,
      });
      return;
    }

    set({ status: "refreshing", refreshToken: storedRefreshToken, user: storedUser });
    try {
      const refreshedToken = await authService.refresh(storedRefreshToken);
      authStorage.setAccessToken(refreshedToken);
      set({
        status: "authenticated",
        accessToken: refreshedToken,
        refreshToken: storedRefreshToken,
        user: storedUser,
        isBootstrapped: true,
        error: null,
      });
    } catch {
      authStorage.clear();
      set({ ...clearAuthState(), isBootstrapped: true, error: "Your session has expired. Please sign in again." });
    }
  },

  async logout() {
    try {
      if (get().accessToken) {
        await authService.logout();
      }
    } catch {
      // Continue local cleanup even if backend logout fails.
    }

    authStorage.clear();
    set({ ...clearAuthState(), isBootstrapped: true, error: null });
  },

  consumeSessionExpired() {
    authStorage.clear();
    set({ ...clearAuthState(), isBootstrapped: true, error: "Session expired. Please sign in again." });
  },

  hasAnyRole(roles) {
    const role = get().user?.role;
    return Boolean(role && roles.includes(role));
  },
}));

