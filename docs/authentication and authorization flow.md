# Authentication and authorization flow

This note distinguishes the supported web flow from the retired Chrome
extension flow. Code and [api.md](api.md) remain the current source of truth.
The original extension-specific note is preserved verbatim in
[authentication flow for chrome extension - deprecated.md](authentication%20flow%20for%20chrome%20extension%20-%20deprecated.md).

## Supported web flow

### Configuration

- Google Console provides a Web OAuth client ID.
- The deployed web callback URI must be registered exactly.
- The client ID is public configuration and may be committed; client secrets
  and provider API keys may not.
- The backend uses `GOOGLE_WEB_CLIENT_ID` as the expected ID-token audience.
- `ALLOWED_EMAILS` and `ALLOWED_DOMAINS` restrict access during personal and
  invited-beta use.

### Browser authentication

1. The web app generates OAuth `state` and an OpenID Connect `nonce`.
2. It stores the expected values for the login attempt in `sessionStorage`.
3. It redirects the browser to Google with `openid email profile` scopes and
   the registered web callback URI.
4. Google returns an ID token and state to the callback.
5. The callback must fail closed if expected state or nonce is absent or does
   not match.
6. The browser stores the current credential according to the supported web
   session design and sends the ID token as `Authorization: Bearer <ID_TOKEN>`.

The current implementation directly implements Google's implicit endpoint
flow, stores tokens in `localStorage`, and does not fail closed when an expected
state or nonce is missing. Because the app needs identity only and does not call
Google APIs for the user, Increment 4 should replace this with Google Identity
Services Sign in with Google unless a concrete requirement justifies retaining
the custom flow. Browser credential storage versus a server session is a
separate explicit decision, not an inherited default.

### Backend authentication and authorization

For every protected endpoint, one FastAPI dependency should:

1. verify the ID-token signature, issuer, audience, and expiry;
2. require an explicitly true verified-email claim before allowlist evaluation
   (the current `claims.get("email_verified", True)` is a confirmed fail-open
   defect);
3. apply the configured email/domain allowlist;
4. resolve or create the internal user from the stable Google `sub`; and
5. return a typed current user.

Authentication establishes identity. Authorization and owner-scoped storage
determine which resumes and reviews that identity may access. Routes never
accept a caller-selected `user_id`.

## Authenticated one-time trial

A visitor may enter a resume and job description before login, but those values
remain only in browser memory. The system makes no LLM call and persists no
sensitive input until the visitor authenticates and explicitly submits.

After submission:

1. resolve or create the internal user;
2. store the submitted resume as an owned active resume;
3. create an owned durable review with an immutable snapshot and job
   description; and
4. run the normal two-call Groq workflow.

The canned demo remains unauthenticated because it uses only server-owned fixed
fixtures and makes no provider call.

## Retired Chrome extension flow

Historically, the extension used a stable manifest key, a Web OAuth client, a
PythonAnywhere `/oauth2cb` bounce, and `chrome.identity.launchWebAuthFlow()` to
forward the fragment to the extension's `chromiumapp.org` callback. It stored
tokens in `chrome.storage.local`.

The implementation and `/oauth2cb` bounce have been removed from the active
tree and remain recoverable at Git tag `chrome-extension-last-working`:

- do not extend or modernize it;
- do not let its bounce callback or Chrome storage requirements shape the web
  authentication design; and
- a future thin extension should choose authentication from its actual
  browser-native requirements.

## Required validation

- exact deployed callback registration;
- success, cancellation, state mismatch, nonce mismatch, missing expected
  state/nonce, expiry, and logout paths;
- verified and unverified email behavior;
- allowlisted and rejected users;
- owner-scoped resume and review access; and
- absence of tokens and sensitive user content from logs and error responses.
