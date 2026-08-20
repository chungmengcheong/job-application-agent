// Pure-logic tests for web/js/api.js: the auth header, safe-error-envelope
// parsing, and the /api/v1 request shapes. Run via
// `node --test web/tests/*.test.mjs` - see docs/frontend.md.
import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";

class MemoryStorage {
  #values = new Map();
  getItem(key) {
    return this.#values.has(key) ? this.#values.get(key) : null;
  }
  setItem(key, value) {
    this.#values.set(key, String(value));
  }
  removeItem(key) {
    this.#values.delete(key);
  }
  clear() {
    this.#values.clear();
  }
}

const originalFetch = globalThis.fetch;
const originalLocalStorage = globalThis.localStorage;

beforeEach(() => {
  globalThis.localStorage = new MemoryStorage();
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  globalThis.localStorage = originalLocalStorage;
});

const { saveAuthToken, getAuthToken } = await import("../js/auth.js");
const { createReview, getReview, submitAnswers, loadLiveResume } = await import("../js/api.js");

test("createReview posts the resume inline to /api/v1/reviews with the auth header", async () => {
  await saveAuthToken({ accessToken: "access-token", idToken: "id-token", expiresAt: Date.now() + 60_000 });

  let capturedUrl;
  let capturedInit;
  globalThis.fetch = async (url, init) => {
    capturedUrl = url;
    capturedInit = init;
    return new Response(
      JSON.stringify({
        id: "rev_123",
        status: "awaiting_answers",
        result: { Fit: { score: 8, rationale: "Strong fit." }, Gap_Map: [], Questions: ["Q?"] },
        safe_error_code: null,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
        completed_at: null,
      }),
      { status: 201, headers: { "Content-Type": "application/json" } },
    );
  };

  const result = await createReview({
    resume: "My resume text",
    jobDescription: "Target job",
    sourceUrl: "https://example.com/job",
  });

  assert.equal(capturedUrl, "/api/v1/reviews");
  assert.deepEqual(JSON.parse(capturedInit.body), {
    resume: "My resume text",
    job_description: "Target job",
    source_url: "https://example.com/job",
  });
  assert.equal(capturedInit.headers.Authorization, "Bearer id-token");
  assert.equal(result.id, "rev_123");
  assert.deepEqual(result.result.Questions, ["Q?"]);
});

test("getReview fetches the durable review by id", async () => {
  let capturedUrl;
  globalThis.fetch = async (url) => {
    capturedUrl = url;
    return new Response(
      JSON.stringify({
        id: "rev_1",
        status: "completed",
        result: { Tailored_Resume: "Resume" },
        safe_error_code: null,
        created_at: "",
        updated_at: "",
        completed_at: "",
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  };

  const result = await getReview("rev_1");

  assert.equal(capturedUrl, "/api/v1/reviews/rev_1");
  assert.equal(result.status, "completed");
});

test("submitAnswers posts qa_pairs to the review's answers route", async () => {
  let capturedUrl;
  let capturedBody;
  globalThis.fetch = async (url, init) => {
    capturedUrl = url;
    capturedBody = JSON.parse(init.body);
    return new Response(
      JSON.stringify({
        id: "rev_1",
        status: "completed",
        result: { Tailored_Resume: "Resume" },
        safe_error_code: null,
        created_at: "",
        updated_at: "",
        completed_at: "",
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  };

  const result = await submitAnswers("rev_1", [{ question: "Q?", answer: "A." }]);

  assert.equal(capturedUrl, "/api/v1/reviews/rev_1/answers");
  assert.deepEqual(capturedBody, { qa_pairs: [{ question: "Q?", answer: "A." }] });
  assert.equal(result.result.Tailored_Resume, "Resume");
});

test("a 401 clears the stored token and surfaces the safe-envelope message", async () => {
  await saveAuthToken({ accessToken: "access-token", idToken: "id-token", expiresAt: Date.now() + 60_000 });
  globalThis.fetch = async () =>
    new Response(
      JSON.stringify({
        error: { code: "UNAUTHENTICATED", message: "Authentication required.", request_id: "req_1", retryable: false },
      }),
      { status: 401, headers: { "Content-Type": "application/json" } },
    );

  await assert.rejects(getReview("rev_1"), /Authentication required/);
  assert.equal(await getAuthToken(), null);
});

test("loadLiveResume returns resume text for an authenticated request", async () => {
  await saveAuthToken({ accessToken: "access-token", idToken: "id-token", expiresAt: Date.now() + 60_000 });
  let capturedUrl;
  let capturedHeaders;
  globalThis.fetch = async (url, init) => {
    capturedUrl = url;
    capturedHeaders = init.headers;
    return new Response(JSON.stringify({ resume: "LIVE RESUME" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  const resume = await loadLiveResume();

  assert.equal(capturedUrl, "/resume?command=load&demo=false");
  assert.equal(capturedHeaders.Authorization, "Bearer id-token");
  assert.equal(resume, "LIVE RESUME");
});

test("loadLiveResume throws on the legacy route's 200-with-error body", async () => {
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ error: "Authentication required to load resume." }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });

  await assert.rejects(loadLiveResume(), /Authentication required to load resume\./);
});
