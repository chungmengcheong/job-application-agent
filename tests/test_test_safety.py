"""Tests for guarantees of the test harness itself."""

from __future__ import annotations

import pytest

from backend import api


def test_default_test_harness_blocks_paid_llm_calls() -> None:
    with pytest.raises(AssertionError, match="paid LLM calls are not allowed"):
        api.prompt_llm("This must never reach Groq.")
