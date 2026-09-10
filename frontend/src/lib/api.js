import { toast } from "sonner";

// Fetch wrapper for the real backend. ARCHITECTURE.md §8/§10, BUILDPHASES.md
// "Frontend swap plan" — base URL, bearer header, single-flight refresh-on-401,
// error-envelope unwrapping. This is the one file every service body calls
// through; verifyService.js is the only caller that ever passes `auth: false`.

const BASE = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "");
const TOKEN_KEY = "dot_tokens_v1";

function readTokens() {
  try {
    const raw = localStorage.getItem(TOKEN_KEY);
    if (raw) return JSON.parse(raw);
  } catch (e) {
    // ignore corrupt storage
  }
  return { accessToken: null, refreshToken: null };
}

let tokens = readTokens();

export function getTokens() {
  return tokens;
}

export function setTokens(accessToken, refreshToken) {
  tokens = { accessToken, refreshToken };
  try {
    localStorage.setItem(TOKEN_KEY, JSON.stringify(tokens));
  } catch (e) {
    // ignore quota
  }
}

export function clearTokens() {
  tokens = { accessToken: null, refreshToken: null };
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch (e) {
    // ignore
  }
}

// Registered by authStore.js so this module never imports the store
// (would create a cycle). Called once a refresh attempt has genuinely
// failed — clears auth state and sends the user back to /login.
let unauthorizedHandler = () => {};
export function setUnauthorizedHandler(fn) {
  unauthorizedHandler = fn;
}

export class ApiError extends Error {
  constructor(message, { code, status, details, requestId } = {}) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
    this.requestId = requestId;
  }
}

// Single-flight refresh: concurrent 401s share one in-flight refresh call.
let refreshPromise = null;

async function performRefresh() {
  if (!tokens.refreshToken) {
    throw new ApiError("No refresh token available.", { code: "NO_REFRESH_TOKEN", status: 401 });
  }
  if (!refreshPromise) {
    refreshPromise = fetch(`${BASE}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refreshToken: tokens.refreshToken }),
    })
      .then(async (res) => {
        if (!res.ok) throw new ApiError("Refresh failed.", { status: res.status });
        const data = await res.json();
        setTokens(data.accessToken, data.refreshToken);
        return data;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

function sideEffectsFor(err) {
  // BUILDPHASES.md "Error conventions on the client". 409/422/401 are left
  // to call sites (domain messages, form-field mapping, refresh-and-retry
  // already handled below) — everything else gets a generic toast here so
  // no call site has to remember to handle it.
  switch (err.status) {
    case 403:
      toast.error("You do not have permission for this action.");
      break;
    case 429:
      toast.error("Too many requests. Please wait a moment.");
      break;
    default:
      if (err.status >= 500) {
        toast.error("Something went wrong on our end. Please try again.");
        if (err.requestId) console.error(`Request failed — requestId=${err.requestId}`);
      }
  }
}

async function parseErrorBody(res) {
  try {
    const payload = await res.json();
    const err = payload?.error || {};
    return { code: err.code, message: err.message, details: err.details, requestId: payload?.requestId };
  } catch (e) {
    return { code: undefined, message: res.statusText, details: undefined, requestId: undefined };
  }
}

/**
 * @param {string} path - e.g. "/batches" or "/batches/abc" (no /api prefix)
 * @param {object} opts
 * @param {"GET"|"POST"|"PATCH"|"DELETE"} [opts.method]
 * @param {object} [opts.body]
 * @param {boolean} [opts.auth] - attach Authorization header + refresh-on-401 (default true)
 */
export async function apiFetch(path, { method = "GET", body, auth = true } = {}) {
  const doCall = async () => {
    const headers = { "Content-Type": "application/json" };
    if (auth && tokens.accessToken) headers.Authorization = `Bearer ${tokens.accessToken}`;
    return fetch(`${BASE}/api${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  };

  let res = await doCall();

  if (res.status === 401 && auth) {
    try {
      await performRefresh();
    } catch (e) {
      unauthorizedHandler();
      throw new ApiError("Session expired. Please sign in again.", { code: "SESSION_EXPIRED", status: 401 });
    }
    res = await doCall();
    if (res.status === 401) {
      unauthorizedHandler();
      const info = await parseErrorBody(res);
      throw new ApiError(info.message || "Session expired. Please sign in again.", { ...info, status: 401 });
    }
  }

  if (!res.ok) {
    const info = await parseErrorBody(res);
    const err = new ApiError(info.message || `Request failed (${res.status}).`, { ...info, status: res.status });
    sideEffectsFor(err);
    throw err;
  }

  if (res.status === 204) return null;
  const text = await res.text();
  return text ? JSON.parse(text) : null;
}

export const apiGet = (path, opts) => apiFetch(path, { ...opts, method: "GET" });
export const apiPost = (path, body, opts) => apiFetch(path, { ...opts, method: "POST", body });
export const apiPatch = (path, body, opts) => apiFetch(path, { ...opts, method: "PATCH", body });
export const apiDelete = (path, opts) => apiFetch(path, { ...opts, method: "DELETE" });

// Multipart upload — the one request shape apiFetch doesn't cover (no JSON
// body, and the browser must set its own `Content-Type: multipart/
// form-data; boundary=...`, which setting it manually would break).
export async function apiUpload(path, file) {
  const form = new FormData();
  form.append("file", file);
  const headers = {};
  if (tokens.accessToken) headers.Authorization = `Bearer ${tokens.accessToken}`;

  const doCall = () => fetch(`${BASE}/api${path}`, { method: "POST", headers, body: form });
  let res = await doCall();

  if (res.status === 401) {
    try {
      await performRefresh();
    } catch (e) {
      unauthorizedHandler();
      throw new ApiError("Session expired. Please sign in again.", { code: "SESSION_EXPIRED", status: 401 });
    }
    res = await doCall();
  }

  if (!res.ok) {
    const info = await parseErrorBody(res);
    const err = new ApiError(info.message || `Upload failed (${res.status}).`, { ...info, status: res.status });
    sideEffectsFor(err);
    throw err;
  }
  return res.json();
}

// verifyService.js only — CLAUDE.md rule 4: /api/public/* never carries an
// auth header, ever, even if a token happens to be present.
export const publicGet = (path) => apiFetch(path, { method: "GET", auth: false });
export const publicPost = (path, body) => apiFetch(path, { method: "POST", body, auth: false });
