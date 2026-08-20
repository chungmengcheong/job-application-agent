// The permanent canned demo's routes (`/review`, `/questions`, `/resume`,
// `/jobdescription`) - not `/api/v1`, and not part of what the shared fetch
// helper in api.js scopes. Kept separate because their response shapes
// (PascalCase `Fit`/`Gap_Map`/...) and error shape (`{"detail": ...}`) differ
// from the durable `ReviewOut`/safe-error-envelope contract.

const TIMEOUT_MODEL_CALL_MS = 150000;
const TIMEOUT_DEFAULT_MS = 30000;

async function demoFetch(path, { method = "GET", body, timeoutMs = TIMEOUT_DEFAULT_MS } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(path, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    if (!res.ok) {
      let message = `HTTP ${res.status}`;
      try {
        const errorBody = await res.json();
        if (typeof errorBody?.detail === "string") message = errorBody.detail;
      } catch {
        // fall through
      }
      const error = new Error(message);
      error.status = res.status;
      throw error;
    }
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

/** @returns {Promise<{Fit, Gap_Map, Questions}>} the canned Call 1 response (AnalysisResult) */
export function demoReview(jobDescription) {
  return demoFetch("/review", {
    method: "POST",
    body: { job_description: jobDescription, url: "", demo: true },
    timeoutMs: TIMEOUT_MODEL_CALL_MS,
  });
}

/** @returns {Promise<{Fit, Gap_Map, Tailored_Resume}>} the canned Call 2 response (ReviewResult) */
export function demoQuestions(qaPairs) {
  return demoFetch("/questions", {
    method: "POST",
    body: { qa_pairs: qaPairs, demo: true },
    timeoutMs: TIMEOUT_MODEL_CALL_MS,
  });
}

/** @returns {Promise<string>} the demo resume's text */
export async function demoResume() {
  const body = await demoFetch("/resume?command=load&demo=true");
  return body.resume;
}

/** @returns {Promise<string>} the demo job description text */
export async function demoJobDescription() {
  const body = await demoFetch("/jobdescription", {
    method: "POST",
    body: { url: "", demo: true },
  });
  return body.job_description;
}
