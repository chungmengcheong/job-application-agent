"""Tests for the durable `Review` record store."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.db import init_db
from backend.review_store import ReviewStore


@pytest.fixture
def store(tmp_path: Path) -> ReviewStore:
    db_path = tmp_path / "reviews.db"
    init_db(db_path)
    return ReviewStore(db_path)


def test_create_persists_a_processing_review(store: ReviewStore) -> None:
    record = store.create(
        owner="owner-1",
        resume_content="RESUME",
        job_description="JOB",
        source_url="https://example.com/job",
    )

    assert record.id.startswith("rev_")
    assert record.owner == "owner-1"
    assert record.resume_content == "RESUME"
    assert record.job_description == "JOB"
    assert record.source_url == "https://example.com/job"
    assert record.status == "processing"
    assert record.result_json is None
    assert record.answers_json is None
    assert record.safe_error_code is None
    assert record.completed_at is None


def test_create_allows_missing_source_url(store: ReviewStore) -> None:
    record = store.create(
        owner="owner-1", resume_content="R", job_description="J", source_url=None
    )

    assert record.source_url is None


def test_get_returns_none_for_missing_review(store: ReviewStore) -> None:
    assert store.get("rev_missing") is None


def test_get_for_owner_returns_none_for_other_owner(store: ReviewStore) -> None:
    record = store.create(
        owner="owner-1", resume_content="R", job_description="J", source_url=None
    )

    assert store.get_for_owner(record.id, "owner-2") is None
    assert store.get_for_owner(record.id, "owner-1") is not None


def test_get_for_owner_returns_none_for_missing_review(store: ReviewStore) -> None:
    assert store.get_for_owner("rev_missing", "owner-1") is None


def test_mark_awaiting_answers_stores_result_and_updates_status(store: ReviewStore) -> None:
    record = store.create(
        owner="owner-1", resume_content="R", job_description="J", source_url=None
    )
    result = {"Fit": {"score": 6, "rationale": "ok"}, "Gap_Map": [], "Questions": ["Q?"]}

    store.mark_awaiting_answers(record.id, result)

    updated = store.get(record.id)
    assert updated.status == "awaiting_answers"
    assert updated.result_json == result
    assert updated.completed_at is None


def test_mark_completed_stores_answers_and_result_and_completed_at(
    store: ReviewStore,
) -> None:
    record = store.create(
        owner="owner-1", resume_content="R", job_description="J", source_url=None
    )
    store.mark_awaiting_answers(
        record.id, {"Fit": {"score": 6, "rationale": "ok"}, "Gap_Map": [], "Questions": []}
    )
    result = {"Fit": {"score": 8, "rationale": "better"}, "Gap_Map": [], "Tailored_Resume": "..."}
    answers = [{"question": "Q?", "answer": "A."}]

    store.mark_completed(record.id, result, answers)

    updated = store.get(record.id)
    assert updated.status == "completed"
    assert updated.result_json == result
    assert updated.answers_json == answers
    assert updated.completed_at is not None


def test_mark_failed_records_safe_error_code_without_erasing_prior_result(
    store: ReviewStore,
) -> None:
    record = store.create(
        owner="owner-1", resume_content="R", job_description="J", source_url=None
    )
    call1_result = {
        "Fit": {"score": 6, "rationale": "ok"},
        "Gap_Map": [],
        "Questions": ["Q?"],
    }
    store.mark_awaiting_answers(record.id, call1_result)

    store.mark_failed(record.id, "MODEL_INVALID_OUTPUT", answers_json=[{"question": "Q?", "answer": "A."}])

    updated = store.get(record.id)
    assert updated.status == "failed"
    assert updated.safe_error_code == "MODEL_INVALID_OUTPUT"
    # Call 1's result must survive a Call 2 failure.
    assert updated.result_json == call1_result
    assert updated.answers_json == [{"question": "Q?", "answer": "A."}]


def test_mark_failed_on_first_call_leaves_result_null(store: ReviewStore) -> None:
    record = store.create(
        owner="owner-1", resume_content="R", job_description="J", source_url=None
    )

    store.mark_failed(record.id, "MODEL_CALL_FAILED")

    updated = store.get(record.id)
    assert updated.status == "failed"
    assert updated.result_json is None
