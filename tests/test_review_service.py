"""Tests for `ReviewService`'s two-call workflow, prompt construction, and
error mapping."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.errors import ApiError
from backend.review_service import ReviewService
from backend.review_store import ReviewStore
from backend.db import init_db


class FakeLLMClient:
    """Returns queued responses in order and records every prompt it saw."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self._responses:
            raise AssertionError("FakeLLMClient ran out of queued responses")
        return self._responses.pop(0)


def _extract_prompt_input(prompt: str) -> dict:
    return json.loads(prompt.removeprefix("PROMPT\n").removesuffix("\nEND"))


@pytest.fixture
def prompt_paths(tmp_path: Path) -> tuple[Path, Path]:
    call1 = tmp_path / "call1.txt"
    call2 = tmp_path / "call2.txt"
    call1.write_text("PROMPT\n{{INPUT}}\nEND")
    call2.write_text("PROMPT\n{{INPUT}}\nEND")
    return call1, call2


@pytest.fixture
def store(tmp_path: Path) -> ReviewStore:
    db_path = tmp_path / "reviews.db"
    init_db(db_path)
    return ReviewStore(db_path)


def _service(
    store: ReviewStore, responses: list[str], prompt_paths: tuple[Path, Path]
) -> tuple[ReviewService, FakeLLMClient]:
    fake_llm = FakeLLMClient(responses)
    call1_path, call2_path = prompt_paths
    service = ReviewService(
        store,
        fake_llm,
        call1_prompt_path=call1_path,
        call2_prompt_path=call2_path,
    )
    return service, fake_llm


CALL1_RESPONSE = json.dumps(
    {
        "Fit": {"score": 6, "rationale": "Solid experience."},
        "Gap_Map": [
            {
                "JD Requirement/Keyword": "Leadership",
                "Present in Resume?": "Y",
                "Where/Evidence": "Led a team.",
                "Gap handling": "Retain evidence.",
            }
        ],
        "Questions": ["What else should I know?"],
    }
)

CALL2_RESPONSE = json.dumps(
    {
        "Fit": {"score": 8, "rationale": "Even stronger."},
        "Gap_Map": [
            {
                "JD Requirement/Keyword": "Leadership",
                "Present in Resume?": "Y",
                "Where/Evidence": "Led a team.",
                "Gap handling": "Retain evidence.",
            }
        ],
        "Tailored_Resume": "RESUME improved",
    }
)


def test_create_review_stores_validated_result_and_awaits_answers(
    store: ReviewStore, prompt_paths: tuple[Path, Path]
) -> None:
    service, _ = _service(store, [CALL1_RESPONSE], prompt_paths)

    record = service.create_review(
        owner="owner-1",
        resume_content="RESUME",
        job_description="JOB",
        source_url="https://example.com/job",
    )

    assert record.status == "awaiting_answers"
    assert record.result_json["Fit"]["score"] == 6
    assert record.result_json["Questions"] == ["What else should I know?"]


def test_create_review_prompt_contains_only_job_description_and_resume(
    store: ReviewStore, prompt_paths: tuple[Path, Path]
) -> None:
    service, fake_llm = _service(store, [CALL1_RESPONSE], prompt_paths)

    service.create_review(
        owner="owner-1", resume_content="RESUME", job_description="JOB", source_url=None
    )

    prompt_input = _extract_prompt_input(fake_llm.prompts[0])
    assert prompt_input == {"Job_Description": "JOB", "Resume": "RESUME"}
    assert "Additional_Info" not in prompt_input


def test_create_review_maps_provider_failure_to_api_error_and_marks_failed(
    store: ReviewStore, prompt_paths: tuple[Path, Path]
) -> None:
    fake_llm = FakeLLMClient([])  # no responses queued -> raises on first call
    call1_path, call2_path = prompt_paths
    service = ReviewService(store, fake_llm, call1_prompt_path=call1_path, call2_prompt_path=call2_path)

    with pytest.raises(ApiError) as error:
        service.create_review(
            owner="owner-1", resume_content="R", job_description="J", source_url=None
        )

    assert error.value.code == "MODEL_CALL_FAILED"
    assert error.value.status_code == 502
    assert error.value.retryable is True

    [record] = [r for r in _all_records(store)]
    assert record.status == "failed"
    assert record.safe_error_code == "MODEL_CALL_FAILED"


def test_create_review_maps_invalid_json_to_api_error(
    store: ReviewStore, prompt_paths: tuple[Path, Path]
) -> None:
    service, _ = _service(store, ["not json"], prompt_paths)

    with pytest.raises(ApiError) as error:
        service.create_review(
            owner="owner-1", resume_content="R", job_description="J", source_url=None
        )

    assert error.value.code == "MODEL_INVALID_OUTPUT"
    assert error.value.status_code == 502


def test_submit_answers_completes_review_with_redline_and_answers(
    store: ReviewStore, prompt_paths: tuple[Path, Path]
) -> None:
    service, fake_llm = _service(store, [CALL1_RESPONSE, CALL2_RESPONSE], prompt_paths)
    record = service.create_review(
        owner="owner-1", resume_content="RESUME", job_description="JOB", source_url=None
    )
    qa_pairs = [{"question": "Q?", "answer": "A."}]

    updated = service.submit_answers(review_id=record.id, owner="owner-1", qa_pairs=qa_pairs)

    assert updated.status == "completed"
    assert updated.answers_json == qa_pairs
    assert "<add>" in updated.result_json["Tailored_Resume"]
    assert updated.result_json["Fit"]["score"] == 8


def test_submit_answers_call2_prompt_carries_call1_fit_and_gap_map(
    store: ReviewStore, prompt_paths: tuple[Path, Path]
) -> None:
    service, fake_llm = _service(store, [CALL1_RESPONSE, CALL2_RESPONSE], prompt_paths)
    record = service.create_review(
        owner="owner-1", resume_content="RESUME", job_description="JOB", source_url=None
    )

    service.submit_answers(
        review_id=record.id, owner="owner-1", qa_pairs=[{"question": "Q?", "answer": "A."}]
    )

    call2_input = _extract_prompt_input(fake_llm.prompts[1])
    assert call2_input["Fit"]["score"] == 6
    assert call2_input["qa_pairs"] == [{"question": "Q?", "answer": "A."}]
    assert "Additional_Info" not in call2_input


def test_submit_answers_can_rerun_after_completion(
    store: ReviewStore, prompt_paths: tuple[Path, Path]
) -> None:
    service, fake_llm = _service(store, [CALL1_RESPONSE, CALL2_RESPONSE, CALL2_RESPONSE], prompt_paths)
    record = service.create_review(
        owner="owner-1", resume_content="RESUME", job_description="JOB", source_url=None
    )

    service.submit_answers(
        review_id=record.id, owner="owner-1", qa_pairs=[{"question": "Q?", "answer": "A."}]
    )
    updated = service.submit_answers(
        review_id=record.id,
        owner="owner-1",
        qa_pairs=[{"question": "Q?", "answer": "Updated."}],
    )

    assert len(fake_llm.prompts) == 3
    assert updated.status == "completed"
    assert updated.answers_json == [{"question": "Q?", "answer": "Updated."}]


def test_submit_answers_rejects_review_not_awaiting_answers(
    store: ReviewStore, prompt_paths: tuple[Path, Path]
) -> None:
    service, _ = _service(store, [], prompt_paths)
    record = store.create(
        owner="owner-1", resume_content="R", job_description="J", source_url=None
    )  # still "processing"

    with pytest.raises(ApiError) as error:
        service.submit_answers(review_id=record.id, owner="owner-1", qa_pairs=[])

    assert error.value.code == "REVIEW_NOT_AWAITING_ANSWERS"
    assert error.value.status_code == 409


def test_submit_answers_missing_review_raises_not_found(
    store: ReviewStore, prompt_paths: tuple[Path, Path]
) -> None:
    service, _ = _service(store, [], prompt_paths)

    with pytest.raises(ApiError) as error:
        service.submit_answers(review_id="rev_missing", owner="owner-1", qa_pairs=[])

    assert error.value.code == "NOT_FOUND"
    assert error.value.status_code == 404


def test_submit_answers_other_owner_raises_not_found(
    store: ReviewStore, prompt_paths: tuple[Path, Path]
) -> None:
    service, _ = _service(store, [CALL1_RESPONSE], prompt_paths)
    record = service.create_review(
        owner="owner-1", resume_content="R", job_description="J", source_url=None
    )

    with pytest.raises(ApiError) as error:
        service.submit_answers(review_id=record.id, owner="owner-2", qa_pairs=[])

    assert error.value.code == "NOT_FOUND"


def test_submit_answers_failure_preserves_call1_result(
    store: ReviewStore, prompt_paths: tuple[Path, Path]
) -> None:
    service, _ = _service(store, [CALL1_RESPONSE, "not json"], prompt_paths)
    record = service.create_review(
        owner="owner-1", resume_content="R", job_description="J", source_url=None
    )

    with pytest.raises(ApiError):
        service.submit_answers(
            review_id=record.id, owner="owner-1", qa_pairs=[{"question": "Q?", "answer": "A."}]
        )

    updated = store.get(record.id)
    assert updated.status == "failed"
    assert updated.safe_error_code == "MODEL_INVALID_OUTPUT"
    assert updated.result_json["Questions"] == ["What else should I know?"]
    assert updated.answers_json == [{"question": "Q?", "answer": "A."}]


def test_get_review_missing_raises_not_found(
    store: ReviewStore, prompt_paths: tuple[Path, Path]
) -> None:
    service, _ = _service(store, [], prompt_paths)

    with pytest.raises(ApiError) as error:
        service.get_review(review_id="rev_missing", owner="owner-1")

    assert error.value.code == "NOT_FOUND"
    assert error.value.status_code == 404


def _all_records(store: ReviewStore):
    # No list-all method exists by design (owner-scoped access only); tests
    # that need the one row they just created look it up by re-querying the
    # store's own connection directly.
    import sqlite3

    with sqlite3.connect(store._db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM reviews").fetchall()
    from backend.review_store import ReviewRecord

    return [ReviewRecord.from_row(row) for row in rows]
