"""Integration tests for the durable `/api/v1` review API."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from backend import api, api_v1
from backend.db import init_db
from backend.review_service import ReviewService
from backend.review_store import ReviewStore

CLAIMS_A = {"sub": "user-a", "email": "a@example.com", "email_verified": True}
CLAIMS_B = {"sub": "user-b", "email": "b@example.com", "email_verified": True}

CALL1_RESPONSE = (
    '{"Fit": {"score": 6, "rationale": "Solid."}, "Gap_Map": [], '
    '"Questions": ["What else?"]}'
)
CALL2_RESPONSE = (
    '{"Fit": {"score": 8, "rationale": "Better."}, "Gap_Map": [], '
    '"Tailored_Resume": "RESUME improved"}'
)


class FakeLLMClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)

    def complete(self, prompt: str) -> str:
        if not self._responses:
            raise AssertionError("FakeLLMClient ran out of queued responses")
        return self._responses.pop(0)


def _fake_verify_token(creds=None):
    token = getattr(creds, "credentials", None)
    if token == "user-a-token":
        return CLAIMS_A
    if token == "user-b-token":
        return CLAIMS_B
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")


@pytest.fixture
def make_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Callable[[list[str]], tuple[TestClient, ReviewStore]]:
    """Return a factory that wires api_v1 to an isolated store and a fake
    LLM client queued with the given responses."""

    monkeypatch.setattr(api_v1, "verify_token", _fake_verify_token)
    monkeypatch.setattr(api_v1, "check_authorized_user", lambda claims: claims)

    def _make(responses: list[str]) -> tuple[TestClient, ReviewStore]:
        db_path = tmp_path / "reviews.db"
        init_db(db_path)
        store = ReviewStore(db_path)
        service = ReviewService(store, FakeLLMClient(responses))
        monkeypatch.setattr(api_v1, "review_service", service)
        client = TestClient(api.app, raise_server_exceptions=False)
        return client, store

    return _make


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_create_review_requires_authentication(make_client) -> None:
    client, _ = make_client([])

    response = client.post(
        "/api/v1/reviews",
        json={"resume": "R", "job_description": "J"},
    )

    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "UNAUTHENTICATED"
    assert "request_id" in body["error"]
    assert body["error"]["retryable"] is False


def test_create_review_returns_awaiting_answers_with_call1_result(make_client) -> None:
    client, _ = make_client([CALL1_RESPONSE])

    response = client.post(
        "/api/v1/reviews",
        json={
            "resume": "RESUME",
            "job_description": "JOB",
            "source_url": "https://example.com/job",
        },
        headers=_auth("user-a-token"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "awaiting_answers"
    assert body["result"]["Fit"]["score"] == 6
    assert body["result"]["Questions"] == ["What else?"]
    assert body["safe_error_code"] is None
    assert body["id"].startswith("rev_")


def test_unexpected_exception_still_returns_the_safe_envelope(
    make_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Any bug in review_service must not fall through to a bare,
    envelope-less 500 (Starlette's default unhandled-exception response)."""
    client, _ = make_client([])

    def _explode(**kwargs):
        raise TypeError("simulated unexpected bug")

    monkeypatch.setattr(api_v1.review_service, "create_review", _explode)

    response = client.post(
        "/api/v1/reviews",
        json={"resume": "R", "job_description": "J"},
        headers=_auth("user-a-token"),
    )

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "INTERNAL"
    assert "request_id" in body["error"]


def test_create_review_validation_error_returns_envelope(make_client) -> None:
    client, _ = make_client([])

    response = client.post(
        "/api/v1/reviews",
        json={"resume": "RESUME"},  # missing job_description
        headers=_auth("user-a-token"),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_review_provider_failure_returns_502_and_persists_failed_row(
    make_client,
) -> None:
    client, store = make_client([])  # no queued response -> provider call fails

    response = client.post(
        "/api/v1/reviews",
        json={"resume": "RESUME", "job_description": "JOB"},
        headers=_auth("user-a-token"),
    )

    assert response.status_code == 502
    body = response.json()
    assert body["error"]["code"] == "MODEL_CALL_FAILED"
    assert body["error"]["retryable"] is True

    with_status_failed = [
        r for r in _all_records(store) if r.status == "failed"
    ]
    assert len(with_status_failed) == 1
    assert with_status_failed[0].safe_error_code == "MODEL_CALL_FAILED"


def test_get_review_returns_the_owners_review(make_client) -> None:
    client, _ = make_client([CALL1_RESPONSE])
    created = client.post(
        "/api/v1/reviews",
        json={"resume": "RESUME", "job_description": "JOB"},
        headers=_auth("user-a-token"),
    ).json()

    response = client.get(f"/api/v1/reviews/{created['id']}", headers=_auth("user-a-token"))

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_review_returns_not_found_for_other_owner(make_client) -> None:
    client, _ = make_client([CALL1_RESPONSE])
    created = client.post(
        "/api/v1/reviews",
        json={"resume": "RESUME", "job_description": "JOB"},
        headers=_auth("user-a-token"),
    ).json()

    response = client.get(f"/api/v1/reviews/{created['id']}", headers=_auth("user-b-token"))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_get_review_returns_not_found_for_missing_review(make_client) -> None:
    client, _ = make_client([])

    response = client.get("/api/v1/reviews/rev_missing", headers=_auth("user-a-token"))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_submit_answers_completes_review(make_client) -> None:
    client, _ = make_client([CALL1_RESPONSE, CALL2_RESPONSE])
    created = client.post(
        "/api/v1/reviews",
        json={"resume": "RESUME", "job_description": "JOB"},
        headers=_auth("user-a-token"),
    ).json()

    response = client.post(
        f"/api/v1/reviews/{created['id']}/answers",
        json={"qa_pairs": [{"question": "What else?", "answer": "More detail."}]},
        headers=_auth("user-a-token"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert "<add>" in body["result"]["Tailored_Resume"]


def test_submit_answers_rejects_review_not_awaiting_answers(make_client) -> None:
    client, _ = make_client([CALL1_RESPONSE, CALL2_RESPONSE])
    created = client.post(
        "/api/v1/reviews",
        json={"resume": "RESUME", "job_description": "JOB"},
        headers=_auth("user-a-token"),
    ).json()
    qa_body = {"qa_pairs": [{"question": "What else?", "answer": "More detail."}]}
    client.post(
        f"/api/v1/reviews/{created['id']}/answers", json=qa_body, headers=_auth("user-a-token")
    )

    response = client.post(
        f"/api/v1/reviews/{created['id']}/answers", json=qa_body, headers=_auth("user-a-token")
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REVIEW_NOT_AWAITING_ANSWERS"


def _all_records(store: ReviewStore):
    import sqlite3

    from backend.review_store import ReviewRecord

    with sqlite3.connect(store._db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM reviews").fetchall()
    return [ReviewRecord.from_row(row) for row in rows]
