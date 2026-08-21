# Job Application Coach — Frontend Architecture

This is the current frontend source of truth. The supported client is a small
plain HTML/CSS/JS application under `web/`, served by the same FastAPI app as
`/api/v1`. The backend contracts remain in [api.md](api.md); implementation
order and exit gates remain in [../backlog.md](../backlog.md).

There is no frontend build step, framework runtime, separate frontend
deployment, or production cross-origin boundary. The development-only API
toggle is described below because it is explicitly disabled and ignored in
production.

## Client structure

```text
web/
    index.html                 one workspace document
    auth-callback.html         OAuth callback document
    css/styles.css             layout and presentation
    js/
        main.js                bootstrap and durable-review URL restoration
        workflow.js            shared render state and active-tab state
        review-workspace.js    DOM wiring and workflow orchestration
        api.js                 authenticated /api/v1 fetches
        demo-api.js            isolated canned-demo fetches
        auth.js                browser credential and login helpers
        backend-mode.js        development-only API target toggle
        review-display.js      fit, gap, and question rendering
        redline.js             local redline rendering and editing
    tests/*.test.mjs           pure-logic Node tests
```

FastAPI serves `/app/` and the explicit `/app/reviews/{review_id}` route. The
browser normally calls relative URLs, so the document and API share an origin.
In non-production, `/app-config` may explicitly enable a local API target at
`http://127.0.0.1:8000`; the selection is ignored and hidden in production,
including when stale local storage is present.

## Multi-tab workspace dataflow

“Tabs” means the four accessible panels inside one workspace document. They
are not browser tabs and do not own separate application state. `workflow.js`
keeps one `review` object and one `activeTab`; `review-workspace.js` renders
only the selected panel and derives labels and enabled controls from the
review stage.

```text
                              same-origin browser session
                                         |
 /app/ or /app/reviews/{id}  ->  main.js -> workflow.js
                                         |
                           review-workspace.js renders one active panel
                                         |
        +----------------+---------------+----------------+----------------+
        |                |                                |                |
 Job Description     Job fit                         Questions          Resume
 input / source      fit + gaps                       answers             baseline or
 URL; submit         actions                         -> Call 2             proposed
 -> Call 1           -> Questions                    -> revised            redline
                                                     Job fit
```

### Tab contract

| Panel | Initial state | Contents | Main transition or dataflow |
|---|---|---|---|
| Job Description | Active on a new workspace | Job-description input, optional source URL, and submit action. After review creation it becomes a read-only view. | Submit starts Call 1. Demo uses `POST /review`; live mode uses `POST /api/v1/reviews` with the stored `resume_id` after Increment 3.5. |
| Job fit | Disabled before a review exists; active after Call 1 | Fit score, rationale, gap map, and stage-appropriate actions. | Call 1 returns `awaiting_answers`, activates this panel, and enables the Questions panel. After Call 2 its label becomes `Revised Job Fit`. |
| Questions | Disabled before a review exists; enabled when questions are returned | Follow-up questions and unsent answer fields. | “Provide answers” selects this panel. Submit calls demo `POST /questions` or live `POST /api/v1/reviews/{review_id}/answers`, then returns to Revised Job Fit. |
| Resume | Available before and after review | The demo or stored baseline resume before completion; the proposed resume and redline controls after completion. | Before completion it is a baseline view. After a completed Call 2, “See proposed resume” selects it and displays the deterministic redline. |

The loading section temporarily replaces the workspace while a model call is
running. Errors appear in the shared error banner; a 401 clears the browser
credential and a 403 leaves authentication intact while reporting that the
resource is forbidden.

### End-to-end flows

#### New workspace

1. `main.js` initializes the backend-mode control and the review workspace.
2. Demo mode is on by default. The Job Description panel is active, its job
   description is prefilled from a fixed fixture, and the Resume panel can
   show the fixed demo resume. Job fit and Questions are disabled.
3. In live mode, the user logs in first. Until Increment 3.5, the workspace
   loads the single operator resume through the authenticated legacy
   `GET /resume`; Increment 3.5 replaces that with the user's stored resume.

#### Call 1 and tab transition

1. The user submits the Job Description panel.
2. The client enters loading state and sends the job description plus resume
   input to the appropriate demo or live endpoint.
3. The response becomes the single `review` state object. The client selects
   Job fit, renders fit/gaps, and enables Questions when follow-up questions
   exist. A live review pushes `/app/reviews/{review_id}` into browser history;
   demo mode does not change the URL or create a database record.

#### Call 2 and proposed resume

1. The user selects Questions, fills the local answer fields, and submits.
2. The client sends the question/answer pairs for the current review. The
   server reruns Call 2 from the immutable resume and job-description
   snapshot.
3. A completed review replaces the `review` object, changes the labels to
   Revised Job Fit and Proposed resume, selects Revised Job Fit, and enables
   the proposed-resume action.
4. Selecting Proposed resume renders the deterministic redline. Accept,
   reject, edit, redline visibility, and copy-clean-text changes remain local
   browser state; they do not create a server artifact version.

#### Refresh and direct review URL

Only a live review has a durable URL. On `/app/reviews/{review_id}`, `main.js`
sets live mode and loading state, calls `GET /api/v1/reviews/{review_id}`, and
hydrates the same tab workspace. It selects Job fit after restoration. The
review's server `status` (`processing | awaiting_answers | completed |
failed`) remains the source of truth for what the panels show. Demo results
are deliberately route-less and are not restored after refresh.

## State ownership

### Durable server state

The backend owns the authenticated user, stored resumes, review ID, immutable
resume/job-description snapshot, status, answers, validated result, and
timestamps. Increment 3.5 introduces the durable user and resume records from
a fresh database and removes the live dependency on `user/resume.txt`.

### Workflow state

`workflow.js` owns only the current review representation, authentication and
demo flags, loading/error flags, the active tab, and the distinct
`notAuthorized` flag. It does not maintain a second named workflow-state enum.
Once a review exists, display derives from the review's server status.

### Local UI state

`review-workspace.js` and `redline.js` own unsent job-description/source-URL
fields, unsent answers, redline accept/reject/edit overrides, redline
visibility, and copy feedback. These values are intentionally not treated as
durable review state.

## Request boundaries

`api.js` centralizes relative `/api/v1` requests, bearer headers, timeouts,
safe-error parsing, and 401 credential clearing. After Increment 3.5 its live
review creation call sends `resume_id`, not inline resume content.

`demo-api.js` remains separate because the permanent demo uses non-`/api/v1`
routes, fixed server fixtures, no authentication, no provider calls, and no
persistence. It returns the same consumer-level stages needed by the tabs but
uses the legacy PascalCase response shapes.

The supported system does not read another browser tab or active-page DOM. An
optional `source_url` is page context only. A browser-native extension is not
part of this frontend architecture; any future client must be reconsidered as
a separate backlog decision over the proven API.

## Redline behavior

`redline.js` parses the backend's deterministic `<add>`/`<del>` markup into
ordered segments and addresses changes by segment index. The controls are
keyboard-focusable buttons rendered inside each pending change. The clean-text
copy treats unresolved pending changes as accepted, while the current local
accept/reject/edit choices are preserved in the workspace until the page is
reloaded.

## Validation and release contract

The web client has no compile, bundle, lint, or package-install step:

- run pure-logic tests with `node --test web/tests/*.test.mjs`;
- run the production-like browser smoke test with
  `pytest tests/test_web_smoke.py`; and
- run locally with `uvicorn backend.api:app --reload --port 8000`, then open
  `http://127.0.0.1:8000/app/`.

The smoke test verifies the served demo two-call flow, tab transitions, and
durable-review-ID hydration with a seeded token and intercepted API response.
It does not verify deployed Google OAuth, responsive layout, or a live
provider-backed workflow; those remain Increment 4 validation work.
