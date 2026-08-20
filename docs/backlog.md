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

## Increment 3.5 — Add durable users, stored resumes, and one-time trial onboarding

Goal: Introduce durable users and stored resumes — the identity that
Increment 2's `Review` records referenced only loosely, by raw `sub` and
inline resume content — and use them to let a new visitor obtain one custom
review without turning the canned demo into a live unauthenticated provider
endpoint.

### Add SQLite configuration and migrations for users and resumes

Add `users` and `resumes` tables with foreign keys and transaction boundaries,
and a development-safe initialization command. Migrate existing `reviews`
rows forward: resolve or create the matching `users` row for each recorded
`sub`, and add a nullable `resume_id` column recording which stored resume (if
any) a review used. Do not add repository hierarchies, separate artifact
tables, model-call tables, or optimistic versions.

gates_release_type: beta

### Add internal users derived from verified identity

Resolve or create a user from the verified Google `sub`. Use email for display
and allowlist audit, never as the ownership key.

gates_release_type: beta

### Support stored resumes and one active selection

Allow each user to create, list, retrieve, update, and activate stored resumes.
Exactly one stored resume may be active at a time. Switch `POST
/api/v1/reviews` to take `resume_id` instead of inline resume content, and
update the (already `/api/v1`-based) web client to select from stored resumes
accordingly. Do not add archive or resume version history yet.

gates_release_type: personal

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

- One authenticated user can manage stored resumes and select one as active.
- Reviews created back in Increment 2 resolve to a real owning `users` row.
- No sensitive trial input is persisted and no provider call occurs before authentication and explicit submission.
- The resulting resume and review are owned by the newly created user.
- The canned demo remains a separate fixture-based experience.


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
