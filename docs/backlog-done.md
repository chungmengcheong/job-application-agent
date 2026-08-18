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
with Increment 2's replacement of `/resume` by typed `/api/v1/resumes`
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

