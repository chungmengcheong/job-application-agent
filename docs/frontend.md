# AI Recruiting Agent — Frontend Notes

This document records the current frontend and the supported web-only target.

## Current implementation

One large React panel currently runs in two hosts:

- a statically exported Next.js web app; and
- a Manifest V3 Chrome side-panel extension.

Chrome extension development and releases are frozen. Its code remains
temporarily because the web app and extension share `extension-panel.tsx` and
build source under `BrowserExtension/`. The extension build, OAuth behavior,
packaging, and installed-side-panel behavior are not current release gates.

The current panel:

- loads a canned demo or the single server resume;
- accepts a pasted job description;
- shows fit, gaps, questions, and a tailored resume;
- submits follow-up answers;
- renders custom server-generated redline markup; and
- stores accepted/rejected edits only in React state.

## Current web runtime

The Next.js app uses static export. `/` combines marketing content with the
panel, `/panel` renders the panel directly, and `/auth-callback` processes the
Google OAuth fragment.

Users paste the job description. The web app does not and should not pretend to
read another browser tab.

Current web authentication:

1. generate state and nonce;
2. store them in `sessionStorage`;
3. redirect to Google;
4. parse tokens from the callback fragment;
5. compare returned state and decoded nonce when stored expectations exist;
6. store tokens in `localStorage`; and
7. send the ID token as the API bearer credential.

The current callback does not fail closed when expected state or nonce is
missing. Live callback registration remains a production validation item.

## Frozen extension runtime

The repository still contains a side-panel manifest, background worker,
content-script/iframe legacy path, Chrome identity and storage code, and a
custom static-export packaging script.

Do not refactor these into shared platform adapters. After the supported web app
no longer depends on extension-only files:

- delete the manifest, worker, content script, Chrome OAuth/storage code,
  packaging scripts, generated extension artifacts, and extension-only tests;
- rename `BrowserExtension/` to a web-oriented directory in a contained change;
  and
- preserve a tagged Git reference and a short historical architecture note.

After the web workflow is reliable, reassess a new thin extension against three
browser-native jobs: extracting the active page's job description, assisting
with user-approved application-form completion, and inspecting relevant
networking context. Reuse the proven API and only the UI components that are
actually economical to share.

## Current dataflow

```text
panel mounts
    -> load canned demo fixtures by default

user exits demo and authenticates
    -> load one stored server resume

submit job description
    -> current combined provider call
    -> fit + gaps + questions + tailored redline

submit answers
    -> repeat combined provider call
    -> replace review and resume state
```

The browser holds several interacting booleans for loading, authentication,
authorization, submission, and demo/live mode. Review content and edits vanish
on refresh because there is no durable review ID.

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

## Increment 1.5 workflow

The supported live UI changes to:

```text
select active resume
paste job description
        |
        v
Call 1 loading
        |
        v
fit + gaps + targeted questions
        |
user submits answers
        |
        v
Call 2 loading
        |
        v
revised fit + revised gaps + tailored redline
```

Call 1 must not display or imply that a final tailored resume exists. Call 2
uses the original resume snapshot and job description plus the answers.

The browser waits for complete JSON responses. Do not add SSE or streamed-event
state. If synchronous requests later prove unreliable, durable review polling is
the first fallback.

## Supported web target

Use a deliberately small decomposition:

```text
web shell and routes
    |
    +-- typed API client
    +-- ReviewWorkspace + explicit workflow state
    +-- resume management and active selection
    +-- review/fit/gap/question display
    +-- existing redline display and local editing
```

Do not begin with a predicted hierarchy of feature folders or web/Chrome
platform interfaces. Extract further components only as independently complex
behavior emerges.

## State ownership

### Durable server state

- current authenticated user;
- stored resumes and active-resume selection;
- review ID, immutable inputs, status, answers, and validated result; and
- completed tailored resume and redline.

Refreshing the page refetches this state by ID.

### Workflow state

A reducer or equivalent explicit model should represent approximately:

```text
booting
demo_ready
signed_out
resume_required
ready
submitting_analysis
awaiting_answers
submitting_answers
completed
error
```

Authentication is a session fact, not something inferred from loaded resume
content.

### Local UI state

- unsent job description;
- unsent answers;
- active tab;
- redline visibility;
- locally accepted/rejected/edited changes; and
- copy feedback.

Finalized-resume persistence is deferred. Copy/download and local editing may
remain without creating additional server artifact versions.

## Typed client contract

Centralize:

- `/api/v1` URLs;
- bearer headers;
- request and response schemas;
- safe error codes;
- timeouts; and
- JSON parsing.

Do not add SSE parsing, reconnect logic, provider events, or Chrome storage
abstractions.

## Build and release contract

The supported web client must have:

- one package manager and lockfile;
- intentional dependency versions rather than `latest`;
- non-interactive tests, lint, and typecheck;
- no suppression of TypeScript or lint failures during builds;
- one documented production build; and
- a production-like browser smoke test.

The current extension build is frozen and may be removed after web separation.
A future extension would receive its own release contract if the browser-native
jobs justify resuming it.

## Current web gaps

- OAuth callback registration and failure behavior are not live-verified.
- Missing expected OAuth state or nonce does not fail closed.
- a fixed side-panel layout and Chrome-only concepts remain in shared code;
- TypeScript and lint failures do not reliably block builds;
- there is no durable review restoration;
- the redline parser has a known mixed-change defect; and
- multiple stored resumes and active selection do not yet exist.

## Validation boundary

Static code and configuration establish the current state model and build
shape. They do not prove deployed OAuth, responsive layout, durable restoration,
or the full two-call browser workflow.
