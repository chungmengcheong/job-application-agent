"""Tests for the thin injectable, config-driven LLM client."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend import llm_client as llm_client_module
from backend.config import settings
from backend.llm_client import DEFAULT_BASE_URL, DEFAULT_MAX_COMPLETION_TOKENS, LLMClient


class FakeCompletions:
    def __init__(self, content: str) -> None:
        self._content = content
        self.calls: list[dict] = []

    def create(self, **kwargs) -> SimpleNamespace:
        self.calls.append(kwargs)
        message = SimpleNamespace(content=self._content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeSdkClient:
    def __init__(self, content: str = '{"ok": true}') -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions(content))


class RecordingOpenAIConstructor:
    """Stands in for the `OpenAI` class import inside llm_client.py."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(self, **kwargs) -> FakeSdkClient:
        self.calls.append(kwargs)
        return FakeSdkClient()


@pytest.fixture(autouse=True)
def isolate_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never let these tests pick up the developer's real LLM/proxy config.

    `llm_model`/`llm_reasoning_effort`/`llm_api_key` come from the `settings`
    singleton (fixed at process start), so isolating them means patching the
    singleton's attributes rather than the environment.
    """
    for var in ("LLM_BASE_URL", "LLM_MAX_COMPLETION_TOKENS", "HTTPS_PROXY", "HTTP_PROXY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_model", "qwen/qwen3.6-27b")
    monkeypatch.setattr(settings, "llm_reasoning_effort", "none")


def test_complete_sends_configured_parameters_and_strips_output() -> None:
    fake_sdk_client = FakeSdkClient(content='  {"ok": true}  ')
    client = LLMClient(model="test-model", client=fake_sdk_client)

    result = client.complete("PROMPT")

    assert result == '{"ok": true}'
    call = fake_sdk_client.chat.completions.calls[0]
    assert call["model"] == "test-model"
    assert call["messages"] == [{"role": "user", "content": "PROMPT"}]
    assert call["reasoning_effort"] == settings.llm_reasoning_effort
    assert call["max_completion_tokens"] == DEFAULT_MAX_COMPLETION_TOKENS
    assert call["response_format"] == {"type": "json_object"}


def test_model_defaults_when_no_override_given() -> None:
    client = LLMClient(client=FakeSdkClient())

    assert client.model == settings.llm_model


def test_model_falls_back_to_settings_when_no_override_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_model", "configured-model")

    client = LLMClient(client=FakeSdkClient())

    assert client.model == "configured-model"


def test_explicit_model_overrides_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_model", "configured-model")

    client = LLMClient(model="explicit-model", client=FakeSdkClient())

    assert client.model == "explicit-model"


def test_reasoning_effort_comes_from_settings_and_max_tokens_from_env_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "llm_reasoning_effort", "high")
    monkeypatch.setenv("LLM_MAX_COMPLETION_TOKENS", "2048")
    fake_sdk_client = FakeSdkClient()

    LLMClient(client=fake_sdk_client).complete("PROMPT")

    call = fake_sdk_client.chat.completions.calls[0]
    assert call["reasoning_effort"] == "high"
    assert call["max_completion_tokens"] == 2048


def test_configures_proxy_transport_when_https_proxy_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recording_constructor = RecordingOpenAIConstructor()
    monkeypatch.setattr(llm_client_module, "OpenAI", recording_constructor)
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:3128")
    monkeypatch.setattr(settings, "llm_api_key", "test-key")

    LLMClient()

    assert len(recording_constructor.calls) == 1
    call = recording_constructor.calls[0]
    assert call["api_key"] == "test-key"
    assert call["base_url"] == DEFAULT_BASE_URL
    assert call["http_client"] is not None


def test_does_not_build_a_proxy_transport_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recording_constructor = RecordingOpenAIConstructor()
    monkeypatch.setattr(llm_client_module, "OpenAI", recording_constructor)
    monkeypatch.setattr(settings, "llm_api_key", "test-key")

    LLMClient()

    call = recording_constructor.calls[0]
    assert call["http_client"] is None


def test_base_url_can_be_overridden_to_target_a_different_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recording_constructor = RecordingOpenAIConstructor()
    monkeypatch.setattr(llm_client_module, "OpenAI", recording_constructor)
    monkeypatch.setenv("LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setattr(settings, "llm_api_key", "test-key")

    LLMClient()

    assert recording_constructor.calls[0]["base_url"] == "https://api.openai.com/v1"
