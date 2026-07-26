# AI Recruiting Agent — Architecture and Design Notes

This is a living record of the system as it exists and the decisions that
shape the next increment. It is intentionally lightweight: update it when an
architectural boundary or product decision changes rather than trying to
catalog every implementation detail.

## Current product boundary

The product compares one stored resume with a pasted job description, asks an
LLM for a fit assessment, gap analysis, follow-up questions, and tailored
resume, then presents the tailored resume as an editable redline.

There are two user interfaces over the same React panel:

- a Manifest V3 Chrome extension side panel, packaged from a static Next.js
  export; and
- a statically exported Next.js web app, intended to run on Vercel.

The FastAPI backend runs on PythonAnywhere. Google supplies identity; an
environment-configured email/domain allowlist supplies authorization. The
current production boundary is a personal app. The next target is a controlled
beta with a handful of explicitly invited users, not an open public service.

Detailed component notes:

- [api.md](api.md) — backend endpoints, contracts, dataflow, and state
- [frontend.md](frontend.md) — shared panel, extension shell, web shell, and
  browser-owned state
- [authentication and authorization flow.md](authentication%20and%20authorization%20flow.md)
  — historical authentication notes; useful context, but the code and the two
  component documents are the current source of truth
- [backlog.md](backlog.md) — confirmed issues and validation risks

## Working architecture hypothesis

This diagram describes the current implementation, not the desired refactor.

```text
                         Google OAuth 2.0
                               ^
                               |
                  ID token + access token in browser
                               |
        +----------------------+----------------------+
        |                                             |
Chrome extension                              Static web app
Manifest V3                                   Next.js export / Vercel
side panel + Chrome APIs                      browser APIs only
        |                                             |
        +------------- shared React panel ------------+
                              |
                    BrowserExtension/lib/api.ts
                    auth header, timeout, API URL
                              |
                              | HTTPS / JSON
                              v
                 FastAPI app on PythonAnywhere
                 backend/api.py + security.py
                    |                    |
                    |                    +--> Google token verification
                    |                         + email/domain allowlist
                    |
                    +--> prompt template + file-backed workflow state
                    |    user/, temp/, demo/, prompts/
                    |
                    +--> Groq chat-completions-compatible API
                    |    model: qwen/qwen3.6-27b
                    |
                    +--> redline.py
                         baseline vs tailored resume diff
```

The core live workflow is:

```text
load stored resume
    |
    v
paste job description --> POST /review --> one LLM call
                                               |
                                               v
                         fit + gaps + questions + tailored resume
                                               |
                                               v
                                  server creates redline markup
                                               |
                                               v
                                  panel renders review and resume
                                               |
                              optional answers to follow-up questions
                                               |
                                               v
                                      POST /questions
                                               |
                                               v
                                  repeat the review LLM call
```

## Important current constraints

- The backend has one global set of `user/` and `temp/` files. Identity is
  checked at endpoint entry, but state is not partitioned by identity, browser
  session, or review. Concurrent users or overlapping requests can read or
  overwrite one another's workflow state.
- Server startup always seeds the working resume and job description from demo
  files. A real resume is copied into the same working baseline only when an
  authenticated client calls `GET /resume?command=load`.
- The first `/review` request uses the job description in its request body,
  but does not save it. `/questions` later reads the server's global
  `temp/job_description.txt`, which remains the demo description under the
  current implementation.
- Demo mode is not a self-contained client fixture. It calls public backend
  endpoints, and some demo endpoints mutate the same global files used by live
  mode.
- The web and extension experiences share most UI and API code, but their
  identity flows, page-URL behavior, token stores, builds, and deployment
  contexts differ.
- The API performs long synchronous LLM calls inside synchronous FastAPI
  handlers. The browser waits up to 150 seconds for review requests.

## Deployment topology

| Concern | Current implementation | Confidence |
|---|---|---|
| Backend | FastAPI/uvicorn ASGI app on `airecruitingagent.pythonanywhere.com` | Documented in README and code |
| Marketing page | `static/index.html`, served by FastAPI at `/` | Confirmed in code |
| Web panel | Static Next.js export; Vercel origin is allowed by backend CORS | Build configuration confirmed; live behavior not verified in this review |
| Extension | Static Next.js export repackaged into `dist-extension/` with Manifest V3 files | Confirmed in build script; installed build not verified in this review |
| LLM | Groq SDK using `qwen/qwen3.6-27b` in the current working tree | Confirmed in uncommitted code; differs from `main`, which uses OpenAI |
| Optional LLM tracing | Disabled; the application does not initialize an external tracing client or decorate LLM calls | Confirmed in code |
| Durable user state | Repository/server files under `user/` | Confirmed in code; deployment persistence/backup not verified |
| Workflow state | Shared files under `temp/` | Confirmed in code |

## Key decisions made

This table records decisions embodied in the current system and decisions made
for the next documentation/refactor phase. “Current” does not imply “keep.”

| Area | Decision | Rationale / implication |
|---|---|---|
| Product | Optimize first for personal production use, then a handful of invited beta users | Avoids prematurely designing for a public multi-tenant product, while still requiring isolation, privacy, and operational reliability. |
| Documentation | Keep one system map plus separate backend and frontend contracts | The shared panel hides meaningful runtime differences; separate notes keep those boundaries visible. |
| Primary client | One React panel supports extension and web | Reuses the product flow, but requires explicit adapters for browser capabilities and authentication. |
| Frontend packaging | Statically export Next.js; repackage the export for Chrome | One buildable UI can serve both surfaces, at the cost of a custom and currently brittle extension build step. |
| Authentication | Google OAuth implicit/hybrid response returns an ID token and access token to the browser | Works with the current backend token verification, but should be reassessed before beta against current OAuth guidance and web threat boundaries. |
| Extension OAuth | Use a PythonAnywhere `/oauth2cb` bounce to the extension's `chromiumapp.org` callback | Workaround for the extension/client binding problem documented by the original implementation. |
| Authorization | Allowlist email addresses and domains through environment variables | Appropriate product gate for a small invited beta if configuration and failure behavior are tested. |
| Resume storage | Store one resume as a server-side text file | Simple for one user; incompatible with concurrent beta use without per-user ownership. |
| Workflow state | Store current/prior responses and follow-up answers as global files | Made the original flow inspectable, but creates correctness and privacy hazards as soon as requests overlap. |
| Review generation | Ask one LLM call to return fit, gaps, questions, and a complete tailored resume as strict JSON | Keeps orchestration simple; creates a large prompt/output and a brittle all-or-nothing response contract. |
| Redlining | Generate deterministic token-level markup on the server | Separates content generation from diff generation and lets the UI accept/reject changes. |
| Demo | Use checked-in job, resume, and response fixtures | Good fixture source; routing demo through mutable production workflow state is not a decision to retain. |
| Observability | Disable optional prompt/response tracing; retain only application-owned, non-content model-call metadata and add structured operational logging | Resume and job content should not be copied into a second observability system. |
| Refactor approach | Characterize behavior locally, refactor in vertical increments, then validate the supported web/streaming stack in production before optimizing LLM calls | Avoids testing obsolete production paths while keeping deployment uncertainty ahead of paid-workflow optimization. |

## Desired boundary for the next increment

The first structural refactor should make one review an explicit unit of work
for the personal web workflow. Ownership remains part of the data model from
the start, but two-user isolation is proved only after the personal workflow,
local streaming, production boundary, and LLM efficiency are working. A
practical limited-beta shape is:

```text
Client-specific adapter (web or extension)
                  |
                  v
          typed API client
                  |
                  v
FastAPI routes --> review service --> LLM adapter
       |               |                |
       |               |                +-- model request/response validation
       |               |
       |               +-- deterministic redline service
       |
       +--> user/review repository (isolated state)
       +--> structured request and error logging
```

This is a working hypothesis, not yet an implementation commitment. The
smallest useful vertical increment is an isolated, schema-validated demo review
that does not touch live state. Durable single-user state and the web client
follow before streaming and production validation.

## Open questions

- What deletion controls should users receive while development-period
  persistence remains in effect?
- Is PythonAnywhere still the intended host after state isolation and
  observability requirements are clear?
- Which Groq model should become the supported baseline for each LLM stage?

## Validation boundary

This document was derived from repository code, fixtures, build configuration,
tests, README history, and the existing authentication note on 2026-07-25.
Static inspection confirms the architecture and the identified state
ownership. It does not confirm that the deployed web app, installed extension,
Google OAuth configuration, PythonAnywhere filesystem, or Groq call currently
works end to end. Streaming will be built and tested locally before its
production hosting path is validated.
