import assert from "node:assert/strict"
import { afterEach, beforeEach, test } from "node:test"

import {
  cleanMarkdown,
  clearAuthToken,
  getAuthToken,
  postQuestions,
  postReview,
  saveAuthToken,
} from "../lib/api.ts"


class MemoryStorage {
  private values = new Map<string, string>()

  getItem(key: string): string | null {
    return this.values.get(key) ?? null
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value)
  }

  removeItem(key: string): void {
    this.values.delete(key)
  }

  clear(): void {
    this.values.clear()
  }
}


const originalFetch = globalThis.fetch
const originalWindow = (globalThis as any).window
const originalLocalStorage = (globalThis as any).localStorage


beforeEach(() => {
  const storage = new MemoryStorage()
  ;(globalThis as any).window = {}
  ;(globalThis as any).localStorage = storage
})


afterEach(() => {
  globalThis.fetch = originalFetch
  ;(globalThis as any).window = originalWindow
  ;(globalThis as any).localStorage = originalLocalStorage
})


test("stores and retrieves an unexpired web auth token", async () => {
  const token = {
    accessToken: "access-token",
    idToken: "id-token",
    expiresAt: Date.now() + 60_000,
  }

  await saveAuthToken(token)

  assert.deepEqual(await getAuthToken(), token)
})


test("does not return an expired web auth token", async () => {
  await saveAuthToken({
    accessToken: "expired-access-token",
    idToken: "expired-id-token",
    expiresAt: Date.now() - 1,
  })

  assert.equal(await getAuthToken(), null)
})


test("clearAuthToken removes the stored web token", async () => {
  await saveAuthToken({
    accessToken: "access-token",
    idToken: "id-token",
    expiresAt: Date.now() + 60_000,
  })

  await clearAuthToken()

  assert.equal(await getAuthToken(), null)
})


test("postReview (live) posts the resume inline to /api/v1/reviews and unwraps the Review envelope", async () => {
  await saveAuthToken({
    accessToken: "access-token",
    idToken: "id-token",
    expiresAt: Date.now() + 60_000,
  })
  let capturedUrl = ""
  let capturedInit: RequestInit | undefined
  globalThis.fetch = async (url, init) => {
    capturedUrl = String(url)
    capturedInit = init
    return new Response(
      JSON.stringify({
        id: "rev_123",
        status: "awaiting_answers",
        result: { Fit: { score: 8, rationale: "Strong fit." }, Gap_Map: [], Questions: ["Q?"] },
        safe_error_code: null,
      }),
      { status: 201, headers: { "Content-Type": "application/json" } },
    )
  }

  const result = await postReview({
    jobDescription: "Target job",
    url: "https://example.com/job",
    demo: false,
    resume: "My resume text",
  })

  assert.equal(
    capturedUrl,
    "https://airecruitingagent.pythonanywhere.com/api/v1/reviews",
  )
  assert.deepEqual(JSON.parse(String(capturedInit?.body)), {
    resume: "My resume text",
    job_description: "Target job",
    source_url: "https://example.com/job",
  })
  const headers = new Headers(capturedInit?.headers)
  assert.equal(headers.get("Authorization"), "Bearer id-token")
  assert.equal(headers.get("Content-Type"), "application/json")
  assert.deepEqual(result, {
    Fit: { score: 8, rationale: "Strong fit." },
    Gap_Map: [],
    Questions: ["Q?"],
    reviewId: "rev_123",
  })
})


test("postReview (demo) still posts to /review with the demo flag", async () => {
  let capturedUrl = ""
  let capturedInit: RequestInit | undefined
  globalThis.fetch = async (url, init) => {
    capturedUrl = String(url)
    capturedInit = init
    return new Response(
      JSON.stringify({ Fit: { score: 7, rationale: "Demo." }, Gap_Map: [], Questions: [] }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    )
  }

  await postReview({
    jobDescription: "Target job",
    url: "https://example.com/job",
    demo: true,
  })

  assert.equal(capturedUrl, "https://airecruitingagent.pythonanywhere.com/review")
  assert.deepEqual(JSON.parse(String(capturedInit?.body)), {
    job_description: "Target job",
    url: "https://example.com/job",
    demo: true,
  })
})


test("postQuestions (live) posts answers to /api/v1/reviews/{reviewId}/answers", async () => {
  let capturedUrl = ""
  let capturedBody: unknown
  globalThis.fetch = async (url, init) => {
    capturedUrl = String(url)
    capturedBody = JSON.parse(String(init?.body))
    return new Response(
      JSON.stringify({
        id: "rev_123",
        status: "completed",
        result: { Fit: { score: 8, rationale: "Updated fit." }, Gap_Map: [], Tailored_Resume: "Resume" },
        safe_error_code: null,
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    )
  }

  const result = await postQuestions({
    qa_pairs: [
      { question: "Answered?", answer: "Yes." },
      { question: "Skipped?", answer: "" },
    ],
    demo: false,
    reviewId: "rev_123",
  })

  assert.equal(
    capturedUrl,
    "https://airecruitingagent.pythonanywhere.com/api/v1/reviews/rev_123/answers",
  )
  assert.deepEqual(capturedBody, {
    qa_pairs: [
      { question: "Answered?", answer: "Yes." },
      { question: "Skipped?", answer: "" },
    ],
  })
  assert.equal(result.reviewId, "rev_123")
})


test("postQuestions (live) rejects without a reviewId", async () => {
  await assert.rejects(
    postQuestions({ qa_pairs: [], demo: false }),
    /Missing review id/,
  )
})


test("postQuestions (demo) still posts to /questions with the demo flag", async () => {
  let capturedUrl = ""
  let capturedBody: unknown
  globalThis.fetch = async (url, init) => {
    capturedUrl = String(url)
    capturedBody = JSON.parse(String(init?.body))
    return new Response(
      JSON.stringify({ Fit: { score: 8, rationale: "Updated fit." }, Gap_Map: [], Tailored_Resume: "Resume" }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    )
  }

  await postQuestions({
    qa_pairs: [{ question: "Answered?", answer: "Yes." }],
    demo: true,
  })

  assert.equal(capturedUrl, "https://airecruitingagent.pythonanywhere.com/questions")
  assert.deepEqual(capturedBody, {
    qa_pairs: [{ question: "Answered?", answer: "Yes." }],
    demo: true,
  })
})


test("a 401 clears the stored token and surfaces the server detail", async () => {
  await saveAuthToken({
    accessToken: "access-token",
    idToken: "id-token",
    expiresAt: Date.now() + 60_000,
  })
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ detail: "Authentication required." }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    })

  await assert.rejects(
    postReview({
      jobDescription: "Target job",
      url: "https://example.com/job",
    }),
    /Authentication required/,
  )
  assert.equal(await getAuthToken(), null)
})


test("cleanMarkdown accepts backend additions and deletions", () => {
  const redline =
    'Led <span style="color:#c00000"><del>small</del></span>' +
    '<span style="color:#008000"><add>large</add></span> teams.'

  assert.equal(cleanMarkdown(redline), "Led large teams.")
})


test("cleanMarkdown preserves ordinary resume text and line breaks", () => {
  const resume = "## EXPERIENCE\n**Leader**\nImproved revenue by 20%."

  assert.equal(cleanMarkdown(resume), resume)
})
