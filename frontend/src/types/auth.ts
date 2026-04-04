export type UserRole = "admin" | "operator" | "viewer";

export interface AuthUser {
  username: string;
  role: UserRole;
  walletName: string | null;
}

export interface LoginPayload {
  username: string;
  password: string;
}

export interface LoginResponse {
  accessToken: string;
  refreshToken: string;
  user: AuthUser;
}

