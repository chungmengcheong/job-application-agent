# AI Recruiting Agent — Ordered Backlog

This is the single source of truth for implementation sequence. Work one
increment at a time and follow the listed item order unless new evidence changes
a dependency. Completed items move to [backlog-done.md](backlog-done.md) as they
land, so this file always reflects only remaining work.

`gates_release_type` records the earliest release that cannot proceed without
the item:

- `personal`: trustworthy personal production use
- `beta`: limited invited-user beta
- `general`: broader release
- `clean-up`: maintenance that does not gate a release

Entries marked **Confirmed** are supported by current code, tests, or build
configuration. **Validation risk** requires a live check.

## Increment 1 — Fix personal correctness and isolate the canned demo

Goal: Make the existing personal workflow trustworthy before restructuring it.
Preserve the current LLM workflow in this increment.

### Validate LLM output before changing state

**Confirmed.** Parse and validate the complete provider result before rotating
or replacing prior valid artifacts. Add bounded repair or safe failure for
invalid JSON and missing required fields.

gates_release_type: personal

### Keep the canned demo but make it read-only and isolated

Retain the checked-in synthetic resume, job description, initial response, and
follow-up response. Demo calls make no LLM request, require no account, create no
session, and never read or write live `user/` or `temp/` workflow state.

gates_release_type: personal

### Align canned demo and live consumer contracts

Validate demo fixtures and mocked live responses against the same schemas and
frontend consumer assertions. Exact model wording need not match.

gates_release_type: personal

Exit gate:

- A live review and follow-up use the same submitted job description and resume.
- Invalid model output leaves the prior valid state intact.
- Repeated demo calls cannot change live state and make no provider call.
- Production responses do not expose debug or provider exception details.

## Increment 1.5 — Adopt the two-call Groq workflow

Goal: Make the user journey match the evidence-gathering logic and make Groq the
single supported provider.

### Baseline the current workflow

Capture representative output quality, token use, latency, and failure behavior
before changing prompts or provider configuration.

gates_release_type: personal

### Introduce a thin injectable Groq client

Switch the supported provider from OpenAI to Groq. Isolate provider syntax,
timeouts, model configuration, usage metadata, and raw response handling behind
one small client that tests can replace. Do not build a multi-provider adapter
framework.

gates_release_type: personal

### Implement Call 1: analysis and questions

Input the selected resume and job description. Return validated fit, gaps, and
targeted questions. Do not generate a tailored resume in Call 1.

gates_release_type: personal

### Implement Call 2: revised analysis and tailored resume

Input the same resume, the same job description, and the user's answers. Return
validated revised fit, revised gaps, and a tailored resume. Generate the redline
deterministically only after the complete resume validates.

gates_release_type: personal

### Update the web workflow and tests

Show fit, gaps, and questions after Call 1. Show revised fit, revised gaps, and
the tailored redline after Call 2. Test both calls with injected responses; the
normal suite makes no paid calls.

gates_release_type: personal

### Compare against the baseline

Confirm that the two-call flow does not materially reduce evidence fidelity,
truthfulness, fit quality, or resume coherence.

gates_release_type: personal

Exit gate:

- Call 1 returns only fit, gaps, and targeted questions.
- Call 2 uses the original resume and job description plus answers and returns
  revised fit, revised gaps, and a tailored resume.
- Groq is the only supported provider and failures are safe.
- The canned demo remains deterministic and makes no Groq call.

## Increment 2 — Introduce durable users, resumes, and reviews

Goal: Replace global workflow files with a small durable domain model.

### Add SQLite configuration and migrations

Create `users`, `resumes`, and `reviews` tables with foreign keys, transaction
boundaries, and a development-safe initialization command.

gates_release_type: beta

### Add internal users derived from verified identity

Resolve or create a user from the verified Google `sub`. Use email for display
and allowlist audit, never as the ownership key.

gates_release_type: beta

### Support stored resumes and one active selection

Allow each user to create, list, retrieve, update, and activate stored resumes.
Exactly one stored resume may be active at a time. Do not add archive or resume
version history yet.

gates_release_type: personal

### Make Review the durable unit of work

Persist owner, selected resume ID, immutable resume snapshot, immutable job
description, answers JSON, validated result JSON, simple status, safe error, and
timestamps. Use `processing | awaiting_answers | completed | failed`.

gates_release_type: personal

### Add a thin ReviewService and SQLite store

FastAPI routes own HTTP concerns; `ReviewService` owns the two-call workflow;
one store module owns SQLite operations; the existing deterministic redline
function remains a function. Do not add repository hierarchies, separate
artifact tables, model-call tables, or optimistic versions.

gates_release_type: personal

### Implement the minimal JSON API

Add:

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

Use one safe typed error envelope.

gates_release_type: personal

### Cut over without a compatibility facade

Switch the single supported web client to `/api/v1` in a coordinated change.
After verification, remove the old live endpoints and global workflow files.

gates_release_type: personal

Exit gate:

- One authenticated user can manage stored resumes and select one as active.
- A review and its follow-up are durable and recoverable by review ID.
- Both calls use the immutable resume snapshot and job description.
- The supported live workflow has no `temp/` dependency.

## Increment 2.5 — Add authenticated one-time trial onboarding

Goal: Let a new visitor obtain one custom review without turning the canned demo
into a live unauthenticated provider endpoint.

### Collect trial inputs ephemerally

Allow a visitor to enter a resume and job description before authentication.
Keep them only in browser memory. Make no LLM call and persist no sensitive input.

gates_release_type: beta

### Require authentication and explicit submission

After authentication, show what will be submitted and require an explicit
action. Create the internal user, store the resume as active, create the owned
review, and then run the normal two-call workflow.

gates_release_type: beta

### Define one-time eligibility and abuse controls

Specify what makes the trial one-time and apply input, token, timeout, and rate
limits. Do not weaken ownership or create an unauthenticated Groq endpoint.

gates_release_type: beta

Exit gate:

- No sensitive trial input is persisted and no provider call occurs before
  authentication and explicit submission.
- The resulting resume and review are owned by the newly created user.
- The canned demo remains a separate fixture-based experience.

## Increment 3 — Simplify the web client around the durable API

Goal: Make the web application deliberate, restorable, and independently
maintainable without Chrome abstractions.

### Add a typed API client

Centralize `/api/v1` requests, schemas, safe errors, authentication headers, and
timeouts. Do not add event-stream parsing.

gates_release_type: personal

### Introduce explicit workflow state

Separate durable server state, review workflow state, and local editing state.
Authentication must not be inferred from loaded resume content.

gates_release_type: personal

### Apply the minimum component split

Extract only a review workspace, resume management/selection, review display,
and redline editing around the typed client and workflow model. Split further
only when behavior becomes independently complex.

gates_release_type: clean-up

### Build a deliberate full-page web product

Remove Chrome-only controls and fixed side-panel assumptions. Add responsive
resume and review routes, accessible loading/error states, and restoration by
durable review ID.

gates_release_type: beta

### Standardize the supported web build

Choose one package manager and lockfile, replace `latest` ranges, add
non-interactive lint/typecheck, stop suppressing failures, and add a
production-like browser smoke test.

gates_release_type: beta

Exit gate:

- Refresh restores a durable review from the backend.
- The supported web build passes tests, typecheck, lint, build, and smoke test.
- Supported web code has no Chrome platform abstraction or behavior.

## Increment 4 — Validate the production boundary

Goal: Verify the deployment assumptions required by the supported personal web
application.

### Verify and harden web authentication

**Validation risk plus confirmed defects.** Exercise callback registration,
state, nonce, expiry, logout, verified email, and unauthorized-user paths. Fail
closed when expected state or nonce is missing.

gates_release_type: personal

### Validate the deployed personal workflow

Exercise login, active-resume selection, Call 1, answers, Call 2, redline, and
reload in the deployed web app.

gates_release_type: personal

### Validate SQLite on the production host

Verify durable filesystem behavior, locking, backup/restore, deployment
persistence, and overlapping writes before beta. Move to managed Postgres only
if these assumptions fail materially.

gates_release_type: beta

### Validate Groq from the production host

Verify the supported model, proxy behavior, timeouts, safe errors, and usage
capture through the thin client.

gates_release_type: personal

### Verify production tracing is disabled

Confirm `LANGSMITH_TRACING_V2=false`. Do not trace beta-user prompt or response
content without explicit content, access, and retention controls.

gates_release_type: personal

Exit gate:

- Every production validation risk is converted to verified behavior,
  configuration work, or a reproducible defect.

## Increment 5 — Prove limited-beta isolation

Goal: Safely extend the working product to a handful of invited users.

### Scope every store operation by owner

Require the authenticated internal user for all resume and review reads and
writes. Return the same not-found result for missing and other-user resources.

gates_release_type: beta

### Add two-user concurrency and authorization tests

Run overlapping review, follow-up, resume update, activation, and forbidden
access scenarios for two identities.

gates_release_type: beta

### Add retention and deletion controls

Define development-period retention and provide explicit user/operator deletion
before expanding beyond the invited beta.

gates_release_type: beta

### Add proportionate operations support

Add safe structured request/review logging, health/readiness checks, backup and
restore instructions, and a repeatable deploy/rollback procedure.

gates_release_type: beta

Exit gate:

- Two users can run overlapping workflows with no cross-user access or state
  corruption.
- The beta has a tested release, backup, and rollback path.

## Cleanup — Archive the frozen Chrome extension implementation

Perform after the supported web application no longer depends on extension-only
files. This retires the current implementation, not the extension hypothesis.

- Keep extension development and releases frozen during the web-first phase.
- Separate any still-shared web code.
- Delete manifest, service worker, content script, Chrome OAuth/storage code,
  extension packaging scripts, generated artifacts, and extension-only tests.
- Rename `BrowserExtension/` to a web-oriented directory in a contained change.
- Preserve a tagged Git reference and a short historical architecture note.

gates_release_type: clean-up

## Future decision — Reassess a thin browser-native extension

After the web workflow is reliable, test whether these jobs justify a second
client:

- extract a job description from the active page;
- assist with user-approved application-form completion; and
- inspect relevant networking context.

If retained, build a thin purpose-built extension over the proven API. Reuse UI
components only where demonstrated sharing is cheaper than purpose-built UI.
Do not automatically restore the current extension architecture or introduce
platform adapters before the decision.

gates_release_type: clean-up

## Explicitly deferred

These are not ordered implementation commitments:

- SSE, WebSockets, event sequencing, or browser-visible provider streaming;
- persisted demo sessions and demo refresh continuity;
- a three-stage LLM workflow;
- artifact/answer/final-resume version checks;
- separate artifact and model-call tables;
- multi-provider abstractions;
- advanced automatic retry orchestration;
- finalized-resume persistence;
- Chrome extension implementation until the browser-native jobs are reassessed;
- Postgres unless SQLite production validation fails.
