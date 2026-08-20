# AI Recruiting Agent — Frontend Notes

This document records the current frontend and the supported web-only target.

**Landed (Increment 3, 2026-08-20):** the supported web client is plain
HTML/CSS/JS with no build step, served by the same FastAPI app as
`/api/v1` (`web/`), replacing the Next.js/React app for the supported
product. See `plan-refactor-frontend.md` for the historical implementation
plan this followed. The obsolete `BrowserExtension/` tree and generated
extension release have now been removed; Git tag
`chrome-extension-last-working` preserves the last working implementation.

## Supported web client (`web/`)

One page (`web/index.html`) with a handful of ES modules under `web/js/`,
loaded directly by the browser via `<script type="module">` — no bundler,
transpiler, or package.json:

```text
web/js/
    auth.js              Google OAuth (implicit flow) + token storage
    api.js                /api/v1 fetch helper (auth header, timeouts,
                          safe-error-envelope parsing) + the one legacy
                          authenticated GET /resume getter Increment 3.5
                          replaces with stored resumes
    demo-api.js           the canned demo's non-/api/v1 routes
    workflow.js            durable/workflow/local state boundary; derives
                          what to show from review?.status
    review-workspace.js    orchestrator: DOM wiring, submit/answer actions
    review-display.js      fit/gap/question render functions
    redline.js              accept/reject/edit for the deterministic redline
    main.js                 bootstrap + durable-review-ID restoration
web/auth-callback.html      OAuth fragment parsing, state/nonce check, redirect
web/css/styles.css          plain CSS (flexbox/grid)
web/tests/*.test.mjs         pure-logic unit tests (`node --test`)
```

Served same-origin from the existing FastAPI app:

- `app.mount("/app", StaticFiles(directory=WEB_DIR, html=True))` serves
  `web/index.html` at `/app/` and every other file under `web/` as-is.
- `GET /app/reviews/{review_id}` is an explicit route registered before that
  mount (a static mount alone 404s on a path with no matching file); it
  serves the same `index.html`, and `main.js` reads the ID back out of
  `location.pathname` and hydrates via `GET /api/v1/reviews/{review_id}`.
- The marketing splash (`static/index.html`, unchanged) links to `/app/`
  instead of the retired Vercel deploy.

Because the web client is same-origin with `/api/v1`, every request is a
plain relative `fetch(...)` — no `BACKEND_URL` env, no local/cloud dev
toggle, and no CORS handling for this origin at all.

## Retired extension runtime

The former side-panel manifest, background worker, content script, Chrome
identity/storage code, Next.js/React client, packaging scripts, generated
artifacts, and extension-only tests are no longer in the active tree. The
supported `web/` client never imported them, so no web-oriented rename or
shared platform adapter was needed.

After the web workflow is reliable, reassess a new thin extension against three
browser-native jobs: extracting the active page's job description, assisting
with user-approved application-form completion, and inspecting relevant
networking context. Reuse the proven API and only the UI components that are
actually economical to share.

## Current dataflow

```text
page loads at /app/
    -> demo mode by default; job description prefilled from the demo fixture

user logs in (full-page Google OAuth redirect, then back to /app/)
    -> authenticated; the one live operator resume is loaded (GET /resume)

submit job description
    -> Call 1 (demo: POST /review; live: POST /api/v1/reviews)
    -> fit + gaps + questions
    -> live mode pushes /app/reviews/{id} into the URL (history.pushState)

submit answers
    -> Call 2 (demo: POST /questions; live: POST /api/v1/reviews/{id}/answers)
    -> revised fit + revised gaps + tailored redline

refresh, or load /app/reviews/{id} directly
    -> main.js calls GET /api/v1/reviews/{id} and hydrates the same view
```

Demo mode never touches the URL or `/api/v1` (see "Canned demo experience"
below); only live reviews are restorable by ID.

## Canned demo experience

Keep the current product experience:

- fixed synthetic resume and job description;
- canned initial and follow-up results;
- no authentication, account, provider call, persistence, or continuity;
- read-only server fixtures; and
- the same frontend response schemas as mocked live behavior.

The future authenticated one-time trial is separate. It may collect a resume
and job description in browser memory, then requires authentication and explicit
submission before persistence or a custom provider call.

## State ownership

### Durable server state

- current authenticated user (from the verified ID token, not yet a durable
  `users` row — Increment 3.5);
- the one live operator resume (Increment 3.5 adds stored resumes and
  active-resume selection);
- review ID, immutable inputs, status, answers, and validated result; and
- completed tailored resume and redline.

Refreshing the page refetches this state by ID (`web/js/main.js`).

### Workflow state

`web/js/workflow.js` does not invent a separate client-side state name kept
in sync by hand. What the UI shows derives directly from the review's own
status (`processing | awaiting_answers | completed | failed`, the same enum
`backend/review_store.py` uses) once a review exists, alongside a few
independent flags that aren't part of that enum: `authenticated`,
`demoMode`, `loading`, and `error` (plus `notAuthorized`, distinct from
`authenticated` — a 403 leaves the session valid but forbids one resource,
while a 401 signs the user out).

Authentication is tracked from `auth.js`'s stored-token presence, never
inferred from whether a resume fetch happened to succeed.

### Local UI state

- unsent job description and source URL (`review-workspace.js`);
- unsent answers (`review-display.js`'s question form);
- per-change accept/reject/edit overrides and the redline-visibility toggle
  (`redline.js`); and
- copy feedback.

Finalized-resume persistence is deferred. Copy and local editing remain
without creating additional server artifact versions.

## Shared fetch helper

`web/js/api.js` centralizes:

- `/api/v1` URLs;
- bearer headers;
- safe error codes (attaches the HTTP status to the thrown `Error` so
  callers can distinguish 401 from 403); and
- timeouts (150s for the two model calls, 30s elsewhere) and JSON parsing.

This is a small module, not a compiled "typed" client — nothing enforces
request/response shapes without a compiler, and the backend already
validates them (`backend/schemas.py`) before they reach the browser. It does
not add SSE parsing, reconnect logic, provider events, or Chrome storage
abstractions. `web/js/demo-api.js` is a separate, equally small module for
the canned demo's non-`/api/v1` routes, whose response and error shapes
differ from the durable contract.

## Redline editing

`web/js/redline.js` parses the backend's deterministic
`<span style="color:#008000"><add>…</add></span>` /
`...#c00000"><del>…</del></span>` markup (`backend/redline.py`) into an
ordered list of segments and addresses each one by array index rather than
by re-matching the original markup substring. The prior React port
(`BrowserExtension/components/resume-renderer.tsx`) used
`tailoredMarkdown.replace(originalMarkup, ...)`, which targets only the
first textual match — wrong when two changes carry identical markup (e.g.
the same word changed on two different resume lines). Index-based
addressing does not have that failure mode. Accept/reject/edit toolbars use
CSS `:hover`/`:focus-within`, not JS-tracked hover state.

## Build and release contract

The supported web client is plain HTML/CSS/JS with no package manager,
lockfile, bundler, or compiler — most of a conventional "build and release
contract" is satisfied by that absence rather than by a passing check:

- non-interactive pure-logic unit tests: `node --test web/tests/*.test.mjs`
  (no install step, no `package.json`);
- one documented production-like browser smoke test exercising the two-call
  demo flow and durable-review-ID restoration:
  `pytest tests/test_web_smoke.py` (dev-only —
  `pip install -r requirements-dev.txt && playwright install chromium`;
  skips cleanly if playwright isn't installed); and
- one documented way to run it locally: `uvicorn backend.api:app --reload
  --port 8000`, then browse to `http://127.0.0.1:8000/app/` — editing any
  `web/` file takes effect on the next refresh, no build/watch process
  involved.

The retired Next.js/React app and extension build remain available at Git tag
`chrome-extension-last-working`. A future extension would receive its own
release contract if the browser-native jobs justify resuming it.

## Current web gaps

- OAuth callback registration and failure behavior are not live-verified
  (Increment 4).
- `web/auth-callback.html` ports the prior callback's behavior as-is: it
  does not fail closed when expected state or nonce is missing from
  `sessionStorage` (Increment 4 hardens this).
- multiple stored resumes and active selection do not yet exist — the live
  workflow still loads the one operator resume via the legacy authenticated
  `GET /resume` (Increment 3.5 replaces this with `resume_id`); and
- redline accept/reject/edit interactions are hover-driven, not yet
  keyboard-operable.

## Validation boundary

Static code and configuration establish the current state model, build
shape, and the client-side restoration mechanism (verified by
`tests/test_web_smoke.py` against a real browser and a real server process,
using a seeded token and an intercepted API response rather than live
OAuth). They do not prove deployed OAuth, responsive layout, or a live
authenticated two-call workflow end to end. Those require the explicit
production checks in [../backlog.md](../backlog.md)'s Increment 4.
