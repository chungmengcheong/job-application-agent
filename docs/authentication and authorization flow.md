# Authentication and authorization flow

The supported system is a same-origin web application. FastAPI serves the
client at `/app/` and the protected API at `/api/v1`; the browser normally
sends relative requests to that same origin. Same-origin delivery removes the
frontend/backend CORS and deployment split, but it does not replace token
validation or resource authorization.

Code and [api.md](api.md) remain the detailed implementation sources; the
ordered work and validation gates are in [../backlog.md](../backlog.md).

## Configuration

- Google Console provides the Web OAuth client ID.
- The deployed web callback URI must be registered exactly.
- The client ID is public browser configuration; client secrets and provider
  API keys must not be committed.
- The backend uses `GOOGLE_WEB_CLIENT_ID` as the expected ID-token audience.
- `ALLOWED_EMAILS` and `ALLOWED_DOMAINS` restrict access during personal and
  invited-beta use.
- Production uses the same-origin API target. The development-only local API
  toggle is available only when `/app-config` explicitly permits it and is
  ignored in production.

## Browser authentication

The current browser flow is:

1. The user selects Log in. The client generates OAuth `state` and an OpenID
   Connect `nonce` and stores them in `sessionStorage` for that attempt.
2. The browser redirects to Google with `openid email profile` scopes and the
   same-origin callback URI `/app/auth-callback.html`.
3. Google returns an ID token and state to the callback document.
4. The callback validates the response and stores the browser credential. The
   current implementation stores it in `localStorage` with an expiry.
5. `api.js` sends the ID token as `Authorization: Bearer <ID_TOKEN>` on
   protected relative `/api/v1` requests.

The current implementation directly uses Google's implicit endpoint flow and
has a known fail-open edge case when expected callback state or nonce is
missing. Increment 4 must make missing state/nonce fail closed and replace or
explicitly justify the hand-built flow with Google Identity Services Sign in
with Google. It must also decide explicitly whether the browser credential
remains client-stored or is exchanged for a server session.

## Backend authentication and authorization

Every protected endpoint must authenticate and authorize the caller before
reading or writing resources:

1. Verify the ID-token signature, issuer, audience, and expiry.
2. Require an explicitly true `email_verified` claim before allowlist checks;
   an absent claim must not pass.
3. Apply the configured email/domain allowlist.
4. Resolve or create the internal user from the stable Google `sub`.
5. Scope every resume and review operation to that internal user.

Routes never accept a caller-selected `user_id`. Authentication establishes
identity; authorization establishes ownership. Missing and other-user
resources should return the same not-found result where the API contract calls
for it.

## Initial personal database identity

Increment 3.5 starts from a fresh database. Its bootstrap creates the personal
user with canonical email `ccmmail@gmail.com` and ports the single
`user/resume.txt` file into that user's stored resume. The seed must be
idempotent and must not invent a Google `sub`.

On the first verified login for that allowlisted email, the token's stable
Google `sub` is attached to the seeded user. Subsequent ownership uses `sub`,
not an email string; verified login may update the stored display/audit email.
No historical `users` or `reviews` are imported.

## Authenticated one-time trial

A visitor may enter a resume and job description before login. Those values
remain in browser memory; no provider call or sensitive persistence occurs
until the visitor authenticates and explicitly submits.

After submission, the normal authenticated flow resolves the internal user,
stores the submitted resume, creates an owned review with immutable inputs,
and runs the two-call workflow. The canned demo remains unauthenticated,
fixture-based, provider-free, and non-persistent.

## Required validation

- exact deployed callback registration;
- success, cancellation, state mismatch, nonce mismatch, missing expected
  state/nonce, expiry, and logout paths;
- explicitly verified and unverified email behavior;
- allowlisted and rejected users;
- first-login binding of `ccmmail@gmail.com` to the verified Google `sub`;
- owner-scoped resume and review access; and
- absence of tokens and sensitive user content from logs and error responses.
