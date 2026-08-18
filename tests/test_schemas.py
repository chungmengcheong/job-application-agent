"""Tests for the minimum typed review response schemas."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.schemas import AnalysisResult, ReviewResult

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = REPO_ROOT / "demo"


def test_analysis_result_validates_demo_review_fixture() -> None:
    data = json.loads((DEMO_DIR / "API_response_review_demo.json").read_text())

    result = AnalysisResult.model_validate(data)

    assert result.model_dump(by_alias=True) == data


def test_review_result_validates_demo_follow_up_fixture() -> None:
    data = json.loads(
        (DEMO_DIR / "API_response_review_add_info_demo.json").read_text()
    )

    result = ReviewResult.model_validate(data)

    assert result.model_dump(by_alias=True) == data


def test_analysis_result_round_trips_gap_map_keys() -> None:
    data = {
        "Fit": {"score": 7, "rationale": "Solid."},
        "Gap_Map": [
            {
                "JD Requirement/Keyword": "Leadership",
                "Present in Resume?": "Y",
                "Where/Evidence": "Led a team.",
                "Gap handling": "Retain evidence.",
            }
        ],
        "Questions": ["What else should I know about you and this job?"],
    }

    result = AnalysisResult.model_validate(data)

    assert result.model_dump(by_alias=True) == data


def test_analysis_result_rejects_missing_questions() -> None:
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(
            {
                "Fit": {"score": 8, "rationale": "..."},
                "Gap_Map": [],
            }
        )


def test_analysis_result_rejects_invalid_score_type() -> None:
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(
            {
                "Fit": {"score": "not a number", "rationale": "..."},
                "Gap_Map": [],
                "Questions": [],
            }
        )


def test_review_result_round_trips_gap_map_keys() -> None:
    data = {
        "Fit": {"score": 8, "rationale": "Even stronger now."},
        "Gap_Map": [
            {
                "JD Requirement/Keyword": "Leadership",
                "Present in Resume?": "Y",
                "Where/Evidence": "Led a team.",
                "Gap handling": "Retain evidence.",
            }
        ],
        "Tailored_Resume": "...",
    }

    result = ReviewResult.model_validate(data)

    assert result.model_dump(by_alias=True) == data


def test_review_result_rejects_missing_tailored_resume() -> None:
    with pytest.raises(ValidationError):
        ReviewResult.model_validate(
            {"Fit": {"score": 8, "rationale": "..."}, "Gap_Map": []}
        )


def test_review_result_rejects_invalid_score_type() -> None:
    with pytest.raises(ValidationError):
        ReviewResult.model_validate(
            {
                "Fit": {"score": "not a number", "rationale": "..."},
                "Gap_Map": [],
                "Tailored_Resume": "...",
            }
        )
