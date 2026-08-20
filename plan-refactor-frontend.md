# Implementation Plan — Increment 3: Simplify the web client around the durable API

Source: [`docs/backlog.md`](docs/backlog.md), "Increment 3 — Simplify the web
client around the durable API". This plan sequences that increment's five
items into concrete file-level work. It does not touch Increment 3.5+ scope
(stored resumes, users) or the later Chrome-extension archival cleanup.

**Revised direction (2026-08-19):** the original draft of this plan kept
`BrowserExtension/`'s Next.js/React stack and refactored it in place. After
review, the plan now rewrites the web client as plain HTML/CSS/JS with no
build step, served directly by the existing FastAPI app on PythonAnywhere —
retiring Vercel and Node/npm entirely from the supported product. Rationale:

- The actual product surface is small (paste a job description → fit/gaps/
  questions → answers → tailored resume/redline) and doesn't need a
  component framework to stay maintainable.
- Most of today's `package.json` is dead weight unrelated to being "a webapp
  that grew out of a Chrome extension": ~30 Radix/shadcn UI packages are
  listed, but `extension-panel.tsx` only ever imports about six of them.
  Trimming that tree doesn't require keeping the tree.
- `static/index.html` already proves the pattern: FastAPI serves a
  hand-written HTML/CSS page directly today, with no framework or build
  step, for the marketing splash. The interactive product can follow the
  same pattern.
- A future Chrome extension (job-description extraction, autofill, LinkedIn
  page parsing — see backlog's "Future decision — Reassess a thin
  browser-native extension") needs client-side code running in the page
  regardless of what the main webapp is built in. It doesn't need the
  webapp to be React, and per that backlog item, building toward it now
  ("introduce platform adapters before the decision") is explicitly out of
  scope.
- Deploying one FastAPI app on PythonAnywhere, instead of FastAPI on
  PythonAnywhere *plus* a Next.js static export on Vercel, removes a whole
  cross-origin surface (CORS, a separate `BACKEND_URL` build-time env, a
  local/cloud dev toggle) and a second deploy target to keep in sync.

Goal (from backlog): make the web application deliberate, restorable, and
independently maintainable without Chrome abstractions.

Exit gate (from backlog):

- Refresh restores a durable review from the backend.
- The supported web build passes tests, typecheck, lint, build, and smoke test.
- Supported web code has no Chrome platform abstraction or behavior.
- (Read literally, "typecheck"/"lint"/"build" presuppose a compiled/bundled
  client. Step 5 below explains how a build-free vanilla client still
  satisfies the intent of each bullet — mostly by the step not applying, not
  by faking an equivalent.)

## Current state (as of `2dc41c6`)

- `BrowserExtension/` is a Next.js/React app, statically exported and
  deployed to Vercel, that also gets repackaged as a Manifest V3 Chrome
  extension (`scripts/build-extension.js` runs `next build` then copies
  `manifest.json`/`background.js`/`content.js` alongside the static output).
  `lib/api.ts` mixes Chrome extension auth (`chrome.identity`,
  `chrome.storage`, `chrome.tabs`), web OAuth, a dev backend-URL toggle, demo
  calls, and ad hoc `/api/v1` envelope-unwrapping in one file.
  `extension-panel.tsx` is a single ~1000-line component holding all
  workflow state as flat `useState` calls, with authorization partly
  inferred from whether a resume fetch happened to succeed.
- `components/resume-renderer.tsx` contains the actual redline
  accept/reject/edit logic in use today (regex-parses the backend's
  `<span style="color:#008000"><add>…</add></span>` /
  `...#c00000"><del>…</del></span>` markup, injects hoverable inline
  controls). `components/inline-redline.tsx` and
  `lib/inline-redline-parser.ts` are a second, **unused** implementation of
  the same idea — `extension-panel.tsx` never imports them. Don't port
  dead code; port `resume-renderer.tsx`'s actual behavior.
- `docs/frontend.md` already flags "the redline parser has a known
  mixed-change defect" — presumably in this same regex parser, since it's
  the one actually wired in. Worth a look during the port since this logic
  is being rewritten anyway, but not a scope expansion if it turns out to be
  more than a quick fix.
- There is no durable-review route: `reviewId` lives only in React state, so
  a refresh loses it and the completed review becomes unreachable.
- `backend/api.py` already mounts `static/` at `/` and `/static` and serves
  a hand-written marketing splash (`static/index.html`) with zero framework
  or build step — today it links out to
  `https://ai-recruiting-agent.vercel.app/` ("Try in browser") for the
  actual product. `backend/security.py`'s `/oauth2cb` route is a
  Chrome-extension-only OAuth bounce (`chromiumapp.org` forwarding); it's
  backend code, unrelated to this rewrite, and stays as-is for the frozen
  extension.
- `backend/config.py`'s `cors_origins` defaults to the Vercel domain plus
  `localhost:3000`/`127.0.0.1:3000` (the Next dev server ports), alongside
  the Chrome extension's origin assembled separately in `api.py`. Once the
  web client is served same-origin from the FastAPI app, none of the
  Vercel/Next-dev-port entries are needed.
- `google_web_client_id` (`backend/config.py`) is already a real **web**
  OAuth client ID — see
  `docs/authentication flow for chrome extension - deprecated.md`: the
  Chrome-extension-ID-to-client-ID binding never worked, which is why the
  `/oauth2cb` bounce hack exists. A Google web OAuth client supports
  multiple registered redirect URIs, so no new client ID is needed; the web
  flow just needs its own redirect URI(s) added in Google Cloud Console
  under this same client ID (Step 4).
- README's deploy story is already just PythonAnywhere: `pa website create
  --domain ...` / `pa website reload --domain ...` for an ASGI FastAPI app,
  and `uvicorn backend.api:app --reload --port 8000` for local dev. Serving
  the web client from the same app means this is still the entire deploy
  story — nothing new to stand up.

## Key decisions this plan makes

1. **Tag now; leave `BrowserExtension/` entirely untouched; build fresh in a
   new `web/` directory.** Cut a git tag (e.g.
   `chrome-extension-last-working`) before starting, satisfying the later
   Cleanup item's "preserve a tagged Git reference" concern immediately and
   cheaply. Because this plan no longer reuses any of `BrowserExtension/`'s
   code, there is nothing to incrementally strip `chrome.*` calls out of —
   the whole directory simply stops being built or deployed, and is left
   alone for the separate, later "Cleanup — Archive the frozen Chrome
   extension implementation" backlog item to physically delete/rename (that
   item already owns the directory rename and historical note; this plan
   doesn't need to duplicate or preempt that ceremony).
2. **New durable-review routes replace `/panel`.** `web/index.html` serves
   both the empty submission state and, via the browser's History API, a
   `/app/reviews/{review_id}` URL once a review exists — satisfying
   "restoration by durable review ID" through the URL itself. `/` (the
   existing marketing splash) is unchanged except its "Try in browser" CTA,
   which now points at `/app/` instead of the Vercel URL.
3. **Demo stays route-less**, per `docs/api.md`/`docs/frontend.md`: demo
   results render in the same page's local state, with no durable ID or URL
   change, since demo sessions are deliberately not persisted.
4. **The "page URL" field stops reading the active tab.** There's no
   `chrome.tabs` in a plain webapp regardless; per `docs/frontend.md`, "the
   web app does not and should not pretend to read another browser tab."
   It becomes a plain optional "source URL" text input, sent as
   `source_url` (already optional in `CreateReviewRequest`).
5. **Reuse the existing Google client ID; register a new redirect URI for
   it.** Since it's already a web client (see Current state above), no new
   client ID is needed. Register
   `https://airecruitingagent.pythonanywhere.com/app/auth-callback.html`
   (prod) and `http://127.0.0.1:8000/app/auth-callback.html` (local dev,
   since dev now also runs through FastAPI same-origin — see Step 5) as
   additional authorized redirect URIs in Google Cloud Console under that
   client ID. This is a manual console step, not a code change beyond
   renaming the misleadingly-named `CHROME_EXTENSION_CLIENT_ID` constant.
   (Live verification of the callback itself is still Increment 4's job;
   this is just correct configuration.)
6. **Same-origin fetch, no base-URL resolution.** Because `web/` is served
   by the same FastAPI app as `/api/v1`, every client-side call is a plain
   relative `fetch('/api/v1/...')` — no `BACKEND_URL` env injection, no
   `window.__BACKEND_URL__`, no local/cloud dev toggle, and (for the web
   origin) no CORS handling at all, since same-origin requests never go
   through a CORS check. `cors_origins` narrows to whatever the frozen
   Chrome extension still needs; see Step 4.
7. **No component framework, no bundler, no TypeScript build.** Split by
   plain JS module/file instead of framework component, per the backlog's
   "minimum component split" language read literally as "minimum
   decomposition," not "minimum React tree." Optional editor-only type
   hints (`// @ts-check` + JSDoc) are worth considering later but aren't
   assumed here, since adding a TypeScript *build* step would partially
   undo the point of this rewrite — flagged as a judgment call in Step 5,
   not decided unilaterally.
9. **A thin fetch helper, not a "typed client."** The original draft's
   "typed API client" (JSDoc type-mirrors of every request/response shape)
   was solving a TypeScript/React problem — nothing enforces those types
   without a compiler, so in plain JS it's ceremony, not integrity. What
   *is* worth sharing, regardless of framework: one place that attaches the
   auth header, sets the timeout, and parses the safe-error envelope, so
   those three things aren't reimplemented at each of the three live
   endpoints. Step 1 below is sized to that, not to a schema-mirroring
   layer.
10. **No separate client-side workflow-state enum.** The original draft had
   `workflow.js` maintain its own named state
   (`booting`/`demo_ready`/`signed_out`/.../`completed`/`error`) transitioned
   in lockstep with the fetched review. That's a second thing to keep in
   sync with the server for no real benefit: the review's own `status`
   field (`processing | awaiting_answers | completed | failed`, already
   `backend/review_store.py`'s enum) already says what to show once a
   review exists. Step 2 derives rendering directly from `review?.status`
   plus a few independent flags (authenticated, demo mode, loading, error)
   instead of inventing a parallel enum — durable state stays where it
   already lives, on the server.
8. **Prefer Python (Playwright's Python binding) for the smoke test over
   introducing Node/npm.** The rest of the project is already Python; a
   pure-Python smoke-test harness means the shipped product and its test
   tooling both have zero Node/npm dependency. Plain `node --test` remains
   an option for a handful of pure-logic JS unit tests (it ships with Node,
   needs no `package.json` or install step) — see Step 5.

## Step 1 — Add a shared fetch helper

Scope per backlog: centralize `/api/v1` requests, safe errors, authentication
headers, and timeouts. No event-stream parsing. (Not "schemas" — see
Decision 9: nothing enforces request/response shapes without a compiler, and
the backend already validates them before they reach the browser.)

New directory `web/js/`, kept deliberately small — roughly 30-40 lines for
`api.js`, not a schema-mirroring client layer:

- `api.js` — one `apiFetch(path, opts)` helper (`Authorization: Bearer
  <idToken>` injection, `AbortController`-based timeout — 150s for the two
  model calls, 30s elsewhere, matching today's budgets — and error parsing
  that reads the `{"error": {code, message, request_id, retryable}}`
  envelope), plus three one-line wrappers: `createReview(input)`,
  `getReview(reviewId)`, `submitAnswers(reviewId, qaPairs)`, all against
  relative `/api/v1/...` URLs (Decision 6). A one-line JSDoc comment per
  wrapper naming the shape it returns is enough documentation; no attempt to
  mirror `backend/schemas.py` field-by-field.
- `demo-api.js` — the non-`/api/v1` demo routes (`/review`, `/questions`,
  `/resume?demo=true`, `/jobdescription`), kept separate because they're not
  part of what this backlog item scopes and their response shapes
  (PascalCase `Fit`/`Gap_Map`/etc.) differ from `ReviewOut`.
- `auth.js` — token storage (`localStorage`), `login()` (redirect to
  Google, using the renamed client ID and `/app/auth-callback.html` as the
  redirect target — Decision 5), `logout()`, `getAuthToken()`,
  `checkUserAuthentication()`. Web-only; no Chrome API surface exists to
  remove (Decision 1).
- `web/auth-callback.html` — small standalone page: parse the OAuth
  fragment, verify `state`/nonce, store the token, redirect to `/app/`.
  Equivalent to today's `app/auth-callback/page.tsx`, minus the React
  wrapper.
- Optional pure-logic tests: `web/tests/api.test.mjs`,
  `web/tests/auth.test.mjs`, runnable via `node --test web/tests/*.test.mjs`
  with no `package.json` (see Step 5). Port the assertions already in
  `BrowserExtension/tests/api.test.mts` (token expiry, envelope unwrapping,
  401 clearing the token, error-message surfacing) rather than re-deriving
  them.

## Step 2 — Introduce explicit workflow state

Scope per backlog: separate durable server state, review workflow state, and
local editing state. Authentication must not be inferred from loaded resume
content.

`web/js/workflow.js` holds state and a `render()` step, but — per Decision
10 — it does not invent a separate named workflow-state enum to keep in
sync by hand. The review's own `status` field
(`processing | awaiting_answers | completed | failed`, the same enum
`backend/review_store.py` already uses) is what drives display once a
review exists:

- A module-level object holding exactly: `review` (the current `ReviewOut`,
  or `null` before one exists), `authenticated`, `demoMode`, `loading`, and
  `error`. Every mutation goes through one `setState(patch)` function,
  followed by one `render()` call that shows/hides the relevant `<section>`
  elements in `index.html` via a CSS class, switching on `review?.status`
  for the review-phase display and on `authenticated`/`demoMode` for the
  pre-review display (no virtual DOM diffing needed for a handful of
  sections).
- Authentication is tracked independently (from `auth.js`'s token
  presence/validity) and is never flipped based on whether a resume fetch
  happened to succeed. A 401 from any call signs out (clears the token, sets
  `authenticated = false`); a 403 sets a distinct "not authorized for this
  resource" flag that leaves `authenticated` untouched — this directly fixes
  today's conflation in `extension-panel.tsx` (`handleAuthError` inferring
  auth state from a message-string match, `setIsAuthorized(true)` tucked
  inside a resume-load success branch).
- Durable server state (the `ReviewOut` fields) lives in exactly one place —
  the `review` object above — not duplicated the way `review`, `reviewId`,
  and `tailoredMarkdown` are three separately-`useState`'d values kept in
  sync by hand today.
- Local editing state (unsent job-description text, unsent answers, redline
  accept/reject/edit overrides, copy feedback) is plain module-level
  variables in Step 3's files — explicitly not part of `workflow.js`, per
  the durable/workflow/local three-way split.

## Step 3 — Apply the minimum decomposition

Scope per backlog: extract only a review workspace, review display, and
redline editing. No resume-management piece yet (Increment 3.5). Split
further only when independently complex. Read here as "minimum file/module
decomposition," since there's no component framework (Decision 7).

- `web/js/review-workspace.js` — the orchestrator: wires `workflow.js` to
  the DOM, owns the job-description textarea and optional source-URL input,
  calls `api.js` on submit/answer actions, and calls into the two
  files below to render results. Supersedes `extension-panel.tsx`.
- `web/js/review-display.js` — a render function (or two) for fit score,
  rationale, gap-map cards, the Call-1 question form vs. Call-2 "tailored
  resume ready" notice — ported from `extension-panel.tsx`'s
  `TabsContent value="review"` block, same content/logic, now producing
  DOM nodes or an HTML string instead of JSX.
- `web/js/redline.js` — ports `resume-renderer.tsx`'s actual logic (not the
  unused `inline-redline*` files — see Current state): regex-parse the
  `<add>`/`<del>` markup into placeholder spans with `data-change-id`/
  `data-change-type` attributes, inject via `innerHTML`, and use **CSS
  `:hover`** (`.inline-change:hover .toolbar { display: flex }`) to reveal
  the accept/reject/edit toolbar instead of JS-tracked hover state — simpler
  than the React version, not just a port of it. Accept/reject/edit mutate
  the one source-of-truth markdown string via the same
  find-the-original-markup-substring-and-`.replace()` approach already used
  by `handleAcceptChange`/`handleRejectChange`/`handleEditChange` today,
  then re-render from the updated string.
- Do not create a resume-selection module, a generic tab-router abstraction
  beyond what `review-workspace.js` needs, or split `review-display.js`
  further (separate gap-map/fit-badge files) unless it turns out to need
  independent logic — per the backlog's explicit minimalism instruction.

## Step 4 — Build a deliberate full-page web product

Scope per backlog: remove Chrome-only controls and fixed side-panel
assumptions; add responsive review routes, accessible loading/error states,
restoration by durable review ID.

Frontend:

- `web/index.html` — one document containing all view states as
  `<section>` blocks (submission form, loading, review display, redline
  resume view), toggled by `workflow.js`. Normal responsive document flow
  (a centered max-width column), not the current
  `fixed right-0 top-0 h-full w-[500px] ... shadow-lg z-50` side-panel
  shell — there's no host page to float over anymore.
- `web/css/styles.css` — plain CSS (flexbox/grid), replacing Tailwind
  utility classes with real rules. `static/index.html`'s existing
  hand-written CSS is a reasonable style/tone reference.
- Client-side "routing" is deliberately minimal: on load, `main.js` checks
  `location.pathname` for `/app/reviews/{id}`; if present, calls
  `getReview(id)` (from `api.js`) to hydrate `workflow.js` (the restoration path
  the exit gate requires) and renders whatever state that review is in
  (`awaiting_answers` → question form; `completed` → tailored resume +
  redline). On a successful `createReview` in live mode, call
  `history.pushState(null, '', `/app/reviews/${result.id}`)` so the URL
  becomes bookmarkable/refreshable without a full page reload. Demo mode
  stays on `/app/` with no URL change (Decision 3).
- Accessible loading/error states: loading indicators get
  `role="status" aria-live="polite"`; error banners get `role="alert"`;
  move focus to a heading (`tabIndex="-1"` + `.focus()`) after restoring a
  review from a fresh page load, rather than leaving focus wherever the
  browser defaults it.
- Not in scope for this step (flagging so it isn't assumed done): making
  the redline accept/reject/edit interactions keyboard-operable — they're
  hover-driven today (per the in-app tooltip copy) and this backlog item
  doesn't name that gap. Real accessibility issue, candidate follow-up, not
  silently expanding this step.

Backend (small, additive; needed to actually serve `web/` from
PythonAnywhere — Decision 6 doesn't work without it):

- `backend/paths.py`: add `WEB_DIR = REPO_ROOT / "web"`.
- `backend/api.py`: mount it —
  `app.mount("/app", StaticFiles(directory=WEB_DIR, html=True), name="web")`
  (the existing `/static` mount for `static/` is untouched). `html=True`
  serves `index.html` automatically for `/app/`. Add one explicit route
  **registered before that mount** for the durable-ID path, since a static
  file mount alone 404s on a path with no matching file:
  ```python
  @app.get("/app/reviews/{review_id}", include_in_schema=False)
  def web_review_page(review_id: str):
      return FileResponse(WEB_DIR / "index.html")
  ```
  This is the standard "SPA fallback" pattern — same document, client-side
  JS reads the ID from the URL.
- `backend/config.py`: prune `cors_origins` — drop
  `https://ai-recruiting-agent.vercel.app` and the `:3000` Next-dev-server
  entries (dev now runs through FastAPI itself, same-origin — see Step 5).
  Keep only what the frozen Chrome extension origin still needs; that
  origin is already assembled separately in `api.py` from
  `chrome_extension_id` and is unaffected.
- `static/index.html`: change the "Try in browser" CTA from
  `https://ai-recruiting-agent.vercel.app/` to `/app/`.
- Google Cloud Console: register the two redirect URIs from Decision 5.

## Step 5 — Standardize the supported build (i.e., confirm there mostly isn't one)

Scope per backlog: one package manager/lockfile, no `latest` ranges,
non-interactive lint/typecheck, stop suppressing failures, add a
production-like browser smoke test. With no bundler or framework, most of
this is satisfied by absence rather than by a passing check:

- **Package manager / lockfile / dependency versions:** N/A — `web/` has no
  `package.json`. This is a stronger form of "one package manager and
  lockfile" (zero, rather than reconciling npm vs. pnpm as the original
  React-based draft of this plan had to).
- **Typecheck / lint:** no build step to run them in. Optional, not
  committed to here (Decision 7): `// @ts-check` + JSDoc types, checked
  on-demand via `npx tsc --noEmit` or just by an editor, with zero
  `package.json`/install footprint either way. Worth revisiting once the
  vanilla client exists and its real size is known, rather than deciding
  now whether it's worth the friction.
- **Build:** N/A — `web/` is served as-is; there is nothing to compile.
- **Tests:** optional pure-logic unit tests
  (`node --test web/tests/*.test.mjs`, from Step 1) need Node installed but
  no `package.json`, install step, or lockfile — Node ships `node --test`.
- **Smoke test:** a Python Playwright smoke test (`pip install playwright
  pytest-playwright`, added to a dev-only requirements file so it's not a
  runtime dependency of the deployed app) that starts `uvicorn
  backend.api:app` against a throwaway port and drives a real browser
  through `/app/`: submit the demo job description, see fit/gaps/questions
  render, submit answers, see the tailored resume + redline render — the
  full two-call demo path, needing no live credentials or provider call.
  This is "production-like" in that it exercises the actual served
  `web/` files through the actual FastAPI app, not a dev-only shortcut.
- **Document the one supported local workflow** (in `docs/frontend.md` or
  `README.md`): `uvicorn backend.api:app --reload --port 8000`, then browse
  to `http://127.0.0.1:8000/app/` — editing any `web/` file takes effect on
  next refresh, no build/watch process involved. Deploying is unchanged
  from today's `pa website reload --domain ...` once the code is pushed.

## Exit-gate verification checklist

- [ ] Start a live review at `/app/`, let Call 1 complete, note the resulting
      `/app/reviews/{id}` URL, hard-refresh: fit/gaps/questions reappear from
      `GET /api/v1/reviews/{id}`, not from memory.
- [ ] Submit answers, let Call 2 complete, hard-refresh again: the tailored
      resume and redline reappear the same way.
- [ ] The documented local workflow (`uvicorn ... --reload` +
      `node --test web/tests/*.test.mjs` + the Python Playwright smoke test)
      runs non-interactively with no install step beyond `pip install` for
      the smoke test.
- [ ] `grep -rn "chrome\." web/` returns nothing (there was never anything
      to remove — `web/` is written fresh).
- [ ] The whole app (marketing splash + `/app/` + `/api/v1`) is reachable
      from one PythonAnywhere-hosted origin, with no Vercel deploy involved.

## Explicitly out of scope for this plan

- Resume management, multiple stored resumes, active-resume selection —
  Increment 3.5 (stored resumes don't exist until then).
- SSE/WebSocket/event-stream parsing in the API client — explicitly
  excluded by the backlog item itself.
- Any Chrome extension work — job-description extraction, autofill,
  LinkedIn parsing. Per backlog's "Future decision — Reassess a thin
  browser-native extension," that's a later, separate decision; this plan
  deliberately doesn't introduce platform adapters or shared code in
  anticipation of it.
- Deleting `BrowserExtension/`'s files or renaming the directory — the
  separate later "Cleanup" backlog item, untouched by this plan (Decision 1).
- Live OAuth callback hardening (fail-closed on missing state/nonce),
  production SQLite/Groq/tracing validation — Increment 4.
- Keyboard-accessible redline accept/reject/edit interaction — noted above
  as a real gap but not named by this backlog item.
