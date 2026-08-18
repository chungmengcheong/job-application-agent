# AI Recruiting Agent — Completed Backlog Items

Completed items are cut from [backlog.md](backlog.md) and pasted here verbatim,
in completion order, each tagged with the commit that landed it. This file is a
completion record, not a second source of truth: sequencing and exit gates for
remaining work stay in backlog.md.

## Increment 1 — Fix personal correctness and isolate the canned demo

Goal: Make the existing personal workflow trustworthy before restructuring it.
Preserve the current LLM workflow in this increment.

### Preserve the submitted job description through follow-up

**Confirmed.** `/review` does not save its job description, while `/questions`
rereads the demo-seeded global file. Bind the follow-up to the original submitted
job description and working resume.

gates_release_type: personal

Landed: `/review` now writes the submitted job description to `JOB_DESCRIPTION_FILE`
before generating the prompt, so `/questions` reads the same value back. Fixed
`tests/test_api.py::test_follow_up_uses_original_submitted_job_description`
(previously a strict xfail).

### Fix startup cleanup semantics

**Confirmed.** One missing temp file stops deletion of later files. Remove files
independently as an interim correction.

gates_release_type: personal

Landed: lifespan startup now calls `Path.unlink(missing_ok=True)` on each stale
temp file independently instead of one `try`/`except` around sequential
`os.remove` calls. Fixed
`tests/test_api.py::test_lifespan_removes_each_stale_file_independently`
(previously a strict xfail).

### Disable production debug behavior and sanitize errors

**Confirmed.** FastAPI uses `debug=True`, and provider exception text can reach
clients. Add environment-specific debug configuration and stable safe errors.

gates_release_type: personal

Landed: added an `ENVIRONMENT` env var (default `development`); `FastAPI(debug=...)`
is now `False` only when `ENVIRONMENT=production`. The `/review` provider-exception
handler no longer interpolates the raw exception into the client-facing detail
message. README's PythonAnywhere deployment steps and `.env.production` now
document/set `ENVIRONMENT=production`. Fixed
`tests/test_api.py::test_provider_exception_does_not_leak_internal_detail`
(previously a strict xfail); added
`tests/test_test_safety.py::test_debug_is_disabled_when_environment_is_production`
and `::test_debug_defaults_to_enabled_outside_production`.

### Enforce verified email before allowlist authorization

**Confirmed.** Discovered while working Increment 1: `check_authorized_user`
ran the `ALLOWED_EMAILS`/`ALLOWED_DOMAINS` allowlist check before checking
`email_verified`, so an allowlisted-but-unverified email claim was accepted
instead of rejected. Not in the original backlog item list; added here as a
personal-gating security correctness fix alongside the debug/error-sanitization
item above.

gates_release_type: personal

Landed: `check_authorized_user` now checks for a present, verified email first
and raises 401 before any allowlist check runs. Fixed
`tests/test_security.py::test_authorization_rejects_allowlisted_but_unverified_email`
(previously a strict xfail).

### Add the minimum typed review schemas

Add Pydantic contracts for the current fit, gaps, questions, tailored resume,
and safe error responses. Do not introduce schemas for future streaming events,
artifact versions, or a three-stage workflow.

gates_release_type: personal

Landed: `backend/schemas.py` adds `Fit`, `GapItem`, `ReviewResult` (the shared
fit/gaps/questions/tailored-resume shape), and `SafeError`. Not yet wired into
routes — that lands with the next two items (validating LLM output before
mutating state, and aligning demo/live responses through the same schema).
Added `tests/test_schemas.py`, which validates both checked-in demo fixtures
against `ReviewResult` and asserts round-trip and rejection behavior.

### Validate LLM output before changing state

**Confirmed.** Parse and validate the complete provider result before rotating
or replacing prior valid artifacts. Add bounded repair or safe failure for
invalid JSON and missing required fields.

gates_release_type: personal

Landed: `generate_review` now parses and validates the raw provider response
against `ReviewResult` before rotating `OUTPUT_FROM_LLM_CURRENT_FILE` or
writing `RESUME_REVISED_FILE`. Invalid JSON or a schema mismatch (e.g. a
missing `Tailored_Resume`) raises a 502 and leaves all prior state untouched;
no bounded repair was added since a safe failure satisfies the item and keeps
scope minimal. The response body is now built from the validated model via
`model_dump(by_alias=True)` rather than the raw parsed dict. Fixed
`tests/test_api.py::test_invalid_llm_json_does_not_replace_prior_valid_state`
and `::test_missing_tailored_resume_does_not_replace_prior_valid_state`
(previously strict xfails).

### Keep the canned demo but make it read-only and isolated

Retain the checked-in synthetic resume, job description, initial response, and
follow-up response. Demo calls make no LLM request, require no account, create no
session, and never read or write live `user/` or `temp/` workflow state.

gates_release_type: personal

Landed: `/resume?demo=true` now returns `RESUME_DEMO_FILE` directly instead of
copying it over the shared live baseline first. `/jobdescription` with
`demo=true` now reads `JOB_DESCRIPTION_DEMO_FILE` (a dedicated demo fixture)
instead of `JOB_DESCRIPTION_FILE`, which after the job-description follow-up
fix now holds whatever job description a live user last submitted. Fixed
`tests/test_api.py::test_demo_resume_load_does_not_mutate_live_baseline`
(previously a strict xfail); added
`::test_demo_job_description_never_reads_live_temp_state`.

### Align canned demo and live consumer contracts

Validate demo fixtures and mocked live responses against the same schemas and
frontend consumer assertions. Exact model wording need not match.

gates_release_type: personal

Landed: `/review` and `/questions` now declare `response_model=ReviewResult`,
so every response on either route — demo fixture or live/mocked LLM output —
is validated and serialized through the identical schema on every request,
not just checked once against a fixture snapshot. Added
`tests/test_api.py::test_review_and_questions_enforce_the_same_response_schema`.
`tests/test_schemas.py` (added under "Add the minimum typed review schemas"
above) already covers offline validation of both demo fixture files.

## Increment 1 exit gate — met

- A live review and follow-up use the same submitted job description and resume.
- Invalid model output leaves the prior valid state intact.
- Repeated demo calls cannot change live state and make no provider call.
- Production responses do not expose debug or provider exception details.

`tests/test_api.py::test_invalid_resume_command_returns_client_error` remains a
deliberate strict xfail: it is a "planned contract" item (an unhelpful
`/resume?command=delete` currently returns HTTP 200 with an `{"error": ...}`
body instead of a 4xx), not a "confirmed" defect, was never a named backlog
item, and is not part of the Increment 1 exit gate above. It fits naturally
with Increment 3.5's replacement of `/resume` by typed `/api/v1/resumes`
endpoints with one safe error envelope, so it is left for that increment
rather than patched piecemeal here.

## Increment 1.5 — Adopt the two-call Groq workflow

Goal: Make the user journey match the evidence-gathering logic and make Groq the
single supported provider.

### Baseline the current workflow

Capture representative output quality, token use, latency, and failure behavior
before changing prompts or provider configuration.

gates_release_type: personal

**Skipped by explicit user decision** (2026-08-18): proceed straight to the
Groq cutover without a baseline capture; see "Compare against the baseline"
below, also skipped.

### Introduce a thin injectable, config-driven LLM client

Switch the supported provider from OpenAI to Groq. Isolate provider syntax,
timeouts, model configuration, usage metadata, and raw response handling behind
one small client that tests can replace. Do not build a multi-provider adapter
framework.

Refined by explicit user decision (2026-08-18): make the client fully
config-driven rather than Groq-named, since Groq's chat completions API is
already OpenAI-schema-compatible — no per-vendor translation logic is needed.
`backend/llm_client.py`'s `LLMClient` wraps the generic `openai` SDK pointed at
a configurable `base_url` (default: Groq's OpenAI-compatible endpoint), with
model, reasoning effort, and max completion tokens all overridable via
`LLM_MODEL` / `LLM_REASONING_EFFORT` / `LLM_MAX_COMPLETION_TOKENS` env vars.
This is one call path, not per-vendor branching, so it does not count as the
multi-provider adapter framework this item still says not to build.

gates_release_type: personal

### Compare against the baseline

Confirm that the two-call flow does not materially reduce evidence fidelity,
truthfulness, fit quality, or resume coherence.

gates_release_type: personal

**Skipped by explicit user decision** (2026-08-18), alongside "Baseline the
current workflow" above.

### Implement Call 1: analysis and questions

Input the selected resume and job description. Return validated fit, gaps, and
targeted questions. Do not generate a tailored resume in Call 1.

gates_release_type: personal

Landed: `POST /review` now runs a dedicated Call 1 prompt
(`prompts/prompt_call1_analysis_GOLD.txt`) built by `create_call1_prompt()` and
validates the result against the new `AnalysisResult` schema (`Fit`, `Gap_Map`,
`Questions`). `Tailored_Resume` is not a field on that schema at all, so Call 1
cannot return one even if the model tries. The raw validated response is saved
to `OUTPUT_FROM_LLM_CURRENT_FILE` for Call 2 to read back.

### Implement Call 2: revised analysis and tailored resume

Input the same resume, the same job description, and the user's answers. Return
validated revised fit, revised gaps, and a tailored resume. Generate the redline
deterministically only after the complete resume validates.

gates_release_type: personal

Landed: `POST /questions` no longer delegates to `/review`'s handler. It builds
its own Call 2 prompt (`prompts/prompt_call2_tailor_GOLD.txt`, via
`create_call2_prompt()`) from the same resume baseline, the job description
Call 1 persisted to `JOB_DESCRIPTION_FILE`, Call 1's raw `Fit`/`Gap_Map` (read
back from `OUTPUT_FROM_LLM_CURRENT_FILE`), and the submitted `qa_pairs`, then
validates the result against `ReviewResult` (`Fit`, `Gap_Map`,
`Tailored_Resume`; no `Questions` field). The deterministic redline is
generated only after `Tailored_Resume` validates.

Refined by explicit user decision (2026-08-18): keep today's PascalCase field
names (`Fit`, `Gap_Map`, `Questions`, `Tailored_Resume`) on the split responses
rather than adopting the lowercase `fit`/`gaps`/`questions`/`tailored_resume`
example in docs/api.md's Increment 1.5 section. The snake_case rename now
belongs to the Increment 2/3 `/api/v1` typed client cutover, not this increment
— renaming twice was judged worse than renaming once at the right boundary.
docs/api.md has been updated to show the actual PascalCase contract.

### Update the web workflow and tests

Show fit, gaps, and questions after Call 1. Show revised fit, revised gaps, and
the tailored redline after Call 2. Test both calls with injected responses; the
normal suite makes no paid calls.

gates_release_type: personal

Landed: `ReviewData` (`extension-panel.tsx`) and `ReviewResponse` (`lib/api.ts`)
mark `Tailored_Resume` and `Questions` as optional, matching the two response
shapes. The review panel only renders the follow-up questions/answer form when
`Questions` is present (Call 1 state) and instead shows a "tailored resume is
ready" notice once `Tailored_Resume` arrives (Call 2 state); the Resume tab
already fell back to the plain baseline resume when no tailored resume exists
yet, so it needed no change. Backend tests inject fake `prompt_llm` responses
shaped for each call (`tests/test_api.py`, `tests/conftest.py`); the normal
suite still makes no paid calls. Demo fixtures were updated to the per-call
shapes: `demo/API_response_review_demo.json` has no `Tailored_Resume`,
`demo/API_response_review_add_info_demo.json` has no `Questions`.

## Increment 1.5 exit gate — met

- Call 1 (`POST /review`) returns only fit, gaps, and targeted questions.
- Call 2 (`POST /questions`) uses the original resume and job description plus
  answers and returns revised fit, revised gaps, and a tailored resume.
- The canned demo remains deterministic and makes no LLM call.

## Increment 2 — Introduce the Review service and durable API

Goal: Replace global workflow files with a durable `Review` record and a
minimal API, without yet introducing durable users or stored resumes. Owner
and resume are inline/denormalized for now; both grow a durable identity in
Increment 3.5.

Refined by explicit user decision (2026-08-18): drop the "additional
candidate info" file input (`user/additional_candidate_info.txt`) rather than
keep reading it server-side. The documented `POST /api/v1/reviews` request
body (`resume`, `job_description`, `source_url`) has no field for it, and
Increment 2 does not reintroduce a home for it; `ReviewService` reads only the
resume content and job description captured on the review itself.

### Add SQLite configuration for reviews

Create a `reviews` table with a development-safe initialization command. Do
not add `users` or `resumes` tables yet, and do not add foreign keys to them;
that schema work is Increment 3.5.

gates_release_type: personal

Landed: `backend/db.py` defines the `reviews` table (no `users`/`resumes`,
no foreign keys) and `init_db()`, which only ever runs `CREATE ... IF NOT
EXISTS` — safe to call on every process startup, never destroys data. The
path defaults to `data/reviews.db` (now gitignored) and is overridable via
`REVIEWS_DB_PATH`. `python -m backend.db` runs it standalone as the
development-safe initialization command. `backend/api.py`'s `lifespan` calls
it on startup in place of the old temp-file copy/cleanup it used to do.

### Make Review the durable unit of work

Persist owner (the verified Google `sub`, not yet a durable `users` row), the
submitted resume content, immutable job description, answers JSON, validated
result JSON, simple status, safe error, and timestamps. Use `processing |
awaiting_answers | completed | failed`.

gates_release_type: personal

Landed: `backend/review_store.py`'s `ReviewRecord`/`ReviewStore` persist
exactly this shape. `result_json`/`answers_json` transitions use `COALESCE`
against the existing column value, so a Call 2 failure records
`status="failed"` and a `safe_error_code` without erasing Call 1's already-
stored fit/gaps. Added `tests/test_review_store.py`.

### Add a thin ReviewService and SQLite store

FastAPI routes own HTTP concerns; `ReviewService` owns the two-call workflow;
one SQLite store module owns review persistence; the existing deterministic
redline function remains a function.

gates_release_type: personal

Landed: `backend/review_service.py`'s `ReviewService` builds each call's
prompt from the review's own stored `resume_content`/`job_description` (never
global files), validates provider output against the existing
`AnalysisResult`/`ReviewResult` schemas before persisting it, generates the
redline via the unchanged `redline_diff` only after Call 2's tailored resume
validates, and maps provider/validation failures to `backend/errors.py`'s
`ApiError` (`MODEL_CALL_FAILED` / `MODEL_INVALID_OUTPUT`, both 502,
retryable). Added `tests/test_review_service.py`, including assertions that
neither prompt contains an `Additional_Info` key.

### Implement the minimal JSON API

Add:

```text
POST   /api/v1/reviews
GET    /api/v1/reviews/{review_id}
POST   /api/v1/reviews/{review_id}/answers
```

`POST /api/v1/reviews` takes the resume content and job description directly;
there is no `resume_id` yet. `GET /api/v1/me` and `/api/v1/resumes/*` do not
exist until Increment 3.5 introduces users and stored resumes.

Use one safe typed error envelope.

gates_release_type: personal

Landed: `backend/api_v1.py` mounts a dedicated `FastAPI` sub-app at
`/api/v1` (`app.mount("/api/v1", api_v1_app)` in `backend/api.py`) with all
three routes, each authenticating via the existing `verify_token`/
`check_authorized_user` and scoping by the verified `sub`. `backend/errors.py`
registers the safe envelope (`{"error": {"code", "message", "request_id",
"retryable"}}`) only on this sub-app, so the legacy/demo routes' error shape
is untouched. A review that fails Call 1 or Call 2 returns an HTTP error
(404/409/422/502, matching today's failure-class precedent) rather than a 201
with a `failed` body; the row is still durably written first, so `GET
/api/v1/reviews/{review_id}` remains the recovery path if a client loses the
response. Missing and other-owner reviews return the same `NOT_FOUND` 404.
Added `tests/test_api_v1.py`, `tests/test_db.py`.

### Cut over without a compatibility facade

Switch the single supported web client to `/api/v1` in a coordinated change.
After verification, remove the old live endpoints and global workflow files.

gates_release_type: personal

Landed: `backend/api.py` dropped every `temp/`-scoped constant, the
lifespan temp-file copy/cleanup, and the live branches of `/review` and
`/questions` (auth, prompt building, LLM call). Those two routes, plus
`/resume` and `/jobdescription`, now serve only the permanent canned demo (and,
for `/resume`, a plain authenticated getter for the one operator resume's
text) — they are not a compatibility facade for the live workflow, since no
code path in them reaches an LLM or the reviews store. `BrowserExtension/lib/api.ts`'s
`postReview`/`postQuestions` branch on `demo`: the demo path is byte-for-byte
unchanged (still `/review`/`/questions`), and the live path now posts to
`/api/v1/reviews` / `/api/v1/reviews/{id}/answers` and unwraps the `{id,
status, result}` envelope back into the flat shape `extension-panel.tsx`
already expected, plus a new `reviewId`. This is intentionally the smallest
frontend change that makes the live path correct; the typed client that
formally replaces this ad hoc unwrapping is Increment 3.

Exit gate:

- Both calls use the immutable resume content and job description captured at
  review creation.
- A review and its follow-up are durable and recoverable by review ID.
- Review ownership is scoped by the verified Google `sub`, even though there is
  no durable `users` table yet.
- The supported live workflow has no `temp/` dependency.

## Increment 2 exit gate — met

- `create_review`/`submit_answers` (`ReviewService`) always read the
  `resume_content`/`job_description` captured on the `Review` row at
  creation, for both calls.
- `GET /api/v1/reviews/{review_id}` recovers a review and its answers by ID
  after the fact (`tests/test_api_v1.py`).
- Every `/api/v1` route scopes by `claims["sub"]`; missing and other-owner
  reviews both return `NOT_FOUND` 404.
- `backend/api.py` no longer references `temp/`; `lifespan` only calls
  `init_db()`.

