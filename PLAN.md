# AI Recruiting Agent — Refactoring Plan

This document records the project outcome, the small target architecture, and
the decisions that constrain implementation. Detailed sequencing and exit gates
live only in [docs/backlog.md](docs/backlog.md).

Supporting documentation:

- [docs/architecture.md](docs/architecture.md) — current and near-term architecture
- [docs/api.md](docs/api.md) — current and proposed backend contracts
- [docs/frontend.md](docs/frontend.md) — current web client and migration boundary
- [docs/backlog.md](docs/backlog.md) — ordered implementation increments

## Immediate outcome

Turn the current application into a reliable personal web app and a credible
portfolio project. The next possible horizon is a controlled beta for a handful
of invited users, but beta-only machinery should not shape the immediate
refactor unless it also improves current correctness, state ownership, or
testability.

Preserve the useful product core:

- compare a stored resume with a pasted job description;
- assess fit and gaps;
- ask targeted follow-up questions;
- use the answers to revise fit and gaps and produce a truthful tailored resume;
- generate deterministic redlines; and
- leave every proposed resume change under user control.

## Product boundaries

### Supported client

The web application is the only supported client during the current refactor.
Chrome extension development and releases are deferred and frozen:

- do not let Chrome APIs, OAuth, storage, packaging, or layout requirements
  shape the web refactor;
- stop treating the extension build as a release gate;
- retain the current extension code only until web-only code has been safely
  separated;
- then remove the obsolete implementation from the active tree while preserving
  a tagged Git reference and a concise architecture note; and
- rename `BrowserExtension/` to a web-oriented directory when that can be done
  as a contained change.

The extension remains a plausible future execution surface for browser-native
capabilities: extracting a job description from the active page, assisting with
user-approved application-form completion, and inspecting relevant networking
context. Reassess those jobs after the web workflow is reliable. A future
extension should be a thin, purpose-built client of the proven API rather than a
reason to preserve the current extension architecture.

### Canned demo

Keep the current public canned demo permanently:

- fixed synthetic resume and job description;
- fixed initial and follow-up responses;
- no LLM calls, authentication, account, or persistence;
- dedicated read-only demo paths that never touch live `user/` or `temp/`
  state; and
- fixtures validated against the same response schemas consumed by the web UI.

The canned demo is distinct from the future authenticated one-time trial.

### Authenticated one-time trial

After durable users and resumes exist, add an onboarding flow in which a visitor
may enter a resume and job description before authentication, but the system
makes no LLM call and persists no sensitive input until the visitor authenticates
and explicitly submits. The resulting account owns the stored resume and custom
review. This is Increment 2.5, not part of demo isolation.

## Target live workflow

Increment 1 preserves the current LLM workflow while making it correct and
safe. Increment 1.5 then changes the live workflow to two calls and makes Groq
the supported provider:

```text
Call 1
resume snapshot + job description
    -> fit
    -> gaps
    -> targeted questions

User answers questions

Call 2
same resume snapshot + same job description + answers
    -> revised fit
    -> revised gaps
    -> tailored resume

validated tailored resume
    -> deterministic server-side redline
```

Call 1 does not generate a premature tailored resume. Call 2 recalculates fit
and gaps from the original evidence plus the answers; it need not reproduce a
new question set.

Use ordinary JSON `POST` and `GET` contracts. Do not add SSE, WebSockets, event
sequencing, or browser-visible streaming now. The backend may later consume a
provider stream internally without exposing streaming to the browser. If
synchronous HTTP proves unreliable, the next simplest transport is
`POST -> 202 + review_id` followed by `GET` polling.

## Small target architecture

```text
Web application
  typed API client + explicit workflow state
                    |
                    v
FastAPI routes: authentication, validation, HTTP errors
                    |
                    v
              ReviewService
             /      |       \
            v       v        v
   SQLiteReviewStore  LLMClient  deterministic redline function
```

- Routes own HTTP concerns.
- `ReviewService` owns the two-call workflow and state transitions.
- One SQLite store module owns persistence. Do not add a repository hierarchy
  for a hypothetical second database.
- One thin injectable, config-driven LLM client owns provider syntax, timeouts,
  usage, and raw-response boundaries. The provider, model, and reasoning/token
  behavior come from configuration, not code, so switching them is a config
  change. This is not multi-provider machinery: there is one call path, not
  per-vendor branching logic, so still do not build a provider adapter
  framework.
- Keep deterministic redlining as a function unless it develops service-level
  dependencies.

## Initial durable model

Use three tables initially.

### `User`

```text
id
google_subject       unique verified Google `sub`
email                display and allowlist audit value
active_resume_id     nullable pointer to one owned stored resume
created_at
last_seen_at
```

### `Resume`

```text
id
user_id              owner
name
content
created_at
updated_at
```

A user may store multiple resumes and select exactly one as active. Updating a
stored resume never changes snapshots already attached to reviews.

### `Review`

```text
id
user_id              owner
resume_id            selected stored resume
resume_snapshot      immutable content used by both calls
job_description      immutable input used by both calls
source_url           optional page context for web or a future extension
answers_json
result_json           validated current analysis or completed result
status                processing | awaiting_answers | completed | failed
safe_error_code
created_at
updated_at
completed_at
```

Keep fit, gaps, questions, answers, and tailored output in validated JSON fields
until independent querying or lifecycle requirements justify separate tables.
Do not initially add artifact versions, answer versions, model-call tables,
retry histories, or finalized-resume versions.

## Minimal authenticated API

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

Every owned-resource operation derives the user from the verified token and
scopes the query by that internal user. No request accepts a caller-selected
`user_id`.

Use one stable safe error envelope. Do not retain a compatibility facade: add
the new API, switch the single supported web client in a coordinated increment,
and remove the old routes after the new flow is verified.

## Frontend boundary

The first decomposition should be only as large as the current problems require:

- typed API client;
- `ReviewWorkspace` with an explicit reducer or state model;
- resume management and active-resume selection;
- review/fit/gap/question presentation; and
- existing redline display and editing behavior.

Separate durable server state, workflow state, and ephemeral editing state.
Do not create Chrome/web platform interfaces or a predicted tree of feature
modules. Split components further when their behavior becomes independently
complex.

## Testing and safety rules

- Write the behavioral assertion before fixing each confirmed defect.
- Normal tests must block live provider calls unless a fake is explicitly
  injected.
- Validate complete model output before replacing the prior valid artifact.
- Keep every test's mutable filesystem or database isolated.
- Validate canned demo fixtures and mocked live responses through the same
  consumer schemas.
- Preserve strict known-defect tests until the fixing increment makes them pass.
- Run focused tests, the complete backend suite, frontend tests, typecheck, and
  the supported web build after each relevant increment.
- Production validation is required for Google OAuth, Groq, hosting, and SQLite
  persistence; mocks do not establish those boundaries.

Never log tokens, resumes, job descriptions, answers, raw prompts, or raw model
responses. Production tracing remains disabled until explicit content, access,
and retention controls exist.

## Explicit deferrals

Do not let these items shape Increment 1 or the minimum durable architecture:

- SSE or other browser-visible streaming;
- persisted demo sessions or demo continuity;
- a three-stage LLM workflow;
- multiple provider support;
- separate artifact and model-call tables;
- optimistic artifact or answer version checks;
- finalized-resume persistence and version checks;
- compatibility facades;
- Chrome extension implementation or shared platform adapters until the
  browser-native jobs are reassessed;
- advanced retry orchestration and operator failure inspection; and
- Postgres unless production SQLite validation fails.

## Implementation source of truth

[docs/backlog.md](docs/backlog.md) is the only source of truth for ordered
increments, release gates, and exit criteria. Architecture and contract
documents describe the current system and the next supported boundary; they do
not maintain duplicate phase plans.
