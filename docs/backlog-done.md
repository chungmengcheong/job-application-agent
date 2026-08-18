# AI Recruiting Agent — Completed Backlog Items

Completed items are cut from [backlog.md](backlog.md) and pasted here verbatim,
in completion order, each tagged with the commit that landed it. This file is a
completion record, not a second source of truth: sequencing and exit gates for
remaining work stay in backlog.md.

## Increment 1 — Fix personal correctness and isolate the canned demo

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
