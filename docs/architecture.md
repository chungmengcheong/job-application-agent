# AI Recruiting Agent — Architecture and Design Notes

This document distinguishes the current implementation from the next supported
architecture. [../PLAN.md](../PLAN.md) records settled project decisions;
[backlog.md](backlog.md) owns implementation order.

## Product boundary

The immediate product is a reliable personal web application. It compares a
stored resume with a pasted job description, assesses fit and gaps, asks
targeted questions, produces a tailored resume from the added evidence, and
shows deterministic editable redlines.

The statically exported Next.js web app is the only supported client going
forward during the current refactor. Chrome extension development and releases
are frozen because the web and extension currently share a React panel, but
Chrome-specific interfaces and shells are not part of the near-term target
architecture. After the web client is separated, the obsolete extension
implementation can leave the active tree while a tagged Git reference and
historical architecture note preserve it.

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
                 auth + route orchestration
                    |        |        |
                    v        v        v
             global files  provider  redline.py
             user/ temp/    client    deterministic diff
```

The current live workflow asks one provider call to return fit, gaps, questions,
and a complete tailored resume. After the user answers questions, the backend
repeats that combined generation.

Important current constraints:

- `user/` and `temp/` contain one process-global workflow state.
- `/review` uses the submitted job description but does not persist it;
  `/questions` rereads the demo-seeded global job description.
- startup cleanup can leave stale later files when an earlier file is missing.
- model output is used before complete schema validation.
- the canned demo uses checked-in fixtures but some demo paths can mutate the
  same working files as live mode.
- synchronous provider requests can occupy the browser for up to 150 seconds.
- the current working tree contains a Groq migration while the committed
  baseline and some error text still refer to OpenAI.

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

## Target live workflow

Increment 1.5 introduces two Groq calls:

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
typed API client + explicit workflow state
                  |
                  v
FastAPI routes
auth + validation + safe HTTP errors
                  |
                  v
            ReviewService
        /          |          \
       v           v           v
SQLiteReviewStore  GroqClient  redline function
```

Boundaries:

- routes own authentication dependencies, request validation, and HTTP errors;
- `ReviewService` owns workflow transitions and passes the same immutable inputs
  to both calls;
- one SQLite store module owns persistence and transactions;
- one thin injectable Groq client owns provider syntax, model configuration,
  timeouts, usage, and raw-response handling; and
- deterministic redlining remains a function until it needs independent
  dependencies.

Do not add a repository hierarchy, multi-provider framework, separate redline
service, or compatibility facade without a demonstrated need.

## Durable domain model

### User

- stable internal ID;
- unique verified Google `sub`;
- email for display and allowlist audit;
- pointer to one active owned resume; and
- timestamps.

### Resume

- ID and owner;
- name and content; and
- timestamps.

A user may store multiple resumes and select one as active. Existing review
snapshots do not change when a stored resume is updated.

### Review

- ID and owner;
- selected resume ID and immutable resume snapshot;
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

## Identity and ownership

One FastAPI dependency verifies the Google ID token, enforces the invited-user
policy, resolves the internal user from the verified `sub`, and returns a typed
current user. Routes never accept a caller-selected `user_id`.

Every live resume and review query includes owner scope. Missing and
other-user resources return the same not-found response. Canned demo paths do
not resolve through the live store.

## Deployment assumptions

| Concern | Current state | Required validation |
|---|---|---|
| Backend | FastAPI on PythonAnywhere | deployed personal workflow |
| Web | static Next.js export | callback, CORS, responsive workflow |
| Extension | frozen shared-code legacy | no longer a current release gate; reassess browser-native jobs after the web workflow is proven |
| Provider | Groq migration in working tree | model, proxy, timeouts, safe errors |
| Persistence | global server files | SQLite durability, backup, locking |
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
