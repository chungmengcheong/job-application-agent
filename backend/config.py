"""Centralized application settings.

Operational defaults (model choice, reasoning effort, the public Google
OAuth/Chrome-extension identifiers) are committed here in source, since this
app has a single deployment target. Secrets and the authorized-user
allowlist have no default and are read only from the environment / `.env`
file - see `.env.example`.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


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

    # Google OAuth / Chrome extension identity - not secret (sent to the
    # browser / visible in the extension's own manifest), but named here
    # rather than duplicated as string literals across files.
    google_web_client_id: str = "258289407737-mdh4gleu91oug8f5g8jqkt75f62te9kv.apps.googleusercontent.com"
    chrome_extension_id: str = "oblgighcolckndbinadplmmmebjemido"

    # Authorized-user allowlist - no default; must come from .env.
    allowed_emails: str = ""
    allowed_domains: str = ""

    # Observability
    langsmith_api_key: str = ""

    @property
    def allowed_emails_set(self) -> set[str]:
        return _parse_comma_list(self.allowed_emails)

    @property
    def allowed_domains_set(self) -> set[str]:
        return _parse_comma_list(self.allowed_domains)


# Singleton instance
settings = Settings()
