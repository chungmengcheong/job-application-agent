"""Shared pytest configuration and isolated backend fixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend import api  # noqa: E402


VALID_CLAIMS = {
    "sub": "test-user-123",
    "email": "test@example.com",
    "email_verified": True,
    "name": "Test User",
}


@pytest.fixture(autouse=True)
def block_paid_llm_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make accidental live provider calls fail in the normal unit suite."""

    def blocked_prompt_llm(prompt: str) -> str:
        raise AssertionError(
            "Unit tests must mock prompt_llm; paid LLM calls are not allowed."
        )

    monkeypatch.setattr(api, "prompt_llm", blocked_prompt_llm)


@pytest.fixture
def isolated_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Redirect all mutable backend files to one test-owned directory."""
    temp_dir = tmp_path / "temp"
    user_dir = tmp_path / "user"
    demo_dir = tmp_path / "demo"
    prompt_dir = tmp_path / "prompts"
    for directory in (temp_dir, user_dir, demo_dir, prompt_dir):
        directory.mkdir()

    paths = {
        "temp_dir": temp_dir,
        "resume_file": user_dir / "resume.txt",
        "additional_experience_file": user_dir / "additional_candidate_info.txt",
        "call1_prompt_file": prompt_dir / "prompt_call1_analysis_GOLD.txt",
        "call2_prompt_file": prompt_dir / "prompt_call2_tailor_GOLD.txt",
        "resume_baseline_file": temp_dir / "resume_baseline.txt",
        "resume_revised_file": temp_dir / "resume_revised.txt",
        "user_response_file": temp_dir / "user_response.json",
        "output_prior_file": temp_dir / "LLM_response_prior.json",
        "output_current_file": temp_dir / "LLM_response_current.json",
        "job_description_file": temp_dir / "job_description.txt",
        "resume_demo_file": demo_dir / "resume_demo.txt",
        "job_description_demo_file": demo_dir / "job_description_demo.txt",
        "review_demo_file": demo_dir / "API_response_review_demo.json",
        "review_add_info_demo_file": demo_dir / "API_response_review_add_info_demo.json",
    }

    paths["resume_file"].write_text("LIVE RESUME", encoding="utf-8")
    paths["additional_experience_file"].write_text(
        "ADDITIONAL EXPERIENCE", encoding="utf-8"
    )
    paths["call1_prompt_file"].write_text("PROMPT\n{{INPUT}}\nEND", encoding="utf-8")
    paths["call2_prompt_file"].write_text("PROMPT\n{{INPUT}}\nEND", encoding="utf-8")
    paths["resume_demo_file"].write_text("DEMO RESUME", encoding="utf-8")
    paths["job_description_demo_file"].write_text(
        "DEMO JOB DESCRIPTION", encoding="utf-8"
    )

    gap_map = [
        {
            "JD Requirement/Keyword": "Leadership",
            "Present in Resume?": "Y",
            "Where/Evidence": "Led a team.",
            "Gap handling": "Retain evidence.",
        }
    ]
    live_response_call1 = {
        "Fit": {"score": 6, "rationale": "Solid experience; some gaps."},
        "Gap_Map": gap_map,
        "Questions": ["What else should I know about you and this job?"],
    }
    live_response_call2 = {
        "Fit": {"score": 8, "rationale": "Strong relevant experience."},
        "Gap_Map": gap_map,
        "Tailored_Resume": "LIVE RESUME improved",
    }
    demo_response_call1 = {
        **live_response_call1,
        "Fit": {"score": 7, "rationale": "Demo rationale."},
    }
    demo_response_call2 = {
        **live_response_call2,
        "Fit": {"score": 8, "rationale": "Updated demo rationale."},
        "Tailored_Resume": "DEMO RESUME improved",
    }
    paths["review_demo_file"].write_text(
        json.dumps(demo_response_call1), encoding="utf-8"
    )
    paths["review_add_info_demo_file"].write_text(
        json.dumps(demo_response_call2), encoding="utf-8"
    )
    paths["llm_response_call1"] = live_response_call1
    paths["llm_response_call2"] = live_response_call2

    monkeypatch.setattr(api, "TEMP_DIR", temp_dir)
    monkeypatch.setattr(api, "RESUME_FILE", paths["resume_file"])
    monkeypatch.setattr(
        api, "ADDITIONAL_EXPERIENCE_FILE", paths["additional_experience_file"]
    )
    monkeypatch.setattr(api, "PROMPT_CALL1_ANALYSIS_FILE", paths["call1_prompt_file"])
    monkeypatch.setattr(api, "PROMPT_CALL2_TAILOR_FILE", paths["call2_prompt_file"])
    monkeypatch.setattr(api, "RESUME_BASELINE_FILE", paths["resume_baseline_file"])
    monkeypatch.setattr(api, "RESUME_REVISED_FILE", paths["resume_revised_file"])
    monkeypatch.setattr(api, "USER_RESPONSE_FILE", paths["user_response_file"])
    monkeypatch.setattr(api, "OUTPUT_FROM_LLM_PRIOR_FILE", paths["output_prior_file"])
    monkeypatch.setattr(
        api, "OUTPUT_FROM_LLM_CURRENT_FILE", paths["output_current_file"]
    )
    monkeypatch.setattr(api, "JOB_DESCRIPTION_FILE", paths["job_description_file"])
    monkeypatch.setattr(api, "RESUME_DEMO_FILE", paths["resume_demo_file"])
    monkeypatch.setattr(
        api, "JOB_DESCRIPTION_DEMO_FILE", paths["job_description_demo_file"]
    )
    monkeypatch.setattr(api, "RESPONSE_REVIEW_DEMO_FILE", paths["review_demo_file"])
    monkeypatch.setattr(
        api,
        "RESPONSE_REVIEW_ADD_INFO_DEMO_FILE",
        paths["review_add_info_demo_file"],
    )

    return paths


@pytest.fixture
def client(
    isolated_paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> TestClient:
    """Return a deterministic authorized client with isolated backend state."""
    monkeypatch.setattr(api, "verify_token", lambda creds=None: VALID_CLAIMS)
    monkeypatch.setattr(api, "check_authorized_user", lambda claims: claims)
    with TestClient(api.app, raise_server_exceptions=False) as test_client:
        yield test_client
