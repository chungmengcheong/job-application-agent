"""Thin injectable client for an OpenAI-compatible chat completion API.

The active provider, model, and reasoning/token behavior all come from
configuration, not code, so switching them is a config change. Today's
default configuration points at Groq's OpenAI-compatible endpoint; the
`openai` package is used here as a generic client, not because OpenAI is
the provider.
"""
import os

import httpx
from openai import OpenAI

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-120b"
DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=180.0, write=30.0, pool=60.0)
# Reasoning-capable models spend part of their completion budget "thinking"
# before answering the actual prompt; how much (or whether it can be turned
# off at all) varies by model, so this is configurable, not assumed.
DEFAULT_REASONING_EFFORT = "low"
DEFAULT_MAX_COMPLETION_TOKENS = 4096


class LLMClient:
    """Sends one prompt to the configured model and returns the raw text response."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        reasoning_effort: str | None = None,
        max_completion_tokens: int | None = None,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        client: OpenAI | None = None,
    ) -> None:
        self._model = model or os.getenv("LLM_MODEL") or DEFAULT_MODEL
        self._reasoning_effort = (
            reasoning_effort
            or os.getenv("LLM_REASONING_EFFORT")
            or DEFAULT_REASONING_EFFORT
        )
        self._max_completion_tokens = int(
            max_completion_tokens
            or os.getenv("LLM_MAX_COMPLETION_TOKENS")
            or DEFAULT_MAX_COMPLETION_TOKENS
        )

        if client is not None:
            self._client = client
            return

        proxy_url = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
        http_client = None
        if proxy_url:
            transport = httpx.HTTPTransport(proxy=proxy_url, retries=1)
            http_client = httpx.Client(transport=transport)

        self._client = OpenAI(
            api_key=api_key or os.getenv("LLM_API_KEY"),
            base_url=base_url or os.getenv("LLM_BASE_URL") or DEFAULT_BASE_URL,
            timeout=timeout,
            http_client=http_client,
        )

    @property
    def model(self) -> str:
        return self._model

    def complete(self, prompt: str) -> str:
        """Send one prompt and return the model's raw text response, stripped."""
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            reasoning_effort=self._reasoning_effort,
            max_completion_tokens=self._max_completion_tokens,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content.strip()
