"""Shared pytest configuration and isolated backend fixtures."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Point every ReviewStore built during this test session at a throwaway
# database, not the real repo's data/reviews.db. Must happen before backend.api
# (which imports backend.api_v1, which constructs a module-level ReviewStore)
# is ever imported.
_TEST_DB_DIR = tempfile.mkdtemp(prefix="reviews-test-db-")
os.environ["REVIEWS_DB_PATH"] = str(Path(_TEST_DB_DIR) / "reviews.db")

from backend import api, api_v1  # noqa: E402


VALID_CLAIMS = {
    "sub": "test-user-123",
    "email": "test@example.com",
    "email_verified": True,
    "name": "Test User",
}


@pytest.fixture(autouse=True)
def block_paid_llm_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make an accidental live provider call fail in the normal unit suite.

    Only guards the one real `LLMClient` instance the app wires up by
    default (`backend.api_v1.review_service`'s). Tests that need a fake
    provider response replace `api_v1.review_service` outright (see
    tests/test_api_v1.py), which makes this guard moot for them; tests of
    `LLMClient` itself (tests/test_llm_client.py) construct their own
    instances against an injected fake SDK client and never go through here.
    """

    def blocked_complete(prompt: str) -> str:
        raise AssertionError(
            "Unit tests must inject a fake LLMClient; paid LLM calls are not allowed."
        )

    monkeypatch.setattr(api_v1.review_service._llm_client, "complete", blocked_complete)


@pytest.fixture
def isolated_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Redirect the demo fixtures and the one operator resume file to one
    test-owned directory. The live workflow has no `temp/` dependency
    anymore, so there is nothing else left to isolate here."""
    user_dir = tmp_path / "user"
    demo_dir = tmp_path / "demo"
    for directory in (user_dir, demo_dir):
        directory.mkdir()

    paths = {
        "resume_file": user_dir / "resume.txt",
        "resume_demo_file": demo_dir / "resume_demo.txt",
        "job_description_demo_file": demo_dir / "job_description_demo.txt",
        "review_demo_file": demo_dir / "API_response_review_demo.json",
        "review_add_info_demo_file": demo_dir / "API_response_review_add_info_demo.json",
    }

    paths["resume_file"].write_text("LIVE RESUME", encoding="utf-8")
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
    demo_response_call1 = {
        "Fit": {"score": 7, "rationale": "Demo rationale."},
        "Gap_Map": gap_map,
        "Questions": ["What else should I know about you and this job?"],
    }
    demo_response_call2 = {
        "Fit": {"score": 8, "rationale": "Updated demo rationale."},
        "Gap_Map": gap_map,
        "Tailored_Resume": "DEMO RESUME improved",
    }
    paths["review_demo_file"].write_text(
        json.dumps(demo_response_call1), encoding="utf-8"
    )
    paths["review_add_info_demo_file"].write_text(
        json.dumps(demo_response_call2), encoding="utf-8"
    )

    monkeypatch.setattr(api, "RESUME_FILE", paths["resume_file"])
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
