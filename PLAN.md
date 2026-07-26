# AI Recruiting Agent — Refactoring Plan

This is a living implementation plan. It translates the current-system
documentation into a sequence of small, runnable, observable increments. It
should change as assumptions are validated; it is not a commitment to every
future feature.

Supporting context:

- [docs/architecture.md](docs/architecture.md) — current system and working
  target architecture
- [docs/api.md](docs/api.md) — current backend contracts and state ownership
- [docs/frontend.md](docs/frontend.md) — current web/extension behavior
- [docs/backlog.md](docs/backlog.md) — evidence-labeled P0–P3 backlog

## Outcome

Refactor the personal production app into a reliable foundation for a
controlled beta with a handful of users:

1. demo and live mode exercise the same application workflow without sharing
   mutable state;
2. every resume and review is explicitly owned by one authenticated user;
3. backend and frontend use small, explicit state models rather than implicit
   files and interacting booleans; and
4. the review loop sends less repeated context and streams useful progress and
   output to the user.

The refactor should preserve the product's useful core: job-fit assessment,
gap analysis, follow-up questions, truthful resume tailoring, deterministic
redlines, and user control over proposed changes.

## Success criteria

### Personal production use

- A review and its follow-up use the same submitted job description and resume.
- Public demo activity cannot read or alter live resume/review state.
- The supported web workflow passes a production-like smoke test.
- Invalid model output fails safely without corrupting the prior review.
- Sensitive content is not emitted through application logs or error responses.
- The supported LLM provider, authentication flow, and tracing policy are
  explicitly configured and validated.

### Limited beta

- Two authorized users can run overlapping reviews without state leakage or
  corruption.
- Each user can manage their own active resume.
- Each review has a durable identifier, ownership, status, and inspectable
  failure state.
- Refreshing the browser restores the active review.
- Demo and live responses conform to one versioned schema.
- Structured logs connect a client request, review, model call, and failure
  without containing resume or job-description text.

### LLM and streaming

- The first useful review information appears before the complete tailored
  resume is ready.
- A disconnected client can reload the durable review rather than forcing a
  second paid model call.
- Follow-up turns do not resend unnecessary prior model prose or unrelated
  resume content.
- Token counts, latency, model, provider, and outcome are recorded per model
  call.
- A malformed or interrupted stream cannot leave a review marked complete.

## Non-goals for this refactor

- General-public signup, billing, teams, or enterprise tenancy
- Automated job-page scraping
- A background job platform before synchronous-plus-streaming execution proves
  insufficient
- Semantic/vector search over resumes before prompt measurements justify it
- Supporting many LLM providers simultaneously
- Rebuilding the visual design
- Automatically accepting or saving LLM resume edits without user action

## Guiding design decisions

| Area | Decision | Rationale |
|---|---|---|
| Unit of work | Make `Review` the durable aggregate | It binds user, resume snapshot, job description, questions, answers, model calls, status, and output. |
| Identity boundary | Derive ownership from verified token claims, never request fields | Prevents one caller from selecting another user's state. |
| Persistence | Use a repository abstraction backed initially by SQLite | Appropriate for a small beta, supports transactions and concurrent users, and leaves a path to managed Postgres. |
| Resume input | Snapshot the selected resume into each review | Follow-ups remain reproducible even if the user later replaces their resume. |
| Demo | Seed an isolated demo review through the same service/schema | Removes special response paths and contract drift while keeping demo deterministic. |
| API shape | Use conventional JSON commands plus server-sent events for review progress | SSE fits one-way model output, works over normal HTTP, and is simpler than WebSockets for this workflow. |
| Streaming durability | Persist validated stage results before emitting completion events | Browser disconnection must not determine whether work is saved. |
| LLM boundary | One provider adapter, typed inputs/outputs, and recorded usage | Keeps provider churn out of domain logic and makes optimization measurable. |
| LLM workflow | Separate structured analysis from resume generation | The user can see fit/gaps/questions earlier; follow-up turns can update only affected artifacts. |
| Redline | Keep deterministic diffing outside the LLM | Avoids spending tokens on markup and preserves inspectable behavior. |
| Frontend state | Separate server state, workflow state, and local edit state | Avoids one large component coordinating auth, fetching, workflow, and redline editing through booleans. |
| Migration | Build vertical slices behind current behavior; avoid a big-bang rewrite | Each increment can be tested and deployed independently. |
| Primary beta client | Web application | Stabilize one complete user experience before returning to the extension. |
| Extension timing | Defer extension refactoring to a post-beta P2 increment | The extension should consume the proven shared product core rather than shape the first beta architecture. |
| Initial database | SQLite | Appropriate for the expected beta scale; validate production filesystem, backup, and concurrent-write assumptions. |
| Resume versions | Support multiple resumes per user | Users need durable versions and must explicitly select the resume used for each review. |
| Demo retention | Persist synthetic demo sessions for 24 hours | Supports refresh and stream reconnection without retaining demo activity as durable product history. |
| LLM provider | Groq through its OpenAI-compatible interface | Preserve an OpenAI-shaped adapter while choosing Groq as the supported provider. |
| Development retention | Persist resumes, job descriptions, answers, reviews, and model-call metadata during development | Supports debugging and product learning; deletion controls and a beta retention policy remain required before broader use. |
| Optional traces | Do not retain optional prompt/response traces | Avoid duplicating sensitive resume and job-description content outside application-owned state. |

SQLite is the selected first-beta database, not a permanent infrastructure
decision. Validate PythonAnywhere locking, backup, filesystem persistence, and
overlapping-write behavior before the multi-user release gate. If those
assumptions fail, move the same repository contract to managed Postgres.

## Target architecture

```text
Web shell                         Chrome extension shell
OAuth + browser adapter           OAuth + Chrome adapter
        |                                  |
        +---------- shared product UI -----+
                           |
                    typed API client
                    + SSE event client
                           |
                           v
                  FastAPI route layer
                  auth + validation
                           |
                           v
                     ReviewService
             +-------------+-------------+
             |             |             |
             v             v             v
      ReviewRepository  LLMAdapter   RedlineService
      users/resumes/    typed stages  deterministic
      reviews/events    usage data    diff
             |
             v
        SQLite initially
        Postgres if needed
```

The route layer owns HTTP concerns. `ReviewService` owns workflow transitions.
Repositories own persistence. The LLM adapter owns provider syntax, streaming,
timeouts, usage metadata, and raw-response boundaries. None of those concerns
should live in React components or route functions.

## Core domain model

The exact schema may evolve, but ownership and lifecycle should not be implicit.

### `User`

```text
id                  internal stable ID
google_subject      unique verified `sub` claim
email               normalized display/allowlist audit value
created_at
last_seen_at
```

Use Google's stable `sub` claim as the external identity key. Email can change
and should not be the primary key.

### `Resume`

```text
id
user_id             owner
name
content
content_hash
created_at
updated_at
archived_at
```

Start with one active resume per user in the product UI, while avoiding a
database constraint that prevents later versioning.

### `Review`

```text
id
user_id             owner; nullable only for isolated public demo records
resume_id           source resume
resume_snapshot     immutable content used for this review
job_description
source_url
mode                 live | demo
status               created | analyzing | awaiting_answers |
                     tailoring | completed | failed
schema_version
error_code           safe classified error
created_at
updated_at
completed_at
```

### Review artifacts

Store typed artifacts rather than treating one raw model response as all state:

```text
ReviewAnalysis
    review_id
    version
    fit_score
    fit_rationale
    positioning
    gap_map_json
    questions_json

ReviewAnswers
    review_id
    version
    qa_pairs_json

TailoredResume
    review_id
    version
    content
    redline
```

For a small beta these can be JSON columns or fields on a small number of
tables. Do not prematurely normalize every gap row or question unless querying
them becomes a product requirement.

### `ModelCall`

```text
id
review_id
stage                analysis | follow_up_analysis | tailoring
provider
model
prompt_version
status               started | completed | failed
input_tokens
output_tokens
latency_ms
error_code
created_at
completed_at
```

Do not store full raw prompts/responses by default. If temporarily retained for
development, make that an explicit environment policy with redaction and
retention.

## Backend state model

`ReviewService` is the only component allowed to move a review between states.

```text
created
   |
   v
analyzing ---------------------------> failed
   |
   +--> questions exist --> awaiting_answers
   |                            |
   |                            v
   |                     analyzing follow-up
   |                            |
   +----------------------------+
   |
   v
tailoring ---------------------------> failed
   |
   v
completed
```

Rules:

- Transitions are persisted transactionally.
- `failed` retains the last completed artifact and a safe error code.
- A retry creates a new model-call attempt; it does not erase prior successful
  artifacts.
- Only the owning user can read, update, retry, answer, or delete a live review.
- Demo review identifiers must not resolve through live-user repository paths.
- Completion requires a validated analysis, tailored resume, and deterministic
  redline.
- Model text is never itself the workflow status.

## Frontend state model

Use three deliberately separate kinds of state.

### Server state

Fetched and cached by review/resume ID:

- current user/session
- active resume metadata/content
- review record and status
- analysis, questions, and tailored resume
- model/progress events

Refreshing the page refetches this state from the backend.

### Workflow state

Represent the page as a discriminated state rather than interacting booleans:

```text
booting
demo_ready
signed_out
resume_required
ready
submitting
streaming_analysis
awaiting_answers
streaming_tailoring
completed
error
```

Authentication and authorization are session facts, not inferred from whether
resume content happened to load.

### Local UI state

Keep only ephemeral presentation/editing state locally:

- active tab
- unsent job description
- unsent follow-up answers
- redline visibility
- locally accepted/rejected/edited changes
- copy feedback and tooltip visibility

Do not persist bearer tokens, review content, and developer backend selection
through the same generic storage helper.

## Frontend refactoring plan

The frontend is not one deployment with a few conditionals. It is a shared
product experience hosted by two platforms:

```text
                         Shared product core
             review workflow, screens, redline editor
                        /                 \
                       /                   \
              Web application         Chrome extension
              web auth adapter        Chrome identity adapter
              browser storage         chrome.storage adapter
              responsive shell        side-panel shell
              explicit source URL     active-tab adapter
```

The shared core should know what capability it needs, not which browser API
provides it.

### Proposed module boundaries

```text
BrowserExtension/
    app/                         Next.js web routes and web shell
    extension/                   Manifest, service worker, side-panel entry
    features/
        auth/                    Session UI and platform-neutral auth contract
        resumes/                 Resume list, editor, and selection
        reviews/                 Review workflow and server-state hooks
        redline/                 Redline display and edit model
        demo/                    Demo entry and fixture presentation
    platforms/
        web/                     OAuth redirect, local browser integration
        chrome/                  Chrome identity, storage, active-tab integration
    api/                         Typed JSON and SSE client
    components/                  Reusable presentation components
```

The exact folders can follow the existing Next.js conventions. The important
boundary is that `extension-panel.tsx` no longer owns platform detection,
authentication, API calls, workflow transitions, and the entire product UI.

### Shared product core

Extract the current panel into independently testable product areas:

- `JobDescriptionStep`
- `ReviewSummary`
- `GapMap`
- `FollowUpQuestions`
- `TailoredResume`
- `RedlineEditor`
- `ReviewWorkspace`

`ReviewWorkspace` coordinates a review ID and explicit workflow state. Leaf
components receive typed data and callbacks; they do not call browser APIs or
construct backend URLs.

### Platform contracts

Use narrow interfaces:

```ts
interface AuthAdapter {
  getSession(): Promise<Session | null>
  login(): Promise<void>
  logout(): Promise<void>
}

interface PageContextAdapter {
  getSourceUrl(): Promise<string | null>
}

interface ClientStorage {
  get<T>(key: string): Promise<T | null>
  set<T>(key: string, value: T): Promise<void>
  remove(key: string): Promise<void>
}
```

- The web adapter owns the OAuth callback and web-safe token/session storage.
- The Chrome adapter owns `chrome.identity`, `chrome.storage`, and active-tab
  access.
- Product code receives adapters at the shell boundary and contains no
  `window.chrome` checks.
- The backend base URL is deployment configuration. A local/cloud toggle may
  exist only in a development build.

The current browser-held ID-token design can remain during the first vertical
slice to limit scope. Its long-term web storage/session design is gated by the
P0 authentication validation rather than silently standardized during UI
refactoring.

### Web shell

The web app should become a deliberate full-page application:

- responsive layout rather than a fixed extension-width panel over a landing
  page;
- direct routes for resume management and `reviews/{review_id}`;
- explicit paste/input behavior rather than pretending the web app can inspect
  another tab;
- callback and signed-out pages that preserve the intended destination;
- accessible loading, failure, and reconnect states; and
- no Chrome-specific controls or close-panel behavior.

The FastAPI marketing page and Vercel application currently compete as web
entry points. Choose one canonical product URL and make other entry points
redirect or link to it.

### Chrome extension shell

Retain one supported Manifest V3 path:

- extension action opens the Chrome side panel;
- side panel mounts the shared product core through the Chrome adapters;
- active-tab URL is optional context, not a substitute for job-description
  extraction;
- remove the iframe/content-script panel path unless a separately scoped
  on-page feature needs it; and
- generate `dist-extension/` from source rather than treating generated HTML
  or bundles as parallel source files.

Do not add page scraping during this refactor. If job-description extraction is
later required, give it a separate permission and data-flow review.

### Review and redline persistence

Server review artifacts are durable. Redline hover/selection state remains
local. The user must take an explicit action to create a finalized artifact:

```text
POST /api/v1/reviews/{review_id}/final-resume
```

The request sends the accepted/rejected/edited plain resume plus the source
tailored-resume version. The server validates ownership and version, then
stores it as a new review artifact. Copy/download can remain available without
saving.

This addresses reload loss without silently treating every hover or edit as a
server mutation.

### Frontend build system

Before declaring either runtime supported:

- choose one package manager and lockfile;
- replace `latest` dependency ranges with intentional versions;
- remove unused Node/browser shims and duplicate entry paths;
- add non-interactive `lint` and `typecheck` commands;
- stop suppressing TypeScript and lint failures during builds;
- keep web and extension builds as separate named commands over shared source;
- add contract/unit tests before moving component boundaries; and
- document generated artifacts and whether they are committed or release-only.

The web build is the beta release gate. Extension modernization and its build
gate are deferred to a post-beta P2 increment.

## Proposed API

Keep the current endpoints during migration, then retire them after the new
vertical flow is proven.

### Session and resumes

```text
GET    /api/v1/me
GET    /api/v1/resumes
POST   /api/v1/resumes
GET    /api/v1/resumes/{resume_id}
PUT    /api/v1/resumes/{resume_id}
DELETE /api/v1/resumes/{resume_id}
```

For the first increment, `POST`/`PUT` may accept plain text only. File parsing
is a separate future feature.

### Reviews

```text
POST /api/v1/reviews
GET  /api/v1/reviews/{review_id}
POST /api/v1/reviews/{review_id}/answers
POST /api/v1/reviews/{review_id}/retry
POST /api/v1/reviews/{review_id}/final-resume
GET  /api/v1/reviews/{review_id}/events
```

Create review:

```json
{
  "resume_id": "res_...",
  "job_description": "...",
  "source_url": "https://example.com/job"
}
```

Response:

```json
{
  "review_id": "rev_...",
  "status": "created",
  "events_url": "/api/v1/reviews/rev_.../events"
}
```

Submit answers:

```json
{
  "analysis_version": 1,
  "qa_pairs": [
    {
      "question_id": "q_1",
      "answer": "..."
    }
  ]
}
```

The version prevents answers generated for an old question set from silently
updating a newer analysis.

### API error contract

Every `/api/v1` error should use a stable envelope:

```json
{
  "error": {
    "code": "MODEL_TIMEOUT",
    "message": "The review took too long. Please retry.",
    "request_id": "req_...",
    "retryable": true
  }
}
```

- HTTP status communicates the transport/category failure.
- `code` drives client behavior and is safe to log.
- `message` is user-facing and contains no provider exception or sensitive
  input.
- Field validation errors retain structured field locations.
- Demo and live APIs use the same error envelope.
- The frontend switches on typed codes, not searches for `"401"` or `"403"` in
  error strings.

### Streaming event contract

Use Server-Sent Events (SSE), an HTTP response that remains open so the server
can send a sequence of one-way updates to the browser. Unlike WebSockets, SSE
does not create a two-way messaging channel; the browser uses ordinary JSON
requests to start/retry work and SSE only to receive progress.

Use `text/event-stream` with typed, versioned events:

```text
event: review.status
data: {"review_id":"rev_...","status":"analyzing","sequence":1}

event: analysis.completed
data: {"review_id":"rev_...","analysis_version":1,"analysis":{...},"sequence":2}

event: tailoring.delta
data: {"review_id":"rev_...","text":"partial text","sequence":3}

event: review.completed
data: {"review_id":"rev_...","tailored_resume_version":1,"sequence":4}

event: review.failed
data: {"review_id":"rev_...","code":"MODEL_TIMEOUT","retryable":true,"sequence":5}
```

Important boundary:

- Status and completed artifacts are durable server state.
- `tailoring.delta` is transient display data and need not be saved token by
  token.
- On reconnect or refresh, the client first fetches the review record, then
  resumes events after the last sequence if supported.
- The final resume is published only after the complete streamed text passes
  schema/content validation and is saved.
- Never stream raw provider exceptions, prompts, tokens, or internal traces.

SSE is the initial hypothesis. Validate that the selected PythonAnywhere/Vercel
path does not buffer or terminate the stream before making it the supported
transport. If it cannot reliably stream, retain the same durable review model
and use short polling; do not redesign the domain around the transport.

## Less brittle demo design

The demo should be a first-class adapter around the real service contract, not
branches scattered across endpoints.

### Proposed behavior

- Keep checked-in, synthetic `DemoScenario` fixtures:
  - resume
  - job description
  - analysis result
  - follow-up answers/result
  - tailored resume
- Validate every fixture against the same Pydantic schemas used for live model
  output.
- Create demo reviews as isolated SQLite records addressed by an unguessable
  demo-session ID.
- Expire and delete demo reviews automatically after 24 hours.
- Run deterministic redline generation through the same `RedlineService`.
- Emit the same event types as live mode, optionally with short simulated
  delays for the streaming UX.
- Never copy demo content into a live user's resume or review tables.
- Never select demo behavior from a caller-controlled `demo: true` field on a
  live mutation endpoint.

### Preferred public contract

```text
POST /api/v1/demo/reviews
GET  /api/v1/demo/reviews/{demo_review_id}
POST /api/v1/demo/reviews/{demo_review_id}/answers
GET  /api/v1/demo/reviews/{demo_review_id}/events
```

The demo route chooses the fixture scenario server-side. Live routes ignore
demo flags entirely.

### Demo contract test

Run the same consumer assertions against demo and mocked-live responses:

- required fields and allowed enum values;
- analysis and question versions;
- state transition ordering;
- final tailored resume and redline format; and
- frontend rendering.

## Multi-user design

### Request identity

One FastAPI dependency should:

1. verify the Google ID token;
2. enforce the invited email/domain policy;
3. resolve or create the internal user from the verified `sub`; and
4. return a typed `CurrentUser`.

Routes pass `CurrentUser.id` to services. They never accept `user_id` from the
client for owned resources.

### Repository rules

- Every resume/review query includes owner scope.
- A missing resource and another user's resource produce the same not-found
  response.
- Database foreign keys and unique constraints enforce ownership invariants.
- Updates use transactions and, where needed, version checks.
- Filesystem paths are not constructed from email addresses or client input.
- Tests run two-user interleavings, not only sequential happy paths.

### Limited-beta storage decision

Use SQLite for the first beta and validate all of the following:

- one durable production filesystem;
- one effective writer process or acceptable write contention;
- reliable backup/restore;
- deployment does not replace the database file; and
- overlapping review writes pass a stress test.

If a validation fails materially, use managed Postgres before beta. The
repository interface should make this a deployment decision rather than a
service rewrite.

## LLM workflow and token efficiency

Do not optimize only by choosing a smaller model. First stop resending and
regenerating information the system already has.

### Stage 1: structured analysis

Input:

- job description;
- resume snapshot;
- optional additional candidate information; and
- compact prompt instructions.

Output:

- fit score and rationale;
- positioning;
- gap map with stable gap IDs; and
- follow-up questions with stable question IDs.

Persist the validated result and show it immediately.

### Stage 2: follow-up update

Input:

- compact job requirements extracted in stage 1;
- relevant resume evidence or resume snapshot if measurement shows it is still
  necessary;
- prior gap records by stable ID; and
- new question-answer pairs.

Output:

- only updated fit/positioning/gap/question artifacts, preferably as a complete
  replacement structured object rather than prose describing a patch.

Do not include a previously generated tailored resume unless the user is
explicitly revising that artifact.

### Stage 3: tailored resume

Input:

- immutable resume snapshot;
- compact positioning and gap-handling decisions;
- verified follow-up evidence; and
- formatting/truthfulness constraints.

Output:

- plain tailored resume only.

Stream this stage for perceived latency. Generate redlines locally on the
server after completion; never ask the model to produce diff markup.

### Measurement before deeper optimization

Record per stage:

- prompt version;
- input/output tokens;
- time to first event;
- total latency;
- validation/repair attempts;
- user retry rate; and
- whether follow-up answers changed the final result.

Then evaluate:

- removing duplicated instructions or prior prose;
- deriving a compact job-requirements representation once;
- sending only gap-relevant resume sections during follow-up;
- model choice by stage; and
- caching immutable prompt prefixes if the selected provider supports it.

Avoid lossy resume summarization until evals show it preserves decision-critical
evidence. Token savings are not worthwhile if they cause fabricated or omitted
experience.

## Implementation sequence

Each phase ends with a deployable or locally demonstrable vertical result.

### Phase 0 — Validate the production boundary

Goal: distinguish code defects from external configuration problems.

- Inspect one existing LangSmith trace to understand current exposure, then
  disable optional prompt/response tracing for the refactored workflow.
- Validate Google web OAuth callback, state, nonce, expiry, logout, and
  allowlist paths.
- Run the current deployed web workflow end to end.
- Verify the current LLM/provider from the production host.
- Treat web as the primary beta surface; record extension behavior only to
  avoid accidental regression before its later refactor.

Exit gate:

- Each validation-risk P0 backlog item is converted to validated behavior,
  configuration work, or a reproducible defect.

### Phase 1 — Fix personal-use correctness and isolate demo

Goal: make the existing personal workflow trustworthy before restructuring it.

- Preserve the submitted job description through follow-up.
- Fix startup cleanup or remove reliance on startup-global workflow files.
- Disable production debug behavior and sanitize errors.
- Move public demo to isolated routes/fixtures.
- Add Pydantic models for demo and live review output.
- Validate fixtures and deterministic redlines through the same contracts.

Exit gate:

- A live review/follow-up uses the correct inputs.
- Repeated and concurrent demo calls cannot change live state.
- Malformed model output leaves prior state intact.

### Phase 2 — Introduce the review domain slice

Goal: replace implicit current-run files with one explicit, durable review.

- Add database configuration and migrations.
- Add `User`, `Resume`, `Review`, artifact, and `ModelCall` persistence.
- Implement repository interfaces and `CurrentUser`.
- Implement `ReviewService` state transitions.
- Add `/api/v1/me`, resume, create-review, and get-review endpoints.
- Initially call the current single LLM prompt behind the new adapter to limit
  simultaneous change.
- Keep old endpoints as a compatibility facade if needed.

Exit gate:

- One user can create, refresh, and retrieve a durable review through the new
  API with no `temp/` dependency.

### Phase 3 — Prove multi-user isolation

Goal: make the domain slice safe for a handful of invited users.

- Scope every repository operation by owner.
- Add per-user resume create/update/archive behavior.
- Add two-user authorization and overlapping-request tests.
- Add optimistic version checks for answers/retries.
- Validate SQLite concurrency/backup assumptions or move to Postgres.

Exit gate:

- Two users can run overlapping review and follow-up workflows with no
  cross-user reads, writes, or state corruption.

### Phase 4 — Simplify the frontend around the new API

Goal: make the web application deliberate and restoreable, then retain Chrome
as a thin platform shell if it remains a supported surface.

- Split `extension-panel.tsx` into the product components and platform
  boundaries defined in the frontend refactoring plan.
- Implement web and Chrome adapters for auth, storage, source URL, and shell.
- Add a typed API client for `/api/v1`.
- Add typed handling for the common API error envelope.
- Replace interacting workflow booleans with explicit workflow states.
- Treat fetched review/resume data as server state.
- Route review pages by durable review ID.
- Implement a responsive full-page web shell with no Chrome-only controls.
- Keep redline editing local until the user explicitly saves a final resume.
- Implement finalized-resume save plus copy/download behavior.
- Remove or development-gate the backend selector.
- Choose one package manager; restore non-interactive lint and typecheck.
- Stop suppressing lint/type errors during the supported web build.
- Freeze the Chrome extension as a non-beta surface and document its last known
  build; do not let Chrome-specific constraints shape the web refactor.

Exit gate:

- The web app can reload mid-review or after completion and recover from the
  server without mixing demo/live/auth state.
- The supported build passes typecheck, lint, contract tests, and a browser
  smoke test.
- Chrome-only code is confined to the Chrome platform and extension shell.

### Phase 5 — Split and stream the LLM workflow

Goal: improve time-to-value and reduce repeated tokens without weakening
output quality.

- Establish baseline token/latency/quality measurements for the current prompt.
- Implement typed structured-analysis output.
- Persist and emit analysis completion before tailoring.
- Implement the tailored-resume stage as a streamed provider call.
- Add SSE review events with sequence numbers and safe errors.
- Configure explicit provider connect/read/total timeouts.
- Retry only pre-stream or otherwise idempotent failures; never replay an
  ambiguous partial generation automatically.
- Map provider failures into the common API error contract.
- Add disconnect/reload and interrupted-stream tests.
- Implement compact follow-up inputs and compare quality/token use to baseline.
- Run deterministic redline only after final resume validation.

Exit gate:

- The UI receives useful analysis before tailoring completes.
- Reload/disconnect does not duplicate a completed call.
- Token and latency measurements show improvement without material quality loss
  on the evaluation set.

### Phase 6 — Remove compatibility paths and harden beta operations

Goal: leave one supported architecture.

- Remove global workflow files and old endpoints after migration.
- Quarantine obsolete extension iframe/manual-panel paths without undertaking
  the full extension refactor.
- Add structured request, review, and model-call logging.
- Add readiness checks and operator-facing failure inspection.
- Enforce retention/deletion and tracing policies.
- Remove unused frontend/backend dependencies and stale configuration.
- Make backend tests, schema tests, frontend typecheck/lint/build, and web smoke
  tests a release gate.
- Update architecture, API, frontend, backlog, and operating docs in the same
  change that retires a compatibility path.
- Document backup, restore, deploy, and rollback.

Exit gate:

- The supported web/beta workflow deploys through a repeatable release gate and
  has a tested rollback/recovery path.

### Phase 7 — Refactor the Chrome extension after beta

Goal: make the extension a thin P2 shell over the proven shared product core.

- Reassess whether the extension remains worth supporting after web-beta
  learning.
- Retain one Manifest V3 side-panel entry.
- Implement Chrome auth, storage, and active-tab adapters.
- Mount the shared review/resume product core without web-shell assumptions.
- Remove the iframe/content-script panel and parallel generated/source paths.
- Add extension typecheck, build, contract, and manual side-panel smoke gates.

Exit gate:

- The extension consumes the same `/api/v1` contracts and shared product
  components without adding Chrome conditionals to product code.

## Testing strategy

### Backend

- Domain transition unit tests
- Repository ownership and transaction tests
- Route auth/authz and response-schema tests
- Fixture contract tests shared by demo and mocked live mode
- Model-adapter tests with chunked, malformed, interrupted, and timeout streams
- Two-user concurrency tests

### Frontend

- Reducer/state-machine transition tests
- Typed API/event parser tests
- Demo/live contract rendering tests
- Redline accept/reject/edit tests
- Web OAuth callback failure-path tests
- Reload/reconnect behavior with a durable review

### End to end

Minimum production-like scenarios:

1. public demo, including follow-up;
2. authorized live user, first review;
3. authorized live user, follow-up update;
4. refresh during and after review;
5. invalid/expired token;
6. allowlisted vs non-allowlisted user;
7. provider timeout/malformed output;
8. two overlapping users; and
9. streamed connection interruption and recovery.

## Observability

Use structured events with:

- request ID;
- internal user ID or non-reversible safe identifier;
- review ID;
- route/stage;
- status and safe error code;
- duration;
- model/provider/prompt version; and
- token usage.

Never log:

- bearer/access/ID tokens;
- resume or job-description content;
- question answers;
- raw prompts/responses; or
- provider exceptions that may contain request content.

LangSmith is not automatically the production logging system. Its use depends
on the deferred trace-content, access, retention, and redaction decision.

## Migration and rollback

- Introduce the new database and `/api/v1` alongside current routes.
- Seed the operator's current resume through an explicit migration command.
- Do not migrate `temp/` files as durable product records; treat them as
  inspectable legacy artifacts.
- Keep old routes read-only or behind a feature flag during a short transition.
- Make frontend selection of old/new API a deployment configuration, not a
  user-visible toggle.
- Back up the database before schema migration.
- Roll back by deploying the prior application and restoring a compatible
  database backup; document schema compatibility per release.

## Key risks and spikes

| Risk | Smallest validation |
|---|---|
| PythonAnywhere buffers SSE | Deploy a minimal authenticated SSE heartbeat and measure chunk arrival in the web client. |
| SQLite is unsafe under deployment topology | Run overlapping write/read tests in the actual host and verify persistence across reload/deploy. |
| Split prompts reduce output coherence | Compare current one-call output with staged output on representative job/resume fixtures. |
| Follow-up context reduction drops evidence | Build an eval checking every material claim against the resume and answers. |
| Web OAuth configuration is stale | Inspect registered redirects and run success/failure callback paths. |
| LangSmith captures sensitive data | Inspect one identifiable trace before further live testing. |
| Extension and web adapters drift | Run the shared contract suite against both adapters; choose one primary release surface. |

## Resolved decisions and remaining questions

Resolved:

- Web is the primary limited-beta client.
- Chrome extension refactoring is deferred to a post-beta P2 increment.
- SQLite is the first-beta persistence layer, subject to production validation.
- Users can maintain multiple resume versions and select one per review.
- Synthetic demo sessions persist for 24 hours to support refresh/reconnect.
- Groq is the supported provider behind an OpenAI-compatible adapter.
- Resumes, job descriptions, answers, reviews, and model-call metadata persist
  throughout development.
- Optional prompt/response traces are not retained by the refactored workflow.

Remaining:

- Which Groq model should be the supported baseline for each LLM stage?
- Does the intended hosting path deliver SSE chunks reliably, or should the
  first release use durable status plus polling?
- What deletion controls should users receive during development?
- What retention period replaces development-long persistence before use
  expands beyond the limited beta?

## First implementation slice

After the deferred live validations, the first coding slice should be:

> Create an isolated, schema-validated demo review through a `ReviewService`
> and render it through the current frontend without reading or writing
> `temp/`.

Why first:

- directly removes a P0 exposure;
- establishes the service and response-schema boundaries needed by live mode;
- is deterministic and inexpensive to test;
- does not require solving multi-user persistence and streaming at the same
  time; and
- provides a safe fixture harness for every later backend and frontend change.
