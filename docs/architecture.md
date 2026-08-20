# AI Recruiting Agent — Architecture and Design Notes

This document distinguishes the current implementation from the next supported
architecture. [../PLAN.md](../PLAN.md) records settled project decisions;
[backlog.md](backlog.md) owns implementation order.

## Product boundary

The immediate product is a reliable personal web application. It compares a
stored resume with a pasted job description, assesses fit and gaps, asks
targeted questions, produces a tailored resume from the added evidence, and
shows deterministic editable redlines.

A plain HTML/CSS/JS web client, with no build step, served by the same
FastAPI app as `/api/v1`, is the only supported client going forward during
the current refactor (Increment 3) — replacing the Next.js/React app that
used to share code with the Chrome extension. Chrome extension development
and releases are frozen because that Next.js app and the extension currently
share a React panel, but Chrome-specific interfaces and shells were never
part of the near-term target architecture, and the new web client doesn't
reuse any of that shared code. After the web client is separated, the
obsolete Next.js/extension implementation can leave the active tree while a
tagged Git reference and historical architecture note preserve it.

The extension remains a plausible future execution surface for capabilities
that genuinely benefit from running beside the page: extracting a job
description, assisting with user-approved form completion, and inspecting
networking context. Reassess these jobs after the web workflow is reliable. A
future extension should be a thin purpose-built client of the proven API, not a
continuation requirement for the current extension architecture.

The next possible product horizon is a controlled beta with invited users, not
an open public service.

## Current implementation

```text
Chrome extension (frozen)              Static web app
              \                         /
               +-- shared React panel -+
                            |
                     JSON over HTTPS
                            |
                  FastAPI / PythonAnywhere
              /api/v1: auth + validation + safe errors
                            |
                     ReviewService
                    /        |        \
                   v         v         v
          SQLite reviews  LLMClient  redline.py
           (data/reviews.db)          deterministic diff
```

The live workflow runs two Groq calls against a durable `Review` record, per
Increment 2: `POST /api/v1/reviews` creates the row and runs Call 1 (fit,
gaps, questions); `POST /api/v1/reviews/{review_id}/answers` runs Call 2
(revised fit, revised gaps, tailored resume) using the same resume/job
description captured at creation. Call 1 does not generate a tailored resume,
and Call 2 does not return another question set. The pre-Increment-2 routes
(`/review`, `/questions`, `/resume`, `/jobdescription`) remain, but now serve
only the permanent canned demo and a plain resume-text getter — no code path
in them reaches the model or the reviews store.

Important current constraints:

- `user/resume.txt` remains the one operator resume until Increment 3.5's
  stored resumes; the live client fetches its text via `GET /resume` and
  submits it inline to `POST /api/v1/reviews`.
- model output is used before complete schema validation.
- the canned demo uses checked-in fixtures, fully isolated from the live
  reviews store and from `user/resume.txt`.
- synchronous provider requests can occupy the browser for up to 150 seconds
  per call, twice per full review-and-tailor cycle.
- the frontend cutover (`BrowserExtension/lib/api.ts`) is intentionally ad
  hoc — it unwraps the `/api/v1` Review envelope back into the flat shape the
  panel already expected, rather than the shared fetch helper Increment 3
  adds in the new plain HTML/CSS/JS client.

## Canned demo boundary

The canned demo remains a permanent, deterministic product surface:

- server-owned synthetic resume and job description;
- checked-in initial and follow-up responses;
- no authentication, account, provider call, persistence, or session continuity;
- read-only paths isolated from authenticated state; and
- the same validated response shapes consumed by the live web UI.

The future authenticated one-time trial is a separate onboarding flow. A
visitor may enter a resume and job description before authentication, but no
provider call or persistence occurs until authentication and explicit submit.

## Live workflow

Increment 1.5 landed two Groq calls:

```text
active resume snapshot + job description
                  |
                  v
        Call 1: fit + gaps + questions
                  |
            user answers
                  |
                  v
Call 2: same snapshot + same job + answers
      -> revised fit + revised gaps + tailored resume
                  |
                  v
         deterministic redline
```

Call 1 deliberately does not generate a tailored resume. Call 2 recalculates fit
and gaps using the additional evidence and produces the tailored resume.

The browser contract remains ordinary JSON `POST` and `GET`. Provider-side
streaming does not require browser streaming. SSE, WebSockets, and event
sequencing are deferred. If synchronous HTTP becomes unreliable, use
`POST -> 202 + review_id` and `GET` polling before considering streaming.

## Small target architecture

```text
Web application
plain HTML/CSS/JS, no build step, served by the same FastAPI app
                  |
                  v
FastAPI routes
auth + validation + safe HTTP errors
                  |
                  v
            ReviewService
        /          |          \
       v           v           v
SQLiteReviewStore  LLMClient  redline function
```

Boundaries:

- routes own authentication dependencies, request validation, and HTTP errors;
- `ReviewService` owns workflow transitions and passes the same immutable inputs
  to both calls;
- one SQLite store module owns persistence and transactions;
- one thin injectable, config-driven LLM client owns provider syntax, model
  configuration, timeouts, usage, and raw-response handling. The provider
  (currently Groq, via its OpenAI-compatible endpoint), model, and
  reasoning/token behavior are configuration, not code; and
- deterministic redlining remains a function until it needs independent
  dependencies.

Do not add a repository hierarchy, multi-provider framework, separate redline
service, or compatibility facade without a demonstrated need.

As of Increment 2, the backend half of this diagram is implemented
(`backend/api_v1.py`'s FastAPI routes, `backend/review_service.py`'s
`ReviewService`, `backend/review_store.py`'s `ReviewStore`, the unchanged
`LLMClient`/`redline_diff`). The web application half is Increment 3: a
plain HTML/CSS/JS client (no framework, no build step) served from a new
`web/` directory by the same FastAPI app, replacing both the Next.js/React
app under `BrowserExtension/` and its ad hoc `lib/api.ts` `/api/v1`
envelope-unwrapping.

## LLM client configuration notes

Live-validated 2026-08-18 against Groq's OpenAI-compatible endpoint through
`backend/llm_client.py`. Two findings materially shape the configuration:

- **`reasoning_effort` accepted values are model-specific and do not
  overlap.** qwen3 models accept `none` or `default`; gpt-oss models accept
  `low`, `medium`, or `high`. Passing a value from the wrong set is a hard
  `400 BadRequestError`, not a fallback. Switching `LLM_MODEL` therefore also
  requires reviewing `LLM_REASONING_EFFORT` — this is a real coupling the
  config-driven design does not abstract away, and a two-entry lookup table
  isn't worth building for it.
- **Groq's per-minute rate limit (8,000 TPM on the current free/on-demand
  tier) is checked against `prompt_tokens + requested max_completion_tokens`
  at request-admission time, before generation runs** — not against tokens
  actually used. A large `LLM_MAX_COMPLETION_TOKENS` can get an otherwise-fine
  request rejected with `413` purely on the reservation, independent of the
  model or prompt content. Upgrading the Groq tier removes this ceiling.

These are two independent failure modes: a reasoning-capable model can also
burn its entire completion budget on a hidden reasoning trace and return
truncated, unparseable output (`finish_reason: "length"`) well *under* the TPM
cap — this is a generation-behavior problem, not a rate-limit problem, and is
why `reasoning_effort` must be set deliberately rather than left to a model's
default.

Token usage measured for the same demo-sized prompt (~4,300-char resume and
job description; `max_completion_tokens=4096` requested in every case),
representative but not exact — normal sampling variance moves actual
completion tokens by a few hundred between runs:

| Configuration | prompt tokens | completion tokens | reasoning tokens | total tokens | Result |
|---|---:|---:|---:|---:|---|
| `qwen/qwen3.6-27b`, `reasoning_effort=none` | 2,988 | 1,866 | not reported | 4,854 | Valid |
| `qwen/qwen3.6-27b`, `reasoning_effort=default` | — | — | — | — | `400`: Groq's `json_object` mode validator rejects the reasoning-prefixed output outright ("Failed to validate JSON") |
| `openai/gpt-oss-120b`, `reasoning_effort=low` | 2,872 | 1,518 | 141 | 4,390 | Valid |

Notes on the table:

- qwen3's usage response does not break out reasoning tokens separately the
  way gpt-oss's `completion_tokens_details.reasoning_tokens` does; with
  `reasoning_effort=none` there is no reasoning trace to report regardless.
- `qwen3.6-27b` + `default` reasoning is not just slower or more
  token-hungry — combined with `response_format={"type": "json_object"}` it
  fails the request outright, because the hidden `<think>` trace violates
  strict JSON-object output. This is a stronger, cleaner failure than the
  earlier truncation case (no `response_format` and no `max_completion_tokens`
  set at all), which instead silently burned a small default budget on
  reasoning and returned truncated, unparseable content
  (`finish_reason: "length"`, 2,048 completion tokens, zero valid output).
- Current configuration (`LLM_MODEL=qwen/qwen3.6-27b`,
  `LLM_REASONING_EFFORT=none`, `LLM_MAX_COMPLETION_TOKENS=4096`) reserves
  2,988 + 4,096 = 7,084 tokens against the 8,000 TPM cap for this prompt size;
  actual usage lands well under both the cap and the reservation.

## Durable domain model

The domain model grows in two stages, matching the backlog: Increment 2
introduces only `Review`; Increment 3.5 adds `User` and `Resume` underneath it.

### Review (Increment 2) — implemented

`backend/review_store.py`'s `reviews` table (`backend/db.py`), matching this
exactly:

- ID;
- owner — the verified Google `sub`, a plain string match, not yet a foreign
  key to a `users` table;
- submitted resume content, stored immutably and inline (no `resume_id` yet);
- immutable job description;
- optional source URL for page context;
- answers JSON;
- validated current result JSON;
- `processing | awaiting_answers | completed | failed`;
- safe error code; and
- timestamps.

Keep fit, gaps, questions, answers, and tailored output in validated JSON fields
initially. Separate artifact tables, model-call tables, retry histories, and
optimistic versions are deferred.

### User and Resume (Increment 3.5)

`User`:

- stable internal ID;
- unique verified Google `sub`;
- email for display and allowlist audit;
- pointer to one active owned resume; and
- timestamps.

`Resume`:

- ID and owner;
- name and content; and
- timestamps.

A user may store multiple resumes and select one as active. Existing review
snapshots do not change when a stored resume is updated. Increment 3.5 also
migrates `Review` rows created back in Increment 2: it resolves or creates the
`User` row for each recorded `sub`, and adds a nullable `resume_id` column to
`Review`.

## Identity and ownership

Increment 2 scopes every review by the verified `sub` string directly; there
is no durable `users` table yet, so this is a string match, not a foreign-key
lookup.

Once Increment 3.5 lands, one FastAPI dependency verifies the Google ID token,
enforces the invited-user policy, resolves the internal user from the verified
`sub`, and returns a typed current user. Routes never accept a caller-selected
`user_id`.

Every live resume and review query includes owner scope. Missing and
other-user resources return the same not-found response. Canned demo paths do
not resolve through the live store.

## Deployment assumptions

| Concern | Current state | Required validation |
|---|---|---|
| Backend | FastAPI on PythonAnywhere | deployed personal workflow |
| Web | static Next.js export (Increment 3: plain HTML/CSS/JS, same-origin on PythonAnywhere, no Vercel) | callback, responsive workflow |
| Extension | frozen shared-code legacy | no longer a current release gate; reassess browser-native jobs after the web workflow is proven |
| Provider | Groq migration in working tree | model, proxy, timeouts, safe errors |
| Persistence | SQLite `reviews` table (`data/reviews.db`) | production durability, backup, locking |
| Tracing | LangSmith development integration | production disabled |

Use SQLite first. Move to managed Postgres only if production filesystem,
locking, backup, deployment persistence, or overlapping-write validation fails
materially.

## Open validation questions

- Which Groq model is the supported quality and latency baseline?
- Does synchronous request handling complete reliably on the production path,
  or is durable polling required?
- Does SQLite meet the production host's persistence and contention needs?
- Which deletion and retention controls are required before invited beta use?

## Validation boundary

Current-system statements derive from static code, fixtures, tests, and build
configuration. They do not prove deployed Google OAuth, Groq, PythonAnywhere,
or SQLite behavior. Those boundaries require explicit production validation.
