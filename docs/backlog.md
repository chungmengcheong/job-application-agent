# AI Recruiting Agent — Ordered Backlog

This backlog is ordered by proposed implementation sequence. Increments are
intended to be small vertical advances, not long-lived parallel workstreams.
Within each increment, entries are listed in execution order.

- P0: required for trustworthy personal use in production
- P1: required before a limited multi-user beta
- P2: should-do work that can follow the safe core workflow
- P3: useful cleanup or enhancement

Entries marked **Confirmed** are supported directly by code, tests, or build
configuration. Entries marked **Validation risk** require a live check before
the implementation choice is considered settled.

## Increment: 1 — Fix personal correctness and isolate demo

Title: Preserve the submitted job description through follow-up
Description: **Confirmed.** `/review` does not save its job description, while `/questions` rereads the demo-seeded global file. Bind follow-up answers to the original review and job description.
Priority: P0
Date_added: 2026-07-25

Title: Fix startup cleanup semantics
Description: **Confirmed.** One missing temp file stops deletion of later files, allowing stale answers or model output to survive. Remove files independently as an interim fix before eliminating global workflow files.
Priority: P0
Date_added: 2026-07-25

Title: Disable production debug behavior and sanitize errors
Description: **Confirmed.** FastAPI uses `debug=True`, and provider exception text is returned to clients. Add environment-specific debug configuration and stable non-sensitive errors.
Priority: P0
Date_added: 2026-07-25

Title: Add typed review input and output schemas
Description: **Confirmed gap.** Add Pydantic contracts for review analysis, questions, gap values, tailored resumes, and error responses before changing orchestration.
Priority: P1
Date_added: 2026-07-25

Title: Validate LLM output before changing state
Description: **Confirmed.** Parse and validate model output before replacing prior artifacts. Add bounded repair or safe failure behavior for invalid JSON and missing fields.
Priority: P1
Date_added: 2026-07-25

Title: Create an isolated ReviewService demo slice
Description: **Confirmed need.** Route demo behavior through a `ReviewService`, shared schemas, and deterministic redline generation without reading or writing live `user/` or `temp/` state.
Priority: P0
Date_added: 2026-07-25

Title: Replace caller-controlled demo flags with demo routes
Description: **Confirmed.** Remove unauthenticated `demo: true` branches from live mutation endpoints. Create dedicated `/api/v1/demo/reviews` routes that select synthetic scenarios server-side.
Priority: P0
Date_added: 2026-07-25

Title: Retain synthetic demo sessions for 24 hours
Description: Store demo reviews under unguessable session IDs, support refresh and reconnect, and automatically delete them after 24 hours. Demo records must never resolve through live-user repositories.
Priority: P1
Date_added: 2026-07-25

Title: Align demo and live contracts
Description: **Confirmed.** Validate fixtures against the same schemas and consumer assertions used by mocked live responses, including status transitions, redlines, and frontend rendering.
Priority: P2
Date_added: 2026-07-25

## Increment: 2 — Introduce durable review persistence

Title: Refactor backend into explicit boundaries
Description: **Confirmed maintainability issue.** Separate FastAPI routes, `ReviewService`, repositories, the Groq/OpenAI-compatible adapter, and deterministic `RedlineService`.
Priority: P2
Date_added: 2026-07-25

Title: Add SQLite configuration and migrations
Description: Create the selected first-beta database, migration workflow, foreign keys, transaction boundaries, and a development-safe initialization command.
Priority: P1
Date_added: 2026-07-25

Title: Add internal users derived from verified identity
Description: Resolve or create a `User` from the verified Google `sub` claim. Use email for display and allowlist audit, never as the primary ownership key.
Priority: P1
Date_added: 2026-07-25

Title: Support multiple resume versions
Description: Replace the single operator-owned resume file with per-user resume records supporting create, update, list, archive, and explicit selection for each review.
Priority: P1
Date_added: 2026-07-25

Title: Make Review the durable unit of work
Description: Persist owner, resume snapshot, job description, source URL, mode, lifecycle status, versions, safe errors, and timestamps under one review ID.
Priority: P1
Date_added: 2026-07-25

Title: Add transactional workflow transitions
Description: Make `ReviewService` the only state-transition owner. Preserve the last valid artifact on failure and record each retry as a new model-call attempt.
Priority: P1
Date_added: 2026-07-25

Title: Persist typed review artifacts
Description: Store versioned analysis, gap map, questions, answers, tailored resume, and deterministic redline separately from raw provider responses.
Priority: P1
Date_added: 2026-07-25

Title: Add artifact and answer version checks
Description: Reject stale follow-up answers and finalized-resume saves when their source analysis or tailored-resume version has changed.
Priority: P1
Date_added: 2026-07-25

Title: Persist model-call metadata without prompt content
Description: Record stage, provider, model, prompt version, status, token usage, latency, and safe error code. Do not store raw prompts, responses, resumes, or job descriptions as optional traces.
Priority: P1
Date_added: 2026-07-25

Title: Implement the versioned JSON API
Description: Add `/api/v1/me`, resume management, create/get review, submit answers, retry, and finalized-resume endpoints with ownership-aware service calls.
Priority: P1
Date_added: 2026-07-25

Title: Add one typed API error contract
Description: Return stable error codes, safe messages, request IDs, retryability, and correct HTTP statuses. Eliminate HTTP-200 error objects and frontend string searches for `401` or `403`.
Priority: P2
Date_added: 2026-07-25

Title: Keep current endpoints behind a short compatibility facade
Description: Route legacy calls through the new service only while the web client migrates. Do not add new behavior to the old file-backed contract.
Priority: P2
Date_added: 2026-07-25

## Increment: 3 — Rebuild the web client around the new API

Title: Split the monolithic panel into product features
Description: Extract job description, review summary, gap map, follow-up questions, tailored resume, redline editor, and review workspace from `extension-panel.tsx`.
Priority: P2
Date_added: 2026-07-25

Title: Separate shared product code from platform adapters
Description: Introduce narrow auth, storage, and page-context interfaces. Product features must not call `window.chrome`, parse OAuth fragments, or construct backend URLs.
Priority: P2
Date_added: 2026-07-25

Title: Implement a typed JSON and event API client
Description: Centralize `/api/v1` requests, response schemas, common error codes, authentication headers, timeouts, and later SSE event parsing.
Priority: P1
Date_added: 2026-07-25

Title: Replace interacting booleans with an explicit workflow model
Description: Separate durable server state, discriminated review workflow state, and ephemeral local UI/editing state. Authentication must not be inferred from loaded resume content.
Priority: P2
Date_added: 2026-07-25

Title: Build the web app as a deliberate full-page product
Description: Add responsive resume and review routes, explicit paste behavior, accessible loading/error states, and no Chrome-only controls or fixed side-panel layout.
Priority: P1
Date_added: 2026-07-25

Title: Choose one canonical web entry point
Description: Decide whether Vercel or the FastAPI-hosted page is the product URL, then make other web entry points redirect or link to it.
Priority: P1
Date_added: 2026-07-25

Title: Restore reviews by durable ID
Description: Route review pages by review ID and refetch resume, status, analysis, questions, and tailored resume after reload instead of relying on React memory.
Priority: P1
Date_added: 2026-07-25

Title: Persist finalized resume edits explicitly
Description: Keep hover and accept/reject/edit state local until the user saves. Store the resulting plain resume with its source tailored-resume version; retain copy/download without forced persistence.
Priority: P2
Date_added: 2026-07-25

Title: Replace brittle regex redline parsing
Description: **Confirmed by test.** A replacement followed by a standalone deletion can be merged into one incorrect change. Parse the server redline contract deterministically and prove mixed/repeated changes reconstruct both resume versions.
Priority: P1
Date_added: 2026-07-25

Title: Remove the backend selector from production
Description: Make backend URL deployment configuration and expose local/cloud selection only in development builds.
Priority: P3
Date_added: 2026-07-25

Title: Standardize the frontend build system
Description: Choose one package manager and lockfile, replace `latest` ranges, remove unused shims, add non-interactive lint/typecheck, and stop suppressing failures during web builds.
Priority: P1
Date_added: 2026-07-25

Title: Establish the web release gate
Description: Require frontend unit/contract tests, typecheck, lint, static build, and a production-like browser smoke test before deployment.
Priority: P1
Date_added: 2026-07-25

## Increment: 4 — Add durable local streaming

Title: Add durable Server-Sent Events
Description: Expose typed, sequenced status, content-delta, completion, and safe-failure events while keeping the durable review record as source of truth.
Priority: P2
Date_added: 2026-07-25

Title: Add a typed web event client and polling fallback
Description: Consume sequenced events, reconnect by review ID, and recover from the durable review record. Keep polling as a supported fallback when streaming is unavailable.
Priority: P2
Date_added: 2026-07-25

Title: Validate streaming recovery without paid calls
Description: Use deterministic mocked chunks to test disconnect, refresh, timeout, malformed events, and completed-server/failed-client cases without duplicate work or false completion.
Priority: P2
Date_added: 2026-07-25

## Increment: 5 — Validate the production boundary

Title: Verify and harden web authentication
Description: **Validation risk plus confirmed defect.** Confirm the deployed callback registration and exercise state, nonce, expiry, logout, and unauthorized-user paths. Enforce verified email before allowlist checks and fail closed when expected state or nonce is missing.
Priority: P0
Date_added: 2026-07-25

Title: Validate the deployed personal web workflow
Description: **Validation risk.** Exercise login, resume selection, review, follow-up questions, redline editing, save, and copy/download in the deployed web app.
Priority: P0
Date_added: 2026-07-25

Title: Validate SQLite on the production host
Description: **Validation risk.** Confirm durable filesystem behavior, locking, backup/restore, deployment persistence, and overlapping writes before relying on SQLite for beta.
Priority: P1
Date_added: 2026-07-25

Title: Validate Groq from the production host
Description: **Validation risk.** Verify the supported Groq model through the OpenAI-compatible adapter, including proxy behavior, timeouts, safe errors, and model-call metadata.
Priority: P0
Date_added: 2026-07-25

Title: Validate streaming through the hosting path
Description: **Validation risk.** Verify that the deployed SSE path reaches the web client without buffering or premature termination. Retain durable polling if the host cannot stream reliably.
Priority: P2
Date_added: 2026-07-25

Title: Verify LangSmith tracing is disabled in production
Description: Confirm production sets `LANGSMITH_TRACING_V2=false`. Keep development tracing limited to accepted demo/personal data until content, access, and retention guards are implemented.
Priority: P0
Date_added: 2026-07-25

## Increment: 6 — Make the LLM loop efficient

Title: Baseline current LLM quality, tokens, and latency
Description: Record representative first-review and follow-up results, input/output tokens, time to first useful output, total latency, and failure rate before splitting the prompt.
Priority: P2
Date_added: 2026-07-25

Title: Split structured analysis from resume tailoring
Description: Make the first Groq call return validated fit, positioning, stable gap IDs, and stable question IDs. Persist and display analysis before generating the resume.
Priority: P2
Date_added: 2026-07-25

Title: Stream plain tailored-resume generation
Description: Use Groq's OpenAI-compatible streaming interface for the tailoring stage. Stream plain resume text only; generate redlines deterministically after final validation.
Priority: P2
Date_added: 2026-07-25

Title: Add provider timeout and safe-retry rules
Description: Configure explicit connect/read/total timeouts. Retry only pre-stream or provably idempotent failures; never replay ambiguous partial generation automatically.
Priority: P2
Date_added: 2026-07-25

Title: Reduce follow-up context
Description: Send compact job requirements, affected gaps, relevant resume evidence, and new answers rather than prior prose and the previously tailored resume. Measure quality before removing the full resume snapshot.
Priority: P2
Date_added: 2026-07-25

Title: Compare the staged workflow with the baseline
Description: Confirm improved time to first useful output and lower repeated tokens without material loss of evidence, truthfulness, fit quality, or resume coherence.
Priority: P2
Date_added: 2026-07-25

## Increment: 7 — Prove multi-user isolation

Title: Scope every repository operation by owner
Description: Ensure resume and review reads, writes, retries, answers, and deletes require the authenticated internal user. Return the same not-found result for missing and other-user resources.
Priority: P1
Date_added: 2026-07-25

Title: Add two-user concurrency and authorization tests
Description: Run overlapping review, follow-up, resume update, and unauthorized-access scenarios for two identities—not only sequential happy paths.
Priority: P1
Date_added: 2026-07-25

Title: Define development-period retention and deletion controls
Description: Persist resumes, job descriptions, answers, reviews, and model-call metadata throughout development. Provide explicit user/operator deletion and document when the policy must be revisited before broader use.
Priority: P1
Date_added: 2026-07-25

## Increment: 8 — Harden and retire compatibility paths

Title: Add structured request and workflow logging
Description: Record request ID, safe user identifier, review ID, route/stage, status, duration, model/prompt version, token usage, and safe error codes without sensitive content.
Priority: P1
Date_added: 2026-07-25

Title: Add health, readiness, and failure inspection
Description: Extend the process heartbeat with non-sensitive configuration/dependency readiness and an operator view of failed reviews and retryability.
Priority: P2
Date_added: 2026-07-25

Title: Expand the backend release gate with the new architecture
Description: **Baseline established.** The pre-refactor suite now passes with known defects marked `xfail`. Add domain, repository, ownership, schema, concurrency, and streaming tests as those boundaries are introduced.
Priority: P1
Date_added: 2026-07-25

Title: Remove global workflow files and legacy endpoints
Description: Retire `temp/` state, single-user resume files, and old routes only after the web client uses `/api/v1` and migration/rollback have been verified.
Priority: P1
Date_added: 2026-07-25

Title: Quarantine legacy extension paths
Description: Freeze the extension as a non-beta surface and separate obsolete iframe/manual-panel paths so they cannot affect the supported web build.
Priority: P3
Date_added: 2026-07-25

Title: Remove stale dependencies and configuration
Description: Remove unused backend/frontend packages, duplicate entry points, provider remnants, and obsolete build settings after compatibility paths are retired.
Priority: P3
Date_added: 2026-07-25

Title: Keep living documentation synchronized
Description: Update architecture, API, frontend, backlog, deployment, and rollback notes in the same change that introduces or retires a supported boundary.
Priority: P3
Date_added: 2026-07-25

Title: Document backup, restore, deploy, and rollback
Description: Define SQLite backup/restore, schema migration, production deployment, compatibility, and rollback procedures before the limited beta release.
Priority: P1
Date_added: 2026-07-25

## Increment: 9 — Revisit the Chrome extension after web beta

Title: Reassess whether the extension remains worth supporting
Description: Use web-beta learning to decide whether active-tab context and side-panel convenience justify maintaining a second client.
Priority: P2
Date_added: 2026-07-25

Title: Retain one Manifest V3 side-panel shell
Description: If retained, make the extension a thin shell over shared product features and remove the iframe/content-script panel and parallel source/generated entry paths.
Priority: P2
Date_added: 2026-07-25

Title: Implement Chrome platform adapters
Description: Isolate Chrome identity, `chrome.storage`, active-tab context, and side-panel lifecycle behind the same narrow interfaces used by the web adapters.
Priority: P2
Date_added: 2026-07-25

Title: Add an extension release gate
Description: Require shared contract tests, typecheck, extension build, OAuth verification, and a manual installed-side-panel smoke test before calling the extension supported.
Priority: P2
Date_added: 2026-07-25
