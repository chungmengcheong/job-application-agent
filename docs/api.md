# AI Recruiting Agent — Backend API Notes

This is a living record of the current FastAPI contract and workflow behavior.
It documents what callers can rely on today and highlights places where the
implementation does not yet meet the intended contract.

## Purpose

The backend serves the marketing page and demo assets, authenticates and
authorizes invited users, loads a stored resume, asks an LLM to review that
resume against a job description, creates deterministic resume redlines, and
reruns the review after follow-up answers.

Primary implementation:

- `backend/api.py` — routes, prompt assembly, file workflow, LLM call
- `backend/security.py` — Google token verification, allowlist, OAuth bounce
- `backend/redline.py` — token-level resume diff
- `prompts/prompt_resume_review_GOLD.txt` — LLM behavior and JSON schema

## Input contract

### Authentication

Protected live-mode calls send:

```http
Authorization: Bearer <Google ID token>
```

The backend verifies the token against `GOOGLE_WEB_CLIENT_ID`, then permits the
request when the verified email matches `ALLOWED_EMAILS` or its domain matches
`ALLOWED_DOMAINS`.

Demo branches run before authentication in `/review`, `/questions`, and
`/resume`, so those branches are public.

### `POST /jobdescription`

Authentication: none.

```json
{
  "url": "https://example.com/job",
  "demo": false
}
```

| Field | Type | Required | Current meaning |
|---|---|---:|---|
| `url` | string | yes | Accepted but not used to retrieve content |
| `demo` | boolean | no | Defaults to `false`; both values currently return the seeded demo job description |

### `POST /review`

Authentication: required when `demo` is `false`.

```json
{
  "job_description": "Full pasted job description",
  "url": "https://example.com/job",
  "demo": false
}
```

| Field | Type | Required | Current meaning |
|---|---|---:|---|
| `job_description` | string | yes | Injected into the review prompt |
| `url` | string | yes | Accepted for tracking but not persisted or logged structurally |
| `demo` | boolean | no | Returns a checked-in response fixture when `true` |

Before live review, the caller is implicitly expected to have loaded a resume
with `GET /resume?command=load`. The API does not enforce that sequence; if it
has not happened, the global working baseline may still be the demo resume.

### `POST /questions`

Authentication: required when `demo` is `false`.

```json
{
  "qa_pairs": [
    {
      "question": "What was the measurable outcome?",
      "answer": "Revenue increased 15%."
    }
  ],
  "demo": false
}
```

| Field | Type | Required | Current meaning |
|---|---|---:|---|
| `qa_pairs` | array of string-to-string objects | yes | Saved to the global `temp/user_response.json` file and added to the next prompt |
| `demo` | boolean | no | Returns a checked-in follow-up fixture when `true` |

The Pydantic type permits arbitrary string keys in each object; the practical
client convention is exactly `question` and `answer`.

### `GET /resume`

Authentication: required when `demo=false`.

Query parameters:

| Parameter | Type | Required | Current meaning |
|---|---|---:|---|
| `command` | string | yes | Only `load` succeeds |
| `demo` | boolean | no | Copies the demo resume into the global working baseline |

Example:

```http
GET /resume?command=load&demo=false
Authorization: Bearer <Google ID token>
```

### Other routes

| Route | Authentication | Purpose |
|---|---|---|
| `GET /` | none | Serve `static/index.html` |
| `GET /health` | none | Return a basic process heartbeat |
| `GET /oauth2cb` | none | Forward an OAuth URL fragment to the configured Chrome extension callback |
| `/static/*` | none | Serve checked-in static assets |
| `/docs`, `/redoc`, `/openapi.json` | none | FastAPI defaults; enabled by the current app configuration |

## Output contract

### Review response

Both `/review` and `/questions` return this practical shape:

```json
{
  "Fit": {
    "score": 7,
    "rationale": "Brief assessment and positioning recommendation."
  },
  "Gap_Map": [
    {
      "JD Requirement/Keyword": "Required capability",
      "Present in Resume?": "Partial",
      "Where/Evidence": "Evidence or absence in the source resume.",
      "Gap handling": "Rephrase, add truthful evidence, or omit."
    }
  ],
  "Questions": [
    "A material follow-up question?"
  ],
  "Tailored_Resume": "Resume text containing server-generated redline markup"
}
```

Important details:

- `Fit.score` is prompted as an integer from 1 through 10, but is not validated
  after generation.
- The prompt permits `Y`, `N`, or `Partial` for `Present in Resume?`; one
  frontend TypeScript interface narrows this incorrectly to `Y | N`.
- On a live response, `Tailored_Resume` is not the LLM's plain revised resume.
  The server replaces it with a diff against the working baseline:

```html
<span style="color:#c00000"><del>removed text</del></span>
<span style="color:#008000"><add>added text</add></span>
```

- Demo responses are returned directly from fixture JSON and are not normalized
  through the same parse/diff path.
- There is no declared FastAPI response model. Malformed or schema-drifting LLM
  JSON can therefore become a 500 error or a response the frontend only
  partially understands.

### Other responses

`POST /jobdescription`:

```json
{"job_description": "Demo job description text"}
```

`GET /resume?command=load`:

```json
{"resume": "Stored or demo resume text"}
```

Invalid resume command:

```json
{"error": "Invalid command"}
```

Missing credentials on non-demo `/resume` currently returns HTTP 200 with:

```json
{"error": "Authentication required to load resume."}
```

`GET /health`:

```json
{"message": "Hello World"}
```

### Error contract

| Condition | Current status | Body |
|---|---:|---|
| Request body/query validation fails | 422 | FastAPI validation detail |
| Missing or invalid ID token | 401 | `{"detail": "..."}` |
| Authenticated but not allowlisted | 403 | `{"detail": "..."}` |
| LLM SDK call raises | 502 | `{"detail": "generate_review: OpenAI call failed: ..."}` |
| Invalid LLM JSON or missing expected key | typically 500 | FastAPI debug-dependent server error |
| Invalid `/resume` command | 200 | `{"error": "Invalid command"}` |
| Missing `/resume` credentials | 200 | `{"error": "Authentication required..."}` |

The app is instantiated with `debug=True`, so unexpected production error
behavior may disclose more detail than intended.

## Dataflow

### Startup

1. Load `.env`.
2. Create global LLM and LangSmith clients.
3. Create `temp/`.
4. Copy `demo/resume_demo.txt` to `temp/resume_baseline.txt`.
5. Copy `demo/job_description_demo.txt` to `temp/job_description.txt`.
6. Attempt to remove current/prior LLM output, revised resume, and user answers.

The cleanup is wrapped in one `try` block. The first missing file stops the
remaining removals, so stale files later in the sequence can survive startup.

### Initial live review

1. Client calls `/resume?command=load`.
2. Backend authenticates and authorizes the caller.
3. Backend copies `user/resume.txt` to `temp/resume_baseline.txt`.
4. Client sends a pasted job description to `/review`.
5. Backend authenticates and authorizes the caller.
6. `create_review_prompt()` reads:
   - the request's job description;
   - the global working baseline resume;
   - optional `user/additional_candidate_info.txt`;
   - optional current LLM fit/gap output; and
   - optional global follow-up answers.
7. Backend injects that JSON into `prompt_resume_review_GOLD.txt`.
8. Backend makes one synchronous LLM request.
9. Backend rotates `LLM_response_current.json` to
   `LLM_response_prior.json`, then saves the new raw response.
10. Backend parses the response as JSON and reads `Tailored_Resume`.
11. Backend saves the plain revised resume and replaces the response field with
    a deterministic diff against the baseline.
12. Backend returns the review object.

### Follow-up review

1. Client posts every displayed question and its answer to `/questions`.
2. Backend authenticates and authorizes the caller.
3. Backend overwrites the global `temp/user_response.json`.
4. Backend constructs an internal `JobListing` using
   `temp/job_description.txt`.
5. `/questions` calls the `/review` function directly.
6. The second prompt includes prior `Fit`, prior `Gap_Map`, and `qa_pairs`.
7. The normal review save, rotation, diff, and response steps repeat.

Critical contract mismatch: `/review` does not save its request job description
to `temp/job_description.txt`. Therefore the follow-up flow currently uses the
startup-seeded demo job description rather than the user's pasted job
description.

### Demo flow

1. The panel starts with demo mode enabled.
2. It calls `/jobdescription` and `/resume` to load checked-in demo inputs.
3. `/resume?demo=true` also copies the demo resume into the shared working
   baseline.
4. `/review?demo=true` and `/questions?demo=true` return separate checked-in
   JSON fixtures without LLM calls.

The fixture outputs bypass the live response transformation, which allows demo
and live behavior to drift.

## Status model

There is no durable job/status entity. A review request is synchronous and has
only transport/UI state:

```text
idle
  |
  +-- submit --> loading --> succeeded
                         \-> failed
```

The frontend separately tracks:

- initial loading;
- resume loading;
- review loading;
- follow-up submission;
- authenticated/unauthenticated;
- authorized/forbidden; and
- demo/live mode.

The backend does not assign a review ID, request ID, idempotency key, lifecycle
status, or retry status. If the client times out, it cannot determine whether
the server or LLM completed. The API client does not retry `/review` or
`/questions`; it retries `/jobdescription` and `/resume` once.

## State ownership

### User-owned intent

| State | Owner | Location |
|---|---|---|
| Stored resume | Operator/user by filesystem convention | `user/resume.txt` |
| Additional experience | Operator/user by filesystem convention | `user/additional_candidate_info.txt` |
| Pasted job description | Browser until submitted | React component state |
| Follow-up answers before submit | Browser | React component state |

### Server-owned state

| State | Location | Scope in current implementation |
|---|---|---|
| Working baseline resume | `temp/resume_baseline.txt` | Entire backend process |
| Working job description | `temp/job_description.txt` | Entire backend process; demo-seeded |
| Follow-up answers | `temp/user_response.json` | Entire backend process |
| Current raw LLM response | `temp/LLM_response_current.json` | Entire backend process |
| Prior raw LLM response | `temp/LLM_response_prior.json` | Entire backend process |
| Revised plain resume | `temp/resume_revised.txt` | Entire backend process |
| Demo inputs and outputs | `demo/*` | Checked-in global fixtures |
| Prompt | `prompts/prompt_resume_review_GOLD.txt` | Checked-in global configuration |

Authentication establishes who may call the API; it does not scope any of
these files. This is the primary blocker to a limited multi-user beta.

### Browser-owned state

The web client keeps tokens and backend mode in `localStorage`; the extension
uses `chrome.storage.local`. Review content and question answers live only in
React memory and disappear on reload. See [frontend.md](frontend.md).

## Configuration

Environment variables read by the current backend:

| Variable | Purpose |
|---|---|
| `GROQ_API_KEY` | Current working-tree LLM provider |
| `OPENAI_API_KEY` | Historical/current-main provider; unused by the working-tree implementation |
| `LANGSMITH_API_KEY` | LangSmith client/tracing |
| `GOOGLE_WEB_CLIENT_ID` | ID-token audience |
| `ALLOWED_EMAILS` | Comma-separated invited email addresses |
| `ALLOWED_DOMAINS` | Comma-separated invited domains |
| `CHROME_EXTENSION_ID` | OAuth bounce destination |
| `HTTPS_PROXY` / `HTTP_PROXY` | PythonAnywhere outbound proxy configuration |

The code creates a custom `httpx.Client`, but does not pass it to the current
Groq client. The intended proxy behavior therefore needs live validation.

## Validation boundary

This contract was derived from static code and fixture inspection on
2026-07-25. Automated tests and build checks are recorded in
[backlog.md](backlog.md). No live identity, LLM, tracing, proxy, or deployment
call is asserted here.
