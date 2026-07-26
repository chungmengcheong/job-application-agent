# AI Recruiting Agent — Frontend Notes

This is a living record of the current frontend contract. The product UI is one
React panel, but it runs inside two different hosts whose capabilities and
authentication flows must remain explicit.

## Purpose

The frontend:

- loads a demo or stored resume;
- accepts a pasted job description;
- displays fit, gaps, and follow-up questions;
- displays an LLM-tailored resume as interactive redlines;
- copies the accepted/cleaned resume; and
- handles Google login for the extension and web app.

## Runtime surfaces

### Chrome extension

Manifest V3 defines a side panel at `panel.html`, a background service worker,
a content script on all URLs, Chrome identity/storage/tab permissions, and
backend/Google host permissions.

`npm run build-extension`:

1. runs the static Next.js export;
2. copies the export under `dist-extension/app/`;
3. rewrites root-relative asset paths in the exported `index.html`;
4. extracts inline scripts into `extension-init.js` for extension CSP;
5. injects the selected backend URL;
6. writes `dist-extension/panel.html`; and
7. updates the built manifest's resources and backend host permission.

The extension icon opens Chrome's side panel. Separately, the content script
contains an older iframe-panel path and listens for `openPanel`/`togglePanel`
messages, but the current background script does not send those messages.

### Web app

The Next.js app is configured with `output: "export"` and can be served as
static files. `/` renders marketing copy plus the panel; `/panel` renders the
panel alone; `/auth-callback` processes the OAuth fragment and returns to
`/panel`.

On the web, “current tab URL” is the web app's own URL. Users must paste the job
description; there is no page-reading implementation in either runtime.

## Input contract

The shared panel sends:

- `/jobdescription`: current URL and demo flag;
- `/resume`: `command=load` and demo flag;
- `/review`: pasted job description, current URL, and demo flag; and
- `/questions`: every generated question paired with the current answer,
  including empty answers.

The panel expects the backend contracts documented in [api.md](api.md).

## Output contract

The panel expects:

- a numeric `Fit.score` and string `Fit.rationale`;
- `Gap_Map` rows with four exact, human-readable keys;
- an array of question strings; and
- a `Tailored_Resume` string containing Markdown-like text and custom
  server-generated `<del>`/`<add>` markup.

Runtime validation is limited to console warnings. Any object response is set
as review state even if required fields are missing.

The resume renderer uses regular expressions to identify custom markup.
Accepted/rejected/edited changes modify the local string only; they are not
saved to the backend.

## Dataflow

```text
panel mounts
    |
    +--> inspect stored token
    +--> determine current URL
    +--> demo ON by default
    |       |
    |       +--> GET demo resume
    |       +--> POST for demo job description
    |
user pastes/edits job description
    |
    +--> demo automatically turns OFF
    |
login if needed
    |
    +--> load stored server resume
    |
submit review --> POST /review (150-second timeout)
    |
    +--> Review tab: fit, gaps, follow-up questions
    +--> Resume tab: interactive redline
    |
submit answers --> POST /questions (150-second timeout)
    |
    +--> replace review and resume state
```

## Authentication flows

### Extension

1. Generate state and nonce in memory.
2. Launch Google OAuth with `chrome.identity.launchWebAuthFlow`.
3. Google redirects to PythonAnywhere `/oauth2cb`.
4. The backend page forwards the URL fragment to the fixed extension's
   `chromiumapp.org` callback.
5. The extension validates state, extracts ID/access tokens, and saves them in
   `chrome.storage.local`.

The extension generates a nonce but does not validate the ID token's nonce in
client code. The backend's standard ID-token verifier validates signature,
issuer, audience, and expiry, but the submitted nonce is not supplied to it.

### Web

1. Generate state and nonce.
2. Save them in `sessionStorage`.
3. Redirect the browser to Google with
   `<web-origin>/auth-callback` as callback.
4. Parse tokens from the URL fragment on `/auth-callback`.
5. Compare returned state and decoded ID-token nonce when corresponding stored
   values exist.
6. Save tokens in `localStorage` and route to `/panel`.

The callback checks state/nonce only when a stored expected value exists; a
missing stored value does not fail closed. Live Google redirect registration
for the Vercel origin was not verified in this review.

For both clients, the ID token is the bearer credential sent to the backend.
The access token is stored but not used by current product calls. There is no
refresh-token flow; local expiry makes the user sign in again.

## Status model

The UI holds several independent booleans rather than one workflow state
machine:

- `isInitialLoading`
- `isLoadingResume`
- `isLoading`
- `isSubmittingQuestions`
- `isAuthenticated`
- `isAuthorized`
- `demoState`

The visible workflow is approximately:

```text
demo ready
   |
   +--> live unauthenticated --> authenticating --> authenticated/authorized
   |                                  |                    |
   |                                  +--> error           +--> resume loaded
   |
   +--> review loading --> review ready --> follow-up loading --> updated review
              |
              +--> error
```

Because the server does not expose a review ID or job status, a browser timeout
cannot be reconciled with backend completion.

## State ownership

| State | Web | Extension | Lifetime |
|---|---|---|---|
| ID/access tokens and expiry | `localStorage` | `chrome.storage.local` | Until logout/expiry/storage clear |
| OAuth state and nonce | `sessionStorage` | Function-local memory | One login attempt |
| Backend mode | `localStorage` | Browser storage plus in-page value | Persistent dev preference |
| Job description | React state | React state | Current page session |
| Review, questions, tailored resume | React state | React state | Current page/panel session |
| Accepted/rejected resume edits | React string | React string | Current page/panel session |
| Demo mode | React state, defaults on | React state, defaults on | Current page/panel session |
| Active job-page URL | Web app URL fallback | Chrome active tab URL | Current panel session |

No review content is restored after reload. No finalized resume edits are saved
server-side.

## Build and deployment contract

| Command | Intended result | Current caveat |
|---|---|---|
| `npm run dev` | Next.js dev server | Web surface only |
| `npm run build` | Static export in `out/` | TypeScript and ESLint build errors are explicitly ignored |
| `npm run build-extension` | Packaged extension in `dist-extension/` | Deletes/recreates the build directory and relies on HTML rewriting |
| `NEXT_PUBLIC_BACKEND_URL=... npm run build` | Web build against selected backend | Requires build-time environment configuration |
| `BACKEND_URL=... npm run build-extension` | Extension build against selected backend | Injected into generated `extension-init.js` |

`npm run lint` currently opens Next.js's interactive ESLint setup rather than
performing a non-interactive check because no ESLint configuration is present.
There is no frontend test suite.

## Current web gaps

- Web OAuth depends on a redirect URI derived from the deployed origin, while
  the client ID is hard-coded and current Google-console registration is
  unverified.
- The static web app and backend live at different origins, so correct
  `NEXT_PUBLIC_BACKEND_URL` and exact CORS configuration are required.
- The root page lays a fixed-width/fixed-position extension-style panel over
  web marketing content; `/panel` wraps the same component differently but the
  panel itself still carries extension-oriented layout behavior.
- Chrome-only concepts (active tab, local/cloud API toggle, extension close
  behavior) remain visible or embedded in the shared component.
- TypeScript and lint failures cannot currently block a production build.
- The checked-in extension content script and manual `panel.html` represent
  legacy/parallel paths that can drift from the actual side-panel package.

## Validation boundary

This document was derived from code and build configuration on 2026-07-25. It
does not claim that the Vercel deployment, Google web callback, installed
extension, responsive layout, or end-to-end login currently works.
