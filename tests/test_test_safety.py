"""Tests for guarantees of the test harness itself."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from backend import api


def test_default_test_harness_blocks_paid_llm_calls() -> None:
    with pytest.raises(AssertionError, match="paid LLM calls are not allowed"):
        api.prompt_llm("This must never reach Groq.")


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


def test_debug_defaults_to_enabled_outside_production() -> None:
    environment = os.environ.copy()
    environment.pop("ENVIRONMENT", None)

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
