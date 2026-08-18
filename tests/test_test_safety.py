"""Tests for guarantees of the test harness itself."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from backend import api, api_v1


def test_default_test_harness_blocks_paid_llm_calls() -> None:
    with pytest.raises(AssertionError, match="paid LLM calls are not allowed"):
        api_v1.review_service._llm_client.complete("This must never reach Groq.")


def test_explicit_production_tracing_setting_is_not_overridden() -> None:
    environment = os.environ.copy()
    environment["LANGSMITH_TRACING_V2"] = "false"

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os; import backend.api; "
                "assert os.environ['LANGSMITH_TRACING_V2'] == 'false'"
            ),
        ],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_debug_is_disabled_when_environment_is_production() -> None:
    environment = os.environ.copy()
    environment["ENVIRONMENT"] = "production"

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import backend.api as api; assert api.app.debug is False",
        ],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_debug_is_enabled_when_environment_is_not_production() -> None:
    # Set explicitly rather than relying on absence: backend.api unconditionally
    # loads the developer's real .env file, which may itself set ENVIRONMENT.
    environment = os.environ.copy()
    environment["ENVIRONMENT"] = "development"

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import backend.api as api; assert api.app.debug is True",
        ],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
