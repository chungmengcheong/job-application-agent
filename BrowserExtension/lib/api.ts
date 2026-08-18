// Remove the Chrome reference type as it's causing build issues
// Instead we'll use a declaration file

// Safely detect Chrome extension environment - use a function to prevent build-time errors
function isChromeExtension(): boolean {
  try {
    return typeof window !== 'undefined' &&
           typeof (window as any).chrome !== 'undefined' &&
           typeof (window as any).chrome.runtime !== 'undefined' &&
           typeof (window as any).chrome.runtime.id === 'string';
  } catch {
    return false;
  }
}

// Authentication configuration
// bounce needed since chrome extension wasn't binding properly in Google Cloud Console
const CHROME_EXTENSION_CLIENT_ID =
  '258289407737-mdh4gleu91oug8f5g8jqkt75f62te9kv.apps.googleusercontent.com'; // for airecruitingagent.pythonanywhere.com
const AUTH_REDIRECT_URI = 'https://airecruitingagent.pythonanywhere.com/oauth2cb';
const OAUTH_STATE_KEY = "ai_recruiting_agent_oauth_state";
const OAUTH_NONCE_KEY = "ai_recruiting_agent_oauth_nonce";

export const AUTH_CONFIG = {
  clientId: CHROME_EXTENSION_CLIENT_ID,              // <- explicit, no manifest dependency
  authUrl: 'https://accounts.google.com/o/oauth2/v2/auth',
  scope: 'email profile',
  responseType: 'token id_token',
  // ⚠ remove redirectUri from here to avoid accidental use
};

// Auth token storage key
const TOKEN_STORAGE_KEY = "ai_recruiting_agent_auth";

// Auth token interface
interface AuthToken {
  accessToken: string;
  idToken: string;
  expiresAt: number;
}

// ---- Lightweight API response types ----
// postReview (Call 1) returns Fit/Gap_Map/Questions, no Tailored_Resume.
// postQuestions (Call 2) returns Fit/Gap_Map/Tailored_Resume, no Questions.
export interface ReviewResponse {
  Tailored_Resume?: string;
  Fit?: { score?: number; rationale?: string };
  Gap_Map?: Array<{
    "JD Requirement/Keyword": string;
    "Present in Resume?": "Y" | "N";
    "Where/Evidence": string;
    "Gap handling": string;
  }>;
  Questions?: string[];
  error?: string;
}

export interface ResumeResponse {
  resume?: string;
  error?: string;
}

export interface JobDescriptionResponse {
  job_description?: string;
  error?: string;
}

// --- Backend URL override (dev helper) --------------------------------------
export type BackendMode = "auto" | "local";
const BACKEND_MODE_KEY = "ai_recruiting_agent_backend_mode"; // 'auto' | 'local'
const BACKEND_LOCAL_URL = "http://127.0.0.1:8000";

export function getBackendMode(): BackendMode {
  try {
    if (typeof window !== "undefined") {
      const winMode = (window as any).__BACKEND_MODE as BackendMode | undefined;
      if (winMode === "local" || winMode === "auto") return winMode;
      const ls = typeof localStorage !== "undefined" ? localStorage.getItem(BACKEND_MODE_KEY) : null;
      if (ls === "local" || ls === "auto") return ls as BackendMode;
    }
  } catch {}
  return "auto";
}

export async function setBackendMode(mode: BackendMode): Promise<void> {
  try {
    if (typeof window !== "undefined") {
      (window as any).__BACKEND_MODE = mode;
      try { localStorage.setItem(BACKEND_MODE_KEY, mode); } catch {}
      try {
        if ((window as any).chrome?.storage?.local) {
          await new Promise<void>(resolve => {
            (window as any).chrome.storage.local.set({ [BACKEND_MODE_KEY]: mode }, () => resolve());
          });
        }
      } catch {}
    }
  } catch {}
}

function getBackendUrl(): string {
  // 1) Dev override first
  const mode = getBackendMode();
  if (mode === "local") return BACKEND_LOCAL_URL;

  // 2) Build-time injected value
  try {
    if (typeof window !== "undefined" && (window as any).__BACKEND_URL__) {
      return (window as any).__BACKEND_URL__ as string;
    }
  } catch {}

  // 3) Env (at build time)
  try {
    const pe = (typeof process !== "undefined" ? (process as any).env : undefined);
    if (pe?.NEXT_PUBLIC_BACKEND_URL) return pe.NEXT_PUBLIC_BACKEND_URL as string; // for vercel
    if (pe?.BACKEND_URL) return pe.BACKEND_URL as string;
  } catch {}

  // 4) Default (prod)
  return "https://airecruitingagent.pythonanywhere.com";
}

// Get stored auth token
export async function getAuthToken(): Promise<AuthToken | null> {
  try {
    if (isChromeExtension() && (window as any).chrome?.storage) {
      return new Promise((resolve) => {
        (window as any).chrome.storage.local.get(TOKEN_STORAGE_KEY, (result: any) => {
          const token = result[TOKEN_STORAGE_KEY];
          if (token && token.expiresAt > Date.now()) {
            resolve(token);
          } else {
            resolve(null);
          }
        });
      });
    }
  } catch {
    // Ignore errors during build time
  }

  if (typeof window !== "undefined") {
    try {
      const tokenStr = localStorage.getItem(TOKEN_STORAGE_KEY);
      if (!tokenStr) return null;

      const token = JSON.parse(tokenStr);
      if (token && token.expiresAt > Date.now()) {
        return token;
      }
    } catch {
      // Ignore localStorage errors
    }
  }
  return null;
}

// Save auth token
export async function saveAuthToken(token: AuthToken): Promise<void> {
  try {
    if (isChromeExtension() && (window as any).chrome?.storage) {
      return new Promise((resolve) => {
        (window as any).chrome.storage.local.set({ [TOKEN_STORAGE_KEY]: token }, resolve);
      });
    }
  } catch {
    // Ignore errors during build time
  }

  if (typeof window !== "undefined") {
    try {
      localStorage.setItem(TOKEN_STORAGE_KEY, JSON.stringify(token));
    } catch {
      // Ignore localStorage errors
    }
  }
}

// Clear auth token
export async function clearAuthToken(): Promise<void> {
  try {
    if (isChromeExtension() && (window as any).chrome?.storage) {
      return new Promise((resolve) => {
        (window as any).chrome.storage.local.remove(TOKEN_STORAGE_KEY, resolve);
      });
    }
  } catch {
    // Ignore errors during build time
  }

  if (typeof window !== "undefined") {
    try {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    } catch {
      // Ignore localStorage errors
    }
  }
}

// Token store utility (DRY wrapper around get/save/clear)
export const tokenStore = {
  get: async () => getAuthToken(),
  set: async (token: AuthToken) => saveAuthToken(token),
  clear: async () => clearAuthToken(),
};

// Initiate Google OAuth login

function rand(n = 24): string {
  const arr = new Uint8Array(n);
  crypto.getRandomValues(arr);
  // Use Array.from to convert Uint8Array to number[] for String.fromCharCode
  return btoa(String.fromCharCode(...Array.from(arr)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}


export async function login(): Promise<AuthToken | null> {
    try {
        if (isChromeExtension() && (window as any).chrome?.identity) {
            const redirectUri = AUTH_REDIRECT_URI;

            // Hard-code client id to avoid manifest/env fallbacks during debug
            const CLIENT_ID = CHROME_EXTENSION_CLIENT_ID;
            // Required when requesting id_token
            const state = rand();
            const nonce = rand();

            // Sanity checks & debug
            console.log("[OAuth] runtime.id:", (window as any).chrome.runtime.id);
            console.log("[OAuth] using redirectUri:", redirectUri);
            console.log("[OAuth] client_id:", CLIENT_ID);

            // Build the auth URL ONCE
            const params = new URLSearchParams({
                client_id: CLIENT_ID,
                redirect_uri: redirectUri,
                response_type: "token id_token",
                scope: "openid email profile",
                prompt: "consent",
                state,
                nonce,
            });
            const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;
            console.log("[OAuth] authUrl:", authUrl);

            // Launch flow
            const responseUrl = await new Promise<string>((resolve, reject) => {
                (window as any).chrome.identity.launchWebAuthFlow(
                    {url: authUrl, interactive: true},
                    (redirectedTo?: string) => {
                        console.log("[OAuth] redirectedTo:", redirectedTo);
                        if ((window as any).chrome.runtime.lastError) {
                            return reject(new Error((window as any).chrome.runtime.lastError.message));
                        }
                        if (!redirectedTo) return reject(new Error("No response URL returned from auth flow"));
                        resolve(redirectedTo);
                    }
                );
            });

            // Parse fragment (#...)
            const hash = (new URL(responseUrl)).hash.replace(/^#/, "");
            const q = new URLSearchParams(hash);

            // Handle errors first
            const err = q.get("error");
            if (err) {
                const desc = q.get("error_description") || "";
                console.error("[OAuth] error:", err, desc);
                return null;
            }

            // Validate state
            if (q.get("state") !== state) {
                console.error("[OAuth] state mismatch");
                return null;
            }

            const accessToken = q.get("access_token");
            const idToken = q.get("id_token");
            const expiresIn = q.get("expires_in");

            if (!accessToken || !idToken || !expiresIn) {
                console.error("Invalid authentication response:", {accessToken, idToken, expiresIn});
                return null;
            }

            const expiresAt = Date.now() + parseInt(expiresIn, 10) * 1000;
            const token = {accessToken, idToken, expiresAt};
            await tokenStore.set(token);
            return token;
        }
    } catch (e) {
        console.error("Login error:", e);
    }

// Optional non-extension fallback (web)
    if (typeof window !== "undefined") {
        const fallbackRedirect = `${window.location.origin}/auth-callback`;

        // Generate and persist state + nonce for verification on return
        const state = rand();
        const nonce = rand();
        try {
            sessionStorage.setItem(OAUTH_STATE_KEY, state);
            sessionStorage.setItem(OAUTH_NONCE_KEY, nonce);
        } catch {
        }

        const params = new URLSearchParams({
            client_id: AUTH_CONFIG.clientId,
            redirect_uri: fallbackRedirect,
            response_type: "token id_token",
            scope: "openid email profile",          // <-- include 'openid'
            prompt: "consent",
            state,                                   // <-- add state
            nonce,                                   // <-- add nonce (required for id_token)
        });

        window.location.href = `${AUTH_CONFIG.authUrl}?${params.toString()}`;
        return null;
    }
    // Explicit final return for SSR/build or non-browser contexts
    return null;
}

// Logout
export async function logout(): Promise<void> {
  await tokenStore.clear();
}

export async function checkUserAuthentication(): Promise<boolean> {
  try {
    const token = await getAuthToken();
    // Use direct return of comparison result
    return token !== null;
  } catch (error) {
    console.error("Authentication check failed:", error);
    return false;
  }
}

// Unified error handler for fetch responses
async function handleErrorResponse(res: Response): Promise<never> {
  // Clear token only on 401 (auth problem), not on 403 (authorization)
  if (res.status === 401) {
    await tokenStore.clear();
  }

  let message: string | undefined;

  // Try JSON first — but don't throw inside this try/catch,
  // because it would be caught below and we'd lose the message.
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") {
        message = body.detail;
      } else if (typeof body?.message === "string") {
        message = body.message;
      } else if (body != null) {
        // last-resort: stringify the JSON object so we at least surface something useful
        message = JSON.stringify(body);
      }
    } catch {
      // fall through to text branch
    }
  }

  // If we still don't have a message (non-JSON or JSON parse failed), try text
  if (!message) {
    try {
      const text = await res.text();
      if (text) {
        message = text;
      }
    } catch {
      // ignore; we'll fall back to status code
    }
  }

  // Final fallback
  if (!message) {
    message = `HTTP ${res.status}`;
  }

  throw new Error(message);
}

// Helper to add auth token to fetch options (uses tokenStore)
async function addAuthHeader(init: RequestInit = {}): Promise<RequestInit> {
  const token = await tokenStore.get();
  if (!token) return init;
  const headers = new Headers(init.headers || {});
  headers.set("Authorization", `Bearer ${token.idToken}`);
  return { ...init, headers };
}

// --- Unified fetch & retry helpers ---
type ParseMode = "json" | "text" | "raw";

async function apiFetch<T = unknown>(
  path: string,
  init: RequestInit = {},
  opts: { auth?: boolean; timeoutMs?: number; parse?: ParseMode } = {},
): Promise<T extends void ? never : T> {
  const { auth = true, timeoutMs = 30000, parse = "json" } = opts;

  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const base = getBackendUrl();
    const withAuth = auth ? await addAuthHeader(init) : init;
    const res = await fetch(`${base}${path}`, { ...withAuth, signal: controller.signal });
    if (!res.ok) {
      await handleErrorResponse(res); // throws
    }
    if (parse === "raw") return res as any;
    if (parse === "text") return (await res.text()) as any;
    return (await res.json()) as any;
  } finally {
    clearTimeout(id);
  }
}

type RetryOpts = { retries?: number; delayMs?: number; shouldRetry?: (e: unknown) => boolean };

async function withRetry<T>(fn: () => Promise<T>, opts: RetryOpts = {}) {
  const { retries = 0, delayMs = 2000, shouldRetry = () => true } = opts;
  let lastError: unknown;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await fn();
    } catch (e) {
      lastError = e;
      if (attempt === retries || !shouldRetry(e)) break;
      await new Promise(r => setTimeout(r, delayMs));
    }
  }
  throw lastError;
}

export async function postReview({
  jobDescription,
  url,
  demo,
}: { jobDescription: string; url: string; demo?: boolean }): Promise<ReviewResponse> {
  return withRetry(
    () => apiFetch<ReviewResponse>("/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_description: jobDescription,
        url,
        demo: !!demo,
      }),
    }, { auth: true, timeoutMs: 150000, parse: "json" }),
    {
      retries: 0,
      delayMs: 2000,
      shouldRetry: (e) => {
        const msg = String((e as Error)?.message || "");
        return !(msg.includes("401") || msg.includes("403") || msg.toLowerCase().includes("authentication"));
      }
    }
  );
}

export async function postQuestions({
  qa_pairs,
  demo,
}: {
  qa_pairs: Array<{ question: string; answer: string }>;
  demo?: boolean;
}): Promise<ReviewResponse> {
  return withRetry(
    () => apiFetch<ReviewResponse>("/questions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ qa_pairs, demo: !!demo }),
    }, { auth: true, timeoutMs: 150000, parse: "json" }),
    {
      retries: 0,
      delayMs: 2000,
      shouldRetry: (e) => {
        const msg = String((e as Error)?.message || "");
        return !(msg.includes("401") || msg.includes("403") || msg.toLowerCase().includes("authentication"));
      }
    }
  );
}

export function cleanMarkdown(md: string): string {
  if (!md) return md

  try {
    return (
      md
        // Remove <del>...</del> tags
        .replace(/<del[^>]*>.*?<\/del>/gi, "")
        // Remove <ins>...</ins> tags and keep content
        .replace(/<ins[^>]*>(.*?)<\/ins>/gi, "$1")
        // Remove markdown strikethrough ~~...~~
        .replace(/~~(.*?)~~/g, "")
        // Remove <span class="add">...</span> and keep content
        .replace(/<span\s+class=["']add["'][^>]*>(.*?)<\/span>/gi, "$1")
        // Remove <span class="del">...</span>
        .replace(/<span\s+class=["']del["'][^>]*>.*?<\/span>/gi, "")
        // Remove <add>...</add> tags and keep content
        .replace(/<add>(.*?)<\/add>/gi, "$1")
        // Remove <span style="color:#...">...</span> and keep content
        .replace(/<span style="color:#[0-9a-f]+">(.*?)<\/span>/gi, "$1")
        // Remove any remaining HTML tags
        .replace(/<[^>]*>/g, "")
        // Clean up extra whitespace
        .replace(/\n\s*\n\s*\n/g, "\n\n")
        .trim()
    )
  } catch {
    return md
  }
}

export async function getCurrentTabUrl(): Promise<string> {
  try {
    if (isChromeExtension() && (window as any).chrome?.tabs) {
      return await new Promise<string>((resolve) => {
        try {
          (window as any).chrome.tabs.query({ active: true, currentWindow: true }, (tabs: any[]) => {
            const lastErr = (window as any).chrome?.runtime?.lastError;
            if (lastErr) {
              console.warn("[tabs.query] lastError:", lastErr.message || lastErr);
              // Fall back to the panel's own URL so we never reject on load
              resolve(typeof window !== "undefined" ? window.location.href : "");
              return;
            }
            resolve(tabs?.[0]?.url || (typeof window !== "undefined" ? window.location.href : ""));
          });
        } catch (inner) {
          console.warn("[tabs.query] threw synchronously:", inner);
          resolve(typeof window !== "undefined" ? window.location.href : "");
        }
      });
    }
  } catch (e) {
    // Fallback for non-extension environment or during build
    console.warn("[getCurrentTabUrl] outer try/catch:", e);
  }
  return typeof window !== "undefined" ? window.location.href : "";
}

export function getJobDescription({ url, demo }: { url: string; demo?: boolean }): Promise<JobDescriptionResponse> {
  return withRetry(
    () => apiFetch<JobDescriptionResponse>("/jobdescription", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ url, demo: !!demo }),
    }, { auth: false, timeoutMs: 30000, parse: "json" }),
    {
      retries: 1,
      delayMs: 2000,
      shouldRetry: (e) => {
        const msg = String((e as Error)?.message || "");
        // Retry most network-ish failures; job description is public/unauth
        return !(msg.includes("401") || msg.includes("403"));
      }
    }
  );
}

export function manageResume(
  { action = "load", demo = false }: { action?: string; demo?: boolean } = {}
): Promise<ResumeResponse> {
  const qs = new URLSearchParams({ command: action, demo: String(!!demo) });
  return withRetry(
    () => apiFetch<ResumeResponse>(`/resume?${qs.toString()}`, {
      method: "GET",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
    }, { auth: true, timeoutMs: 30000, parse: "json" }),
    {
      retries: 1,
      delayMs: 2000,
      shouldRetry: (e) => {
        const msg = String((e as Error)?.message || "");
        return !(msg.includes("401") || msg.includes("403") || msg.toLowerCase().includes("authentication"));
      }
    }
  );
}
