# AI Recruiting Agent — Refactoring Plan

This document records the project outcome and the cross-cutting safety rules
that still constrain implementation. Current structure and contracts live in
the focused documentation; sequencing and exit gates live only in
[backlog.md](backlog.md).

Supporting documentation:

- [docs/architecture.md](docs/architecture.md) — current and near-term architecture
- [docs/api.md](docs/api.md) — current and proposed backend contracts
- [docs/frontend.md](docs/frontend.md) — current web client and migration boundary
- [backlog.md](backlog.md) — ordered implementation increments

## Immediate outcome

Turn the current application into a reliable personal web app and a credible
portfolio project. The next possible horizon is a controlled beta for a handful
of invited users, but beta-only machinery should not shape the immediate
refactor unless it also improves current correctness, state ownership, or
testability.

Preserve the useful product core:

- compare a stored resume with a pasted job description;
- assess fit and gaps;
- ask targeted follow-up questions;
- use the answers to revise fit and gaps and produce a truthful tailored resume;
- generate deterministic redlines; and
- leave every proposed resume change under user control.

## Testing and safety rules

- Write the behavioral assertion before fixing each confirmed defect.
- Normal tests must block live provider calls unless a fake is explicitly
  injected.
- Validate complete model output before replacing the prior valid artifact.
- Keep every test's mutable filesystem or database isolated.
- Validate canned demo fixtures and mocked live responses through the same
  consumer schemas.
- Preserve strict known-defect tests until the fixing increment makes them pass.
- Run focused tests, the complete backend suite, any frontend logic tests,
  and the browser smoke test after each relevant increment. The web client
  has no compile or bundle step to typecheck or build.
- Production validation is required for Google OAuth, Groq, hosting, and SQLite
  persistence; mocks do not establish those boundaries.

Never log tokens, resumes, job descriptions, answers, raw prompts, or raw model
responses. Production tracing remains disabled until explicit content, access,
and retention controls exist.

## Explicit deferrals

Do not let these items shape the remaining minimum architecture:

- SSE or other browser-visible streaming;
- persisted demo sessions or demo continuity;
- a three-stage LLM workflow;
- multiple provider support;
- separate artifact and model-call tables;
- optimistic artifact or answer version checks;
- finalized-resume persistence and version checks;
- compatibility facades;
- Chrome extension implementation or shared platform adapters until the
  browser-native jobs are reassessed;
- advanced retry orchestration and operator failure inspection; and
- Postgres unless production SQLite validation fails.

## Implementation source of truth

[backlog.md](backlog.md) is the only source of truth for ordered
increments, release gates, and exit criteria. Architecture and contract
documents describe the current system and the next supported boundary; they do
not maintain duplicate phase plans.
