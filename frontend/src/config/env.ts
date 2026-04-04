const normalizeUrl = (value: string) => value.replace(/\/$/, "");

export const env = {
  apiBaseUrl: normalizeUrl(import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:5000"),
  socketUrl: normalizeUrl(import.meta.env.VITE_SOCKET_URL ?? import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:5000"),
};

