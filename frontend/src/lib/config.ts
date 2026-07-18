// Central place for environment-derived URLs. If NEXT_PUBLIC_WS_URL is not set
// we derive the WebSocket origin from the API URL (http->ws, https->wss).

export const API_BASE =
  (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export const API_V1 = `${API_BASE}/api/v1`;

export const WS_BASE = (() => {
  if (process.env.NEXT_PUBLIC_WS_URL) return process.env.NEXT_PUBLIC_WS_URL.replace(/\/$/, "");
  return API_BASE.replace(/^http/, "ws");
})();

export const TOKEN_KEY = "signal_access_token";
export const THEME_KEY = "signal_theme";
