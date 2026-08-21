# Job Application Coach — Ordered Backlog

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

## Cross-cutting testing and safety rules

- Write the behavioral assertion before fixing each confirmed defect.
- Normal tests must block live provider calls unless a fake is explicitly
  injected.
- Validate complete model output before replacing the prior valid artifact.
- Keep every test's mutable filesystem or database isolated.
- Validate canned demo fixtures and mocked live responses through the same
  consumer schemas.
- Preserve strict known-defect tests until the fixing increment makes them
  pass.
- Run focused tests, the complete backend suite, frontend logic tests, and the
  browser smoke test after each relevant increment. The web client has no
  compile or bundle step.
- Production validation is required for Google OAuth, Groq, hosting, and
  SQLite persistence; mocks do not establish those boundaries.
- Never log tokens, resumes, job descriptions, answers, raw prompts, or raw
  model responses.
- Keep production tracing disabled until explicit content, access, and
  retention controls exist.

## Increment 3.1 — Rename project and cut over the public deployment

Goal: Rename the public product to **Job Application Coach**, rename the public
GitHub repository to `job-application-coach`, and make
`jobapplicationcoach.pythonanywhere.com` the canonical deployment before
Increment 3.5 creates the first supported personal database. Start the new
PythonAnywhere deployment from a fresh checkout and virtualenv rather than
pointing the new site at the old deployment's `airecruitingagent` virtualenv.

Keep operational identifiers that do not affect the public product stable where
that avoids migration work: browser storage keys, SQLite table names, and the
`data/reviews.db` filename do not need renaming. The existing LangSmith project
name may also remain stable for trace continuity unless a separate observability
rename is wanted.

### Rename the public product surfaces

Update the visible product name, descriptions, API titles, active documentation,
backlog headings, deployment instructions, and links to the current repository.
Retain the existing marketing screenshots for now; their manual refresh is an
explicit follow-up and does not block this rename. Remove or replace the stale
Chrome-extension calls to action on the landing page; the extension is retired
and is not a supported release target.

Preserve the deprecated extension-authentication document as historical
documentation. Do not rewrite its old flow and host references as if they were
the current system; label or contextualize them only if needed.

gates_release_type: personal

### Rename the public GitHub repository

Rename `chungmengcheong/job-application-agent` to
`chungmengcheong/job-application-coach`. Update the local `origin`, README clone
and deployment commands, active links, and any public references. The local
checkout directory and Python package layout do not need to change.

gates_release_type: personal

### Provision a fresh canonical PythonAnywhere deployment

Create the web app for `jobapplicationcoach.pythonanywhere.com` with a fresh
checkout and virtualenv under the new free-account path
`/home/jobapplicationcoach`, set the production environment values, and
initialize the new deployment's database. The old `/home/airecruitingagent`
path belongs only to the previous account and rollback deployment. Do not copy
the old database unless there is an explicit decision to preserve its data;
Increment 3.5 already defines the supported personal database as fresh.

Keep the old deployment available as a rollback path until the new site passes
the exit gate. Then either redirect the old host to the new canonical host or
leave it as an explicitly retired deployment; do not leave two silently
diverging production sites.

gates_release_type: personal

### Rewire Google authentication for the new host

Keep the existing Web OAuth client ID unless a concrete Google-console reason
requires a new client. Register the new production origin and exact callback
URI, update the OAuth app's public branding and homepage references, and retain
the old origin during the rollback window if the old site remains usable.

Do not change `ALLOWED_DOMAINS`: in this application it is the authorized email
domain allowlist, not the website hostname. Do not combine this cutover with the
Google Identity Services, fail-closed callback validation, or browser-session
decision deferred to Increment 4; this increment only makes the current flow
work on the new canonical host.

gates_release_type: personal

### Preserve stable internal identifiers deliberately

Leave the existing `ai_recruiting_agent_auth`,
`ai_recruiting_agent_oauth_state`, `ai_recruiting_agent_oauth_nonce`, and
`ai_recruiting_agent_backend_mode` browser keys unchanged. A new hostname has a
new browser storage origin, so no key migration is required. Leave the existing
SQLite filename and schema identifiers unchanged; no database migration belongs
in this rename increment.

If the LangSmith project name is changed, treat the resulting loss of trace
continuity as an explicit tradeoff rather than an automatic string replacement.

gates_release_type: personal

Exit gate:

- The public product and repository are consistently named Job Application
  Coach / `job-application-coach` in active code, docs, links, and current
  marketing copy; remaining old references are explicitly historical, stable
  internal identifiers, or the intentionally deferred screenshot refresh.
- The local Git remote points to the renamed public repository.
- `jobapplicationcoach.pythonanywhere.com` serves `/`, `/app/`, `/health`, and
  durable review URLs from the fresh checkout and virtualenv.
- The new host has the correct production environment, proxy configuration,
  database path, and Google OAuth origin/callback registration.
- Login, logout, unauthorized-user handling, and permanent canned demo behavior
  work on the new host; production hides and ignores the development-only local
  API toggle, while local toggle tests remain green.
- The old host has a tested rollback or redirect path and no silently diverging
  production configuration remains.
- Focused tests, the complete backend suite, frontend logic tests, and the
  browser smoke test pass against the renamed codebase.


## Increment 3.5 — Add durable users and stored resumes

Goal: Create the minimum durable personal data model from a fresh database.
Do not migrate existing `users` or `reviews`. Bootstrap one personal user
(`ccmmail@gmail.com`) and port the single `user/resume.txt` into that user's
stored resume, then remove the live file dependency without adding beta
onboarding concerns.

### Create the fresh SQLite personal schema

Add `users` and `resumes` tables plus the review ownership/resume references,
foreign keys, transaction boundaries, and a development-safe initialization
command. A pre-existing database is outside this increment's compatibility
scope: initialize the supported personal database fresh rather than importing
historical `users` or `reviews`. Do not add repository hierarchies, separate
artifact tables, model-call tables, or optimistic versions.

gates_release_type: personal

### Seed the personal user and resume

Idempotently create the user with canonical email `ccmmail@gmail.com` and
create its initial stored resume from `user/resume.txt`. Do not fabricate a
Google identity claim while seeding. On the first verified login for that
allowlisted email, attach the stable Google `sub` to the seeded user; use that
`sub`, not email, as the ongoing ownership key. A verified login may update a
missing or changed display/audit email.

gates_release_type: personal

### Resolve internal users from verified identity

Resolve or create a user from the verified Google `sub`. Use email for display
and allowlist audit, never as the ongoing ownership key. The seeded personal
email is the one explicit bootstrap association; do not create a second user
for the same verified `ccmmail@gmail.com` login.

gates_release_type: personal

### Support the stored resume

Allow each user to create, retrieve, and update a stored resume. The initial
personal workflow has one stored resume; active-resume selection and resume
history remain deferred until multiple resumes are needed.
Switch `POST /api/v1/reviews` to take `resume_id` instead of inline resume content, and
update the (already `/api/v1`-based) web client to load the user's stored
resume accordingly. Do not add archive or resume version history yet.

gates_release_type: personal

Exit gate:

- A fresh personal database contains one seeded `ccmmail@gmail.com` user and
  the ported `user/resume.txt` as that user's stored resume; historical users
  and reviews are not imported.
- A verified login binds that user to the Google `sub` without creating a
  duplicate user.
- Review creation takes an owned `resume_id` while retaining an immutable
  inline snapshot for both model calls.
- The legacy live `GET /resume` path and `user/resume.txt` dependency are gone.
- The canned demo remains a separate fixture-based experience.


## Increment 4 — Validate the production boundary

Goal: Verify the deployment assumptions required by the supported personal web
application before adding beta onboarding behavior.

### Verify and harden web authentication

**Validation risk plus confirmed defects.** Exercise callback registration,
state, nonce, expiry, logout, verified email, and unauthorized-user paths. Fail
closed when expected state or nonce is missing. The current client directly
implements Google's implicit endpoint flow even though it needs authentication
only, not access to Google APIs; replace that hand-built flow with Google
Identity Services Sign in with Google unless a concrete requirement justifies
keeping it. Decide explicitly whether the resulting browser credential remains
client-stored or is exchanged for a server session rather than preserving
`localStorage` by default. Fix the confirmed backend defect that currently
treats a missing `email_verified` claim as verified.

gates_release_type: personal

### Validate the deployed personal workflow

Exercise login, stored-resume loading, Call 1, answers, Call 2, redline, and
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


## Increment 4.5 — Add authenticated one-time trial onboarding

Goal: Let a new visitor obtain one custom review without turning the canned
demo into a live unauthenticated provider endpoint. Durable users and resumes
already exist and the personal production workflow has already been validated.

### Collect trial inputs ephemerally

Allow a visitor to enter a resume and job description before authentication.
Keep them only in browser memory. Make no LLM call and persist no sensitive input.

gates_release_type: beta

### Require authentication and explicit submission

After authentication, show what will be submitted and require an explicit
action. Create the internal user, store the resume, create the owned review,
and then run the normal two-call workflow.

gates_release_type: beta

### Define one-time eligibility and abuse controls

Specify what makes the trial one-time and apply input, token, timeout, and rate
limits. Do not weaken ownership or create an unauthenticated Groq endpoint.

gates_release_type: beta

Exit gate:

- No sensitive trial input is persisted and no provider call occurs before authentication and explicit submission.
- The resulting resume and review are owned by the newly created user.
- The canned demo remains a separate fixture-based experience.

## Increment 5 — Prove limited-beta isolation

Goal: Safely extend the working product to a handful of invited users.

### Scope every store operation by owner

Require the authenticated internal user for all resume and review reads and
writes. Return the same not-found result for missing and other-user resources.

gates_release_type: beta

### Add two-user concurrency and authorization tests

Run overlapping review, follow-up, resume update, and forbidden-access
scenarios for two identities.

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
- Postgres unless SQLite production validation fails;
- active-resume selection and resume history until multiple stored resumes are
  needed.
