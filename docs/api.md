# AI Recruiting Agent — Backend API Notes

This document records the current API and the minimum replacement contract. It
does not define implementation order; see [backlog.md](backlog.md).

## Current API

### Authentication

Authenticated requests send a Google ID token as `Authorization: Bearer ...`.
The backend verifies signature, issuer, audience, and expiry, then applies the
configured email/domain allowlist. Authentication currently protects route
entry but does not partition the global workflow files by user.

### Current routes

| Route | Current purpose | Material issue |
|---|---|---|
| `POST /jobdescription` | Return the demo-seeded job description | URL extraction is not implemented |
| `POST /review` | Call 1: generate fit, gaps, and questions | No tailored resume yet by design |
| `POST /questions` | Call 2: regenerate fit/gaps and produce the tailored resume using answers | Uses the persisted job description, not a resubmission |
| `GET /resume` | Load/save/delete the single resume | Demo load can alter the shared baseline |
| `GET /oauth2cb` | Legacy Chrome OAuth bounce | Deprecated with the extension |

Live `/review` and `/questions` require authentication. Caller-controlled demo
flags select checked-in responses and bypass normal live generation.

### Current live dataflow

```text
GET /resume?command=load
    -> copy one user resume to temp/resume_baseline.txt

POST /review(job description)
    -> persist the submitted job description
    -> build the Call 1 prompt (resume + job description)
    -> provider returns fit + gaps + questions
    -> save the raw response for Call 2 to read

POST /questions(answers)
    -> write global answers
    -> reread the persisted job description
    -> build the Call 2 prompt (resume + job description + Call 1's fit/gaps + answers)
    -> provider returns revised fit + revised gaps + tailored resume
    -> generate deterministic redline
```

This design has no review ID or durable status. If a request times out, the
browser cannot reconcile the outcome.

### Current state ownership

| State | Current location | Scope |
|---|---|---|
| Stored resume | `user/resume.txt` | one operator by convention |
| Baseline resume | `temp/resume_baseline.txt` | entire backend process |
| Job description | `temp/job_description.txt` | entire backend process |
| Answers | `temp/user_response.json` | entire backend process |
| Current/prior responses | `temp/*.json` | entire backend process |
| Demo inputs/results | `demo/*` | checked-in fixtures |

## Increment 1 contract

Increment 1 preserves current route shapes and the current combined live
generation while correcting their behavior:

- preserve the submitted job description through follow-up;
- clean startup files independently;
- disable production debug behavior;
- validate the full provider result before replacing valid state;
- return stable safe errors; and
- make canned demo behavior read-only, fixture-based, and unable to touch live
  files.

Minimum response schemas cover fit, gaps, questions, tailored resume, and safe
errors only. Streaming, artifact versions, and future table shapes do not enter
these contracts.

## Increment 1.5 two-call contract — implemented

Groq becomes the only supported provider through one thin, config-driven
injectable client; see Configuration below. The two calls run on the existing
`POST /review` and `POST /questions` routes; Increment 1.5 did not introduce
new routes or a new request shape — that is `/api/v1`, below.

Field names stay today's PascalCase (`Fit`, `Gap_Map`, `Questions`,
`Tailored_Resume`) rather than the lowercase shape this section showed before
implementation. Explicit user decision (2026-08-18): renaming to snake_case now
and again at the `/api/v1` cutover was judged worse than renaming once, at that
boundary; see docs/backlog-done.md's Increment 1.5 entry.

### Call 1: analysis and questions — `POST /review`

Request (`JobListing`, unchanged from Increment 1):

```json
{
  "job_description": "...",
  "url": "https://example.com/job",
  "demo": false
}
```

The resume comes from the server-side working baseline, not the request body.

Validated output (`AnalysisResult`):

```json
{
  "Fit": {
    "score": 0,
    "rationale": "..."
  },
  "Gap_Map": [],
  "Questions": []
}
```

Call 1 does not return a tailored resume; `Tailored_Resume` is not a field on
this schema.

### Call 2: revised analysis and tailored resume — `POST /questions`

Request (`QuestionAnswers`, unchanged from Increment 1):

```json
{
  "qa_pairs": [
    {
      "question": "...",
      "answer": "..."
    }
  ],
  "demo": false
}
```

The server rebuilds the Call 2 prompt from the same resume baseline, the same
job description Call 1 persisted, Call 1's raw fit/gaps, and these answers.

Validated output (`ReviewResult`):

```json
{
  "Fit": {
    "score": 0,
    "rationale": "..."
  },
  "Gap_Map": [],
  "Tailored_Resume": "..."
}
```

Call 2 returns revised fit and gaps; `Questions` is not a field on this schema.
The server creates redline markup only after the complete tailored resume
validates.

The public browser contract uses ordinary JSON. Provider-side streaming, if
used internally, does not imply SSE. Browser-visible streaming and event
contracts are deferred.

## Durable `/api/v1` contract

After SQLite persistence is introduced, the supported authenticated API is:

```text
GET    /api/v1/me

GET    /api/v1/resumes
POST   /api/v1/resumes
GET    /api/v1/resumes/{resume_id}
PUT    /api/v1/resumes/{resume_id}
POST   /api/v1/resumes/{resume_id}/activate

POST   /api/v1/reviews
GET    /api/v1/reviews/{review_id}
POST   /api/v1/reviews/{review_id}/answers
```

### Create review

```json
{
  "resume_id": "res_...",
  "job_description": "...",
  "source_url": "https://example.com/job"
}
```

The server verifies that the resume belongs to the current user, stores an
immutable resume snapshot and job description, runs Call 1, and returns the
durable review in `awaiting_answers` or `failed` state.

### Submit answers

```json
{
  "qa_pairs": [
    {
      "question": "...",
      "answer": "..."
    }
  ]
}
```

The server retrieves the original resume snapshot and job description, runs
Call 2 with the submitted answers, validates the result, generates the redline,
and persists `completed` or `failed` state. No artifact version is required
initially.

### Review status

Use only:

```text
processing | awaiting_answers | completed | failed
```

If synchronous requests prove unreliable, `POST` may later return `202` with a
review ID and the client may poll `GET /api/v1/reviews/{review_id}`. SSE,
WebSockets, and sequenced events remain deferred.

### Error contract

Every `/api/v1` error uses one safe envelope:

```json
{
  "error": {
    "code": "MODEL_TIMEOUT",
    "message": "The review took too long. Please try again.",
    "request_id": "req_...",
    "retryable": true
  }
}
```

HTTP status communicates the failure class. Provider exceptions, prompts,
tokens, resumes, job descriptions, and answers never appear in client errors or
logs.

## Canned demo API

The canned demo remains fixture-based. It may use dedicated demo routes or a
clearly isolated equivalent, but it must:

- choose only server-owned fixtures;
- make no Groq call;
- create no account, session, or database record;
- never resolve through live-user storage; and
- return the same analysis and completed-result schemas used by the web client.

Demo session IDs, 24-hour retention, refresh recovery, and live user-provided
demo inputs are not part of the design.

## Authenticated one-time trial

The future trial uses the normal owned `/api/v1` resources. Resume and job
description may be collected in browser memory before login, but no persistence
or provider call occurs until authentication and explicit submit. On submit the
system creates or resolves the internal user, stores the resume, marks it active,
and creates an owned review.

## Ownership rules

- Derive the internal user from verified token claims.
- Never accept a client-selected `user_id`.
- Scope every resume and review operation by owner.
- Return the same not-found response for missing and other-user resources.
- Confirm an activated resume is owned by the current user.
- Store an immutable resume snapshot and job description on each review.
- Treat `source_url` as optional page context. The web app may omit or supply
  it; a future extension may populate it from the active page.

## Configuration

Current or planned environment configuration includes:

| Variable | Purpose |
|---|---|
| `LLM_API_KEY` | credential for the configured provider (currently Groq) |
| `LLM_BASE_URL` | OpenAI-compatible endpoint; defaults to Groq's |
| `LLM_MODEL` | explicit supported model |
| `LLM_REASONING_EFFORT` | reasoning budget for models that support it; support and accepted values vary by model |
| `LLM_MAX_COMPLETION_TOKENS` | completion token budget; must fit under the provider tier's rate limit alongside prompt size |
| `LANGSMITH_TRACING_V2` | must be `false` in production |
| `GOOGLE_WEB_CLIENT_ID` | Google ID-token audience |
| `ALLOWED_EMAILS` | invited email allowlist |
| `ALLOWED_DOMAINS` | invited domain allowlist |
| `HTTPS_PROXY` / `HTTP_PROXY` | production outbound proxy when required |

The LLM client (`backend/llm_client.py`) is a thin wrapper around the generic
`openai` SDK pointed at a configurable `base_url`, not a Groq-specific client.
Groq's chat completions API is OpenAI-schema-compatible, so switching provider,
model, or reasoning/token behavior is a config change, not a code change.
OpenAI API-key configuration (`OPENAI_API_KEY`) is unrelated to this and remains
obsolete leftover from before the Groq cutover; remove it once rollback no
longer requires it.

## Validation boundary

Static inspection establishes the current routes and file ownership defects. It
does not establish deployed OAuth, Groq, proxy, timeout, SQLite, or hosting
behavior. Those require explicit production checks.
