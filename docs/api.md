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
| `POST /review` | Generate fit, gaps, questions, and tailored resume | Does not save the submitted job description |
| `POST /questions` | Regenerate the review using answers | Rereads the global demo-seeded job description |
| `GET /resume` | Load/save/delete the single resume | Demo load can alter the shared baseline |
| `GET /oauth2cb` | Legacy Chrome OAuth bounce | Deprecated with the extension |

Live `/review` and `/questions` require authentication. Caller-controlled demo
flags select checked-in responses and bypass normal live generation.

### Current live dataflow

```text
GET /resume?command=load
    -> copy one user resume to temp/resume_baseline.txt

POST /review(job description)
    -> build one combined prompt
    -> provider returns fit + gaps + questions + tailored resume
    -> rotate global response files
    -> generate deterministic redline

POST /questions(answers)
    -> write global answers
    -> reread temp/job_description.txt
    -> repeat the combined review call
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

## Increment 1.5 two-call contract

Groq becomes the only supported provider through one thin injectable client.

### Call 1: analysis and questions

Input:

```json
{
  "resume": "...",
  "job_description": "..."
}
```

Validated output:

```json
{
  "fit": {
    "score": 0,
    "rationale": "..."
  },
  "gaps": [],
  "questions": []
}
```

Call 1 does not return a tailored resume.

### Call 2: revised analysis and tailored resume

Input:

```json
{
  "resume": "same resume used in Call 1",
  "job_description": "same job description used in Call 1",
  "qa_pairs": [
    {
      "question": "...",
      "answer": "..."
    }
  ]
}
```

Validated output:

```json
{
  "fit": {
    "score": 0,
    "rationale": "..."
  },
  "gaps": [],
  "tailored_resume": "..."
}
```

Call 2 returns revised fit and gaps. It need not return another question set.
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
| `GROQ_API_KEY` | supported provider after Increment 1.5 |
| `GROQ_MODEL` | explicit supported model |
| `LANGSMITH_TRACING_V2` | must be `false` in production |
| `GOOGLE_WEB_CLIENT_ID` | Google ID-token audience |
| `ALLOWED_EMAILS` | invited email allowlist |
| `ALLOWED_DOMAINS` | invited domain allowlist |
| `HTTPS_PROXY` / `HTTP_PROXY` | production outbound proxy when required |

OpenAI configuration becomes obsolete after the Groq cutover and should be
removed once rollback no longer requires it.

## Validation boundary

Static inspection establishes the current routes and file ownership defects. It
does not establish deployed OAuth, Groq, proxy, timeout, SQLite, or hosting
behavior. Those require explicit production checks.
