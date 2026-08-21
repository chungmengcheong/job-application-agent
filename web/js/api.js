// Thin shared fetch helper for the durable /api/v1 review API, plus the one
// legacy authenticated `/resume` getter the live client still needs until
// Increment 3.5 adds stored resumes. Centralizes the auth header, timeouts,
// and safe-error-envelope parsing - not a schema-mirroring "typed" client;
// the backend already validates request/response shapes (backend/schemas.py).
import { clearAuthToken, getAuthToken } from "./auth.js";
import { apiUrl } from "./backend-mode.js";

// Matches today's budgets: the two model calls get a long timeout, everything
// else gets a short one.
const TIMEOUT_MODEL_CALL_MS = 150000;
const TIMEOUT_DEFAULT_MS = 30000;

function apiError(message, status) {
  const error = new Error(message);
  error.status = status;
  return error;
}

async function readSafeEnvelopeMessage(res) {
  try {
    const body = await res.json();
    if (typeof body?.error?.message === "string") return body.error.message;
  } catch {
    // fall through
  }
  return `HTTP ${res.status}`;
}

async function apiFetch(path, { method = "GET", body, timeoutMs = TIMEOUT_DEFAULT_MS } = {}) {
  const token = await getAuthToken();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(apiUrl(path), {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token.idToken}` } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    if (!res.ok) {
      if (res.status === 401) await clearAuthToken();
      throw apiError(await readSafeEnvelopeMessage(res), res.status);
    }
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

/**
 * @param {{resume: string, jobDescription: string, sourceUrl?: string}} input
 * @returns {Promise<{id, status, job_description, resume, questions, answers, result, safe_error_code, created_at, updated_at, completed_at}>} ReviewOut
 */
export function createReview({ resume, jobDescription, sourceUrl }) {
  return apiFetch("/api/v1/reviews", {
    method: "POST",
    body: { resume, job_description: jobDescription, source_url: sourceUrl || null },
    timeoutMs: TIMEOUT_MODEL_CALL_MS,
  });
}

/** @returns {Promise<ReviewOut>} */
export function getReview(reviewId) {
  return apiFetch(`/api/v1/reviews/${encodeURIComponent(reviewId)}`);
}

/** @returns {Promise<ReviewOut>} */
export function submitAnswers(reviewId, qaPairs) {
  return apiFetch(`/api/v1/reviews/${encodeURIComponent(reviewId)}/answers`, {
    method: "POST",
    body: { qa_pairs: qaPairs },
    timeoutMs: TIMEOUT_MODEL_CALL_MS,
  });
}

/**
 * Loads the one live operator resume's text (`GET /resume`, not `/api/v1` -
 * see backend/api.py). Increment 3.5 replaces this with stored, selectable
 * resumes; until then it is the only source of resume content for a live
 * review. Returns the resume's raw text; throws on any error response,
 * including the route's own 200-with-`{"error": ...}` shape.
 * @returns {Promise<string>}
 */
export async function loadLiveResume() {
  const token = await getAuthToken();
  const res = await fetch(apiUrl("/resume?command=load&demo=false"), {
    headers: token ? { Authorization: `Bearer ${token.idToken}` } : {},
  });
  if (!res.ok) {
    if (res.status === 401) await clearAuthToken();
    let message = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") message = body.detail;
    } catch {
      // fall through
    }
    throw apiError(message, res.status);
  }
  const body = await res.json();
  if (body?.error) throw apiError(body.error);
  return body.resume;
}
