"""Characterization and regression tests for the current FastAPI workflow."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from backend import api


def _extract_prompt_input(prompt: str) -> dict:
    """Read JSON embedded by the isolated test prompt template."""
    return json.loads(prompt.removeprefix("PROMPT\n").removesuffix("\nEND"))


def _assert_review_contract(body: dict) -> None:
    """Assert the current consumer-critical review response shape."""
    assert set(body) >= {"Fit", "Gap_Map", "Questions", "Tailored_Resume"}
    assert isinstance(body["Fit"]["score"], int)
    assert isinstance(body["Fit"]["rationale"], str)
    assert isinstance(body["Gap_Map"], list)
    assert isinstance(body["Questions"], list)
    assert isinstance(body["Tailored_Resume"], str)
    for gap in body["Gap_Map"]:
        assert set(gap) == {
            "JD Requirement/Keyword",
            "Present in Resume?",
            "Where/Evidence",
            "Gap handling",
        }


def test_health_contract(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}


def test_request_validation_contract(client: TestClient) -> None:
    response = client.post("/review", json={"job_description": "Missing URL"})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(error["loc"][-1] == "url" for error in detail)


def test_lifespan_initializes_isolated_demo_baseline(
    client: TestClient, isolated_paths: dict[str, Path]
) -> None:
    assert isolated_paths["resume_baseline_file"].read_text() == "DEMO RESUME"
    assert (
        isolated_paths["job_description_file"].read_text()
        == "DEMO JOB DESCRIPTION"
    )


def test_lifespan_removes_each_stale_file_independently(
    isolated_paths: dict[str, Path],
) -> None:
    isolated_paths["resume_revised_file"].write_text("STALE REVISED")
    isolated_paths["user_response_file"].write_text("STALE ANSWERS")
    isolated_paths["output_prior_file"].write_text("STALE PRIOR")
    isolated_paths["output_current_file"].unlink(missing_ok=True)

    async def run_lifespan() -> None:
        async with api.lifespan(api.app):
            pass

    asyncio.run(run_lifespan())

    assert not isolated_paths["resume_revised_file"].exists()
    assert not isolated_paths["user_response_file"].exists()
    assert not isolated_paths["output_prior_file"].exists()


def test_prompt_contains_only_required_state_when_optional_files_are_absent(
    isolated_paths: dict[str, Path],
) -> None:
    isolated_paths["resume_baseline_file"].write_text("BASELINE")
    isolated_paths["additional_experience_file"].unlink()

    prompt_input = _extract_prompt_input(api.create_review_prompt("TARGET JOB"))

    assert prompt_input == {
        "Job_Description": "TARGET JOB",
        "Resume": "BASELINE",
    }


def test_prompt_includes_additional_prior_and_answer_state(
    isolated_paths: dict[str, Path],
) -> None:
    isolated_paths["resume_baseline_file"].write_text("BASELINE")
    isolated_paths["output_current_file"].write_text(
        json.dumps(
            {
                "Fit": {"score": 6, "rationale": "Prior rationale"},
                "Gap_Map": [{"JD Requirement/Keyword": "Prior gap"}],
                "Tailored_Resume": "ignored by prompt builder",
            }
        )
    )
    isolated_paths["user_response_file"].write_text(
        json.dumps([{"question": "Question?", "answer": "Answer."}])
    )

    prompt_input = _extract_prompt_input(api.create_review_prompt("TARGET JOB"))

    assert prompt_input["Job_Description"] == "TARGET JOB"
    assert prompt_input["Resume"] == "BASELINE"
    assert prompt_input["Additional_Info"] == "ADDITIONAL EXPERIENCE"
    assert prompt_input["Fit"]["rationale"] == "Prior rationale"
    assert prompt_input["Gap_Map"][0]["JD Requirement/Keyword"] == "Prior gap"
    assert prompt_input["qa_pairs"][0]["answer"] == "Answer."
    assert "Tailored_Resume" not in prompt_input


def test_prompt_replaces_every_input_placeholder(
    isolated_paths: dict[str, Path],
) -> None:
    isolated_paths["resume_baseline_file"].write_text("BASELINE")
    isolated_paths["prompt_file"].write_text("{{INPUT}}\n{{INPUT}}")

    prompt = api.create_review_prompt("TARGET JOB")

    assert "{{INPUT}}" not in prompt
    assert prompt.count('"Job_Description": "TARGET JOB"') == 2


def test_job_description_endpoint_currently_returns_seeded_demo(
    client: TestClient,
) -> None:
    response = client.post(
        "/jobdescription",
        json={"url": "https://example.com/job", "demo": False},
    )

    assert response.status_code == 200
    assert response.json() == {"job_description": "DEMO JOB DESCRIPTION"}


def test_demo_review_is_deterministic_and_skips_llm(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_if_called(prompt: str) -> str:
        raise AssertionError("Demo mode must not call the LLM")

    monkeypatch.setattr(api, "prompt_llm", fail_if_called)
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
    _assert_review_contract(first.json())
    assert first.json()["Fit"]["score"] == 7


def test_demo_follow_up_is_deterministic_and_skips_llm(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_if_called(prompt: str) -> str:
        raise AssertionError("Demo mode must not call the LLM")

    monkeypatch.setattr(api, "prompt_llm", fail_if_called)
    response = client.post(
        "/questions",
        json={
            "qa_pairs": [{"question": "Question?", "answer": "Answer."}],
            "demo": True,
        },
    )

    assert response.status_code == 200
    _assert_review_contract(response.json())
    assert response.json()["Fit"]["score"] == 8


@pytest.mark.xfail(
    strict=True,
    reason="Known bug: demo resume load overwrites the shared live baseline.",
)
def test_demo_resume_load_does_not_mutate_live_baseline(
    client: TestClient, isolated_paths: dict[str, Path]
) -> None:
    isolated_paths["resume_baseline_file"].write_text("LIVE BASELINE")

    response = client.get("/resume", params={"command": "load", "demo": True})

    assert response.status_code == 200
    assert isolated_paths["resume_baseline_file"].read_text() == "LIVE BASELINE"


def test_live_review_parses_output_saves_plain_resume_and_returns_redline(
    client: TestClient,
    isolated_paths: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    isolated_paths["resume_baseline_file"].write_text("LIVE RESUME")
    llm_response = isolated_paths["llm_response"]
    monkeypatch.setattr(api, "prompt_llm", lambda prompt: json.dumps(llm_response))

    response = client.post(
        "/review",
        json={
            "job_description": "TARGET JOB",
            "url": "https://example.com/job",
            "demo": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    _assert_review_contract(body)
    assert body["Fit"] == llm_response["Fit"]
    assert body["Gap_Map"] == llm_response["Gap_Map"]
    assert body["Questions"] == llm_response["Questions"]
    assert "<add> improved</add>" in body["Tailored_Resume"]
    assert (
        isolated_paths["resume_revised_file"].read_text()
        == llm_response["Tailored_Resume"]
    )
    assert json.loads(isolated_paths["output_current_file"].read_text()) == llm_response


def test_live_review_rotates_prior_raw_response(
    client: TestClient,
    isolated_paths: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    isolated_paths["resume_baseline_file"].write_text("LIVE RESUME")
    isolated_paths["output_current_file"].write_text('{"previous": true}')
    monkeypatch.setattr(
        api, "prompt_llm", lambda prompt: json.dumps(isolated_paths["llm_response"])
    )

    response = client.post(
        "/review",
        json={
            "job_description": "TARGET JOB",
            "url": "https://example.com/job",
        },
    )

    assert response.status_code == 200
    assert json.loads(isolated_paths["output_prior_file"].read_text()) == {
        "previous": True
    }


def test_provider_exception_maps_to_bad_gateway(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        api, "prompt_llm", lambda prompt: (_ for _ in ()).throw(TimeoutError("slow"))
    )

    response = client.post(
        "/review",
        json={
            "job_description": "TARGET JOB",
            "url": "https://example.com/job",
        },
    )

    assert response.status_code == 502
    assert "OpenAI call failed" in response.json()["detail"]


def test_provider_exception_does_not_leak_internal_detail(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret_detail = "provider request included private-resume-text"
    monkeypatch.setattr(
        api,
        "prompt_llm",
        lambda prompt: (_ for _ in ()).throw(RuntimeError(secret_detail)),
    )

    response = client.post(
        "/review",
        json={
            "job_description": "TARGET JOB",
            "url": "https://example.com/job",
        },
    )

    assert response.status_code == 502
    assert secret_detail not in response.text


def test_invalid_llm_json_does_not_replace_prior_valid_state(
    client: TestClient,
    isolated_paths: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prior = json.dumps(isolated_paths["llm_response"])
    isolated_paths["output_current_file"].write_text(prior)
    monkeypatch.setattr(api, "prompt_llm", lambda prompt: "not-json")

    response = client.post(
        "/review",
        json={
            "job_description": "TARGET JOB",
            "url": "https://example.com/job",
        },
    )

    assert response.status_code >= 400
    assert isolated_paths["output_current_file"].read_text() == prior


def test_missing_tailored_resume_does_not_replace_prior_valid_state(
    client: TestClient,
    isolated_paths: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prior = json.dumps(isolated_paths["llm_response"])
    isolated_paths["output_current_file"].write_text(prior)
    monkeypatch.setattr(
        api,
        "prompt_llm",
        lambda prompt: json.dumps(
            {"Fit": {"score": 8, "rationale": "Incomplete response"}}
        ),
    )

    response = client.post(
        "/review",
        json={
            "job_description": "TARGET JOB",
            "url": "https://example.com/job",
        },
    )

    assert response.status_code >= 400
    assert isolated_paths["output_current_file"].read_text() == prior


def test_follow_up_uses_original_submitted_job_description(
    client: TestClient,
    isolated_paths: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    isolated_paths["resume_baseline_file"].write_text("LIVE RESUME")
    captured_inputs: list[dict] = []

    def capture_prompt(prompt: str) -> str:
        captured_inputs.append(_extract_prompt_input(prompt))
        return json.dumps(isolated_paths["llm_response"])

    monkeypatch.setattr(api, "prompt_llm", capture_prompt)
    first = client.post(
        "/review",
        json={
            "job_description": "ORIGINAL TARGET JOB",
            "url": "https://example.com/job",
        },
    )
    follow_up = client.post(
        "/questions",
        json={
            "qa_pairs": [{"question": "Question?", "answer": "Answer."}],
            "demo": False,
        },
    )

    assert first.status_code == 200
    assert follow_up.status_code == 200
    assert captured_inputs[-1]["Job_Description"] == "ORIGINAL TARGET JOB"
    assert captured_inputs[-1]["qa_pairs"][0]["answer"] == "Answer."


def test_resume_load_copies_user_resume_to_working_baseline(
    client: TestClient, isolated_paths: dict[str, Path]
) -> None:
    response = client.get(
        "/resume",
        params={"command": "load", "demo": False},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"resume": "LIVE RESUME"}
    assert isolated_paths["resume_baseline_file"].read_text() == "LIVE RESUME"


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


def test_protected_review_returns_401_when_authentication_fails(
    isolated_paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    def reject(creds=None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    monkeypatch.setattr(api, "verify_token", reject)
    with TestClient(api.app, raise_server_exceptions=False) as unauthenticated_client:
        response = unauthenticated_client.post(
            "/review",
            json={
                "job_description": "TARGET JOB",
                "url": "https://example.com/job",
            },
        )

    assert response.status_code == 401


def test_protected_review_returns_403_when_authorization_fails(
    isolated_paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(api, "verify_token", lambda creds=None: {"email": "no@example.com"})

    def forbid(claims):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized.",
        )

    monkeypatch.setattr(api, "check_authorized_user", forbid)
    with TestClient(api.app, raise_server_exceptions=False) as forbidden_client:
        response = forbidden_client.post(
            "/review",
            json={
                "job_description": "TARGET JOB",
                "url": "https://example.com/job",
            },
        )

    assert response.status_code == 403
