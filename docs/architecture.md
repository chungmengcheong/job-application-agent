# AI Recruiting Agent — Architecture

This is the current-system architecture. [../backlog.md](../backlog.md) owns
the cross-cutting constraints, implementation order, and exit gates;
[api.md](api.md) and [frontend.md](frontend.md) contain the detailed
contracts.

## Product and client boundary

The supported product is a personal web application that compares a resume
with a job description, assesses fit and gaps, asks targeted follow-up
questions, produces a truthful tailored resume, and presents deterministic
editable redlines.

The only supported client is the plain HTML/CSS/JS application under `web/`.
FastAPI serves it at `/app/` from the same origin as `/api/v1`; there is no
frontend framework, build step, Node runtime, Vercel deployment, or CORS
boundary for the supported product.

The former Next.js/React web app and Chrome extension were frozen at Git tag
`chrome-extension-last-working`. They were replaced rather than refactored:
the supported client imports no code or assets from that implementation. The
legacy tree was therefore deleted without renaming it. A future extension,
if browser-native jobs justify one, should be a new thin client of `/api/v1`.

The public canned demo remains a separate deterministic surface: checked-in
synthetic inputs and responses, no authentication, model call, persistence, or
access to live resume/review state.

## Current implementation

```text
Browser
  web/ (plain HTML/CSS/JS)
          |
          | same-origin JSON over HTTPS
          v
FastAPI (backend/api.py)
  /app/               static web client
  /api/v1/*            authenticated durable workflow
  legacy demo routes   canned demo + temporary operator-resume getter
          |
          v
ReviewService (backend/review_service.py)
     /                    |                     \
    v                     v                      v
ReviewStore         LLMClient               redline_diff
(SQLite)            (Groq-compatible API)   (deterministic function)
```

Responsibilities are deliberately small:

- FastAPI routes own authentication, request validation, and safe HTTP errors.
- `ReviewService` owns the two-call workflow and valid status transitions.
- `ReviewStore` owns SQLite persistence using short-lived connections.
- `LLMClient` owns provider syntax, timeouts, usage metadata, and raw response
  boundaries. Model and reasoning/token settings come from configuration.
- Redlining stays a deterministic function.

Do not add a repository hierarchy, multi-provider framework, separate redline
service, browser-visible streaming, or compatibility facade without a
demonstrated need.

## Live workflow and state

```text
resume snapshot + job description
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

`POST /api/v1/reviews` durably creates a review before Call 1.
`POST /api/v1/reviews/{review_id}/answers` runs Call 2 from the immutable inputs
stored on that review. `GET /api/v1/reviews/{review_id}` restores a review after
a lost response or browser refresh. Requests are synchronous today; if that is
unreliable in production, prefer `202 + review_id` with polling before adding
SSE or WebSockets.

The current `reviews` table stores:

- `id` and verified Google `sub` as `owner`;
- immutable inline `resume_content`, `job_description`, and optional
  `source_url`;
- answers and the current validated result as JSON;
- `processing | awaiting_answers | completed | failed` status;
- a safe error code and timestamps.

The browser derives its presentation from the review's server status. It keeps
only loading/error/auth flags and unsent or editing state locally. Live review
URLs use `/app/reviews/{review_id}` and rehydrate from `/api/v1`.

## Authentication and ownership

The browser currently obtains a Google ID token through a hand-built implicit
flow, stores it in `localStorage`, and sends it as `Authorization: Bearer ...`.
The backend verifies the token and applies the configured email/domain
allowlist. Every current review read and write is scoped by the verified `sub`;
missing and other-owner resources return the same not-found response. Increment
4 replaces or explicitly justifies the hand-built flow and fixes the current
fail-open handling of a missing `email_verified` claim.

The current one-operator resume remains `user/resume.txt`, exposed to the live
client through the authenticated legacy `GET /resume`. The next personal-use
increment starts with a fresh database, seeds one `ccmmail@gmail.com` user,
ports that file into a stored resume, changes review creation from inline
resume content to an owned `resume_id`, and keeps the inline snapshot on each
review immutable. Historical `users` and `reviews` are not imported.

The seed does not invent a Google identity claim. On the first verified login
for the allowlisted email, the stable Google `sub` is attached to the seeded
user; subsequent ownership uses that `sub`, not the email string.

## LLM configuration constraints

The supported provider path is Groq's OpenAI-compatible API. Configuration is
centralized in `backend/config.py`; there is one call path, not a provider
adapter framework.

Live checks on 2026-08-18 established two material couplings:

- `reasoning_effort` values are model-specific. The current
  `qwen/qwen3.6-27b` configuration requires `none` for the strict JSON response
  path; incompatible values fail rather than degrade gracefully.
- Groq admits a request against prompt tokens plus requested maximum completion
  tokens. The current `4096` completion limit must be considered alongside the
  account's token-per-minute limit when model or prompt size changes.

These are deployment configuration constraints, not reasons to add provider
abstraction.

## Deployment boundary

| Concern | Current implementation | Still requires live validation |
|---|---|---|
| Application | One FastAPI app on PythonAnywhere | deploy/reload/rollback path |
| Web client | Same-origin static files under `web/` | responsive workflow and callback registration |
| Authentication | Google browser token, backend verification and allowlist | state, nonce, expiry, logout, and unauthorized paths |
| Provider | Groq through `LLMClient` | model quality, proxy, timeouts, safe errors, usage |
| Persistence | SQLite `users`, `resumes`, and `reviews` tables in `data/reviews.db` | durability, backup/restore, locking, overlapping writes |
| Tracing | LangSmith enabled for development | confirm disabled in production |

Static code and tests do not prove those production boundaries. SQLite remains
the intended store unless live persistence or contention tests fail materially.

## Near-term changes

The next increment adds durable users and the first stored resume for the
personal app from a fresh database. Authenticated one-time-trial onboarding is
a separate beta increment after the personal production boundary has been
validated. Active-resume selection and resume history remain deferred until
multiple stored resumes are needed.

Before invited beta use, every store operation must be owner-scoped; two-user
authorization/concurrency, retention/deletion, backup/restore, and deployment
rollback must be tested.
