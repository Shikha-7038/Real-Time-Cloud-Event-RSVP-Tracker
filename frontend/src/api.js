// api.js - thin fetch wrapper. In dev, Vite proxies /api to the FastAPI
// backend (see vite.config.js); in production, set VITE_API_BASE.

const API_BASE = import.meta.env.VITE_API_BASE || "/api";
export const WS_BASE = import.meta.env.VITE_WS_BASE || `${location.origin.replace(/^http/, "ws")}/ws`;

export function getToken() {
  return localStorage.getItem("token");
}

let _cachedRaw = null;
let _cachedUser = null;

export function getUser() {
  const raw = localStorage.getItem("user");
  if (raw !== _cachedRaw) {
    _cachedRaw = raw;
    _cachedUser = raw ? JSON.parse(raw) : null;
  }
  return _cachedUser;
}

export function saveSession(token, user) {
  localStorage.setItem("token", token);
  localStorage.setItem("user", JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
}

export async function apiRequest(path, { method = "GET", body = null, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && getToken()) headers["Authorization"] = `Bearer ${getToken()}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  let data = null;
  try { data = await res.json(); } catch (e) { data = null; }

  if (!res.ok) {
    const message = (data && data.message) || (data && data.error) || `Request failed (${res.status})`;
    const err = new Error(message);
    err.status = res.status;
    throw err;
  }
  return data;
}

export function fmtDate(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  if (isNaN(d)) return dateStr;
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}
