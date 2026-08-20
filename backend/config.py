"""Centralized application settings.

Operational defaults (model choice, reasoning effort, timeouts, the public
Google OAuth/Chrome-extension identifiers, CORS origins, tracing project)
are committed here in source, since this app has a single deployment
target. Secrets and the authorized-user allowlist have no default and are
read only from the environment / `.env` file - see `.env.example`.
"""
from pathlib import Path

import httpx
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.paths import DEFAULT_DB_PATH, REPO_ROOT


def _parse_comma_list(raw: str) -> set[str]:
    """Parse a comma-separated string into a lowercase set, tolerating
    surrounding whitespace/quotes on the full value and on each item."""
    cleaned = raw.strip().strip(' "\'')
    return {
        item
        for part in cleaned.split(",")
        if (item := part.strip().strip(' "\'').lower())
    }


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM (Groq's OpenAI-compatible endpoint by default; see llm_client.py)
    llm_api_key: str = ""
    llm_model: str = "qwen/qwen3.6-27b"
    # Reasoning-capable models spend part of their completion budget "thinking"
    # before answering the actual prompt; how much (or whether it can be turned
    # off at all) varies by model, so this is configurable, not assumed. Accepted
    # values are model-specific and do not overlap (qwen3: "none"/"default";
    # gpt-oss: "low"/"medium"/"high") - see docs/architecture.md for measurements.
    llm_reasoning_effort: str = "none"
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_max_completion_tokens: int = 4096
    llm_timeout_connect: float = 10.0
    llm_timeout_read: float = 180.0
    llm_timeout_write: float = 30.0
    llm_timeout_pool: float = 60.0
    # No default - only production (PythonAnywhere) needs a proxy; PythonAnywhere
    # requires outbound HTTP(S) calls to route through its own proxy, so a
    # PythonAnywhere .env should set:
    #   HTTPS_PROXY=http://proxy.server:3128
    #   HTTP_PROXY=http://proxy.server:3128
    https_proxy: str = ""
    http_proxy: str = ""

    # Google OAuth client identity - public browser configuration, not secret.
    google_web_client_id: str = "258289407737-mdh4gleu91oug8f5g8jqkt75f62te9kv.apps.googleusercontent.com"

    # Authorized-user allowlist - no default; must come from .env.
    allowed_emails: str = ""
    allowed_domains: str = ""

    # Deployment environment. Defaults to development so a missing variable
    # fails toward verbose local debugging rather than a silent production
    # misconfiguration.
    environment: str = "development"

    # Observability
    langsmith_api_key: str = ""
    langsmith_tracing_v2: bool = True
    langchain_project: str = "AIRecruitingAgent"

    # Reviews database
    reviews_db_path: Path = DEFAULT_DB_PATH

    @field_validator("environment", mode="after")
    @classmethod
    def _normalize_environment(cls, value: str) -> str:
        return value.strip().lower() or "development"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def llm_timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            connect=self.llm_timeout_connect,
            read=self.llm_timeout_read,
            write=self.llm_timeout_write,
            pool=self.llm_timeout_pool,
        )

    @property
    def allowed_emails_set(self) -> set[str]:
        return _parse_comma_list(self.allowed_emails)

    @property
    def allowed_domains_set(self) -> set[str]:
        return _parse_comma_list(self.allowed_domains)


# Singleton instance
settings = Settings()
