"""Characterization tests for the permanent canned demo and the one
operator-resume getter. The durable, authenticated live workflow now lives
under `/api/v1` — see tests/test_api_v1.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import api
from backend.schemas import AnalysisResult, ReviewResult


def _assert_gap_map_shape(gap_map: list[dict]) -> None:
    for gap in gap_map:
        assert set(gap) == {
            "JD Requirement/Keyword",
            "Present in Resume?",
            "Where/Evidence",
            "Gap handling",
        }


def _assert_call1_contract(body: dict) -> None:
    """Assert Call 1's fit/gaps/questions shape; no tailored resume yet."""
    assert set(body) >= {"Fit", "Gap_Map", "Questions"}
    assert "Tailored_Resume" not in body
    assert isinstance(body["Fit"]["score"], int)
    assert isinstance(body["Fit"]["rationale"], str)
    assert isinstance(body["Gap_Map"], list)
    assert isinstance(body["Questions"], list)
    _assert_gap_map_shape(body["Gap_Map"])


def _assert_call2_contract(body: dict) -> None:
    """Assert Call 2's revised fit/gaps/tailored-resume shape; no new questions."""
    assert set(body) >= {"Fit", "Gap_Map", "Tailored_Resume"}
    assert "Questions" not in body
    assert isinstance(body["Fit"]["score"], int)
    assert isinstance(body["Fit"]["rationale"], str)
    assert isinstance(body["Gap_Map"], list)
    assert isinstance(body["Tailored_Resume"], str)
    _assert_gap_map_shape(body["Gap_Map"])


def test_review_and_questions_use_distinct_call_schemas() -> None:
    """/review (canned Call 1 shape) and /questions (canned Call 2 shape)
    validate against distinct schemas."""
    routes_by_path = {route.path: route for route in api.app.routes}

    assert routes_by_path["/review"].response_model is AnalysisResult
    assert routes_by_path["/questions"].response_model is ReviewResult


def test_health_contract(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}


def test_request_validation_contract(client: TestClient) -> None:
    response = client.post("/review", json={"job_description": "Missing URL"})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(error["loc"][-1] == "url" for error in detail)


def test_job_description_demo_returns_seeded_fixture(client: TestClient) -> None:
    response = client.post(
        "/jobdescription",
        json={"url": "https://example.com/job", "demo": True},
    )

    assert response.status_code == 200
    assert response.json() == {"job_description": "DEMO JOB DESCRIPTION"}


def test_job_description_non_demo_is_inert(client: TestClient) -> None:
    """Real URL extraction is not implemented; the live client submits the
    job description directly to /api/v1/reviews and never calls this route."""
    response = client.post(
        "/jobdescription",
        json={"url": "https://example.com/job", "demo": False},
    )

    assert response.status_code == 200
    assert response.json() == {"job_description": ""}


def test_demo_review_is_deterministic(client: TestClient) -> None:
    payload = {
        "job_description": "ignored demo input",
        "url": "https://example.com/demo",
        "demo": True,
    }

    first = client.post("/review", json=payload)
    second = client.post("/review", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    _assert_call1_contract(first.json())
    assert first.json()["Fit"]["score"] == 7


def test_demo_follow_up_is_deterministic(client: TestClient) -> None:
    response = client.post(
        "/questions",
        json={
            "qa_pairs": [{"question": "Question?", "answer": "Answer."}],
            "demo": True,
        },
    )

    assert response.status_code == 200
    _assert_call2_contract(response.json())
    assert response.json()["Fit"]["score"] == 8


def test_demo_resume_returns_demo_fixture_without_touching_live_resume_file(
    client: TestClient, isolated_paths: dict[str, Path]
) -> None:
    isolated_paths["resume_file"].write_text("LIVE RESUME")

    response = client.get("/resume", params={"command": "load", "demo": True})

    assert response.status_code == 200
    assert response.json() == {"resume": "DEMO RESUME"}
    assert isolated_paths["resume_file"].read_text() == "LIVE RESUME"


def test_resume_load_returns_the_operator_resume_text(
    client: TestClient, isolated_paths: dict[str, Path]
) -> None:
    response = client.get(
        "/resume",
        params={"command": "load", "demo": False},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"resume": "LIVE RESUME"}


@pytest.mark.xfail(
    strict=True,
    reason="Planned API contract: invalid commands should use an HTTP error.",
)
def test_invalid_resume_command_returns_client_error(client: TestClient) -> None:
    response = client.get(
        "/resume",
        params={"command": "delete", "demo": False},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 400
