"""Effective credentials: UI-saved values win, `credential/.env` (process env) is the fallback."""
import os
from dataclasses import dataclass

from . import secrets_store

# provider -> (protocol, base_url, default model)
PRESETS: dict[str, tuple[str, str, str]] = {
    "openrouter": ("openai", "https://openrouter.ai/api/v1", "anthropic/claude-haiku-5.5"),
    "anthropic": ("anthropic", "https://api.anthropic.com", "claude-haiku-5-5"),
}
PROTOCOLS = ("openai", "anthropic")


@dataclass
class LlmConfig:
    provider: str  # openrouter | anthropic | custom
    protocol: str  # openai | anthropic
    base_url: str
    api_key: str
    model: str
    auth: str  # oauth | manual | env
    origin: str  # ui | env


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def apify_token() -> tuple[str | None, str]:
    saved = secrets_store.get("apify")
    if saved and saved.get("token"):
        return saved["token"], "ui"
    if _env("APIFY_TOKEN"):
        return _env("APIFY_TOKEN"), "env"
    return None, "none"


def llm_config() -> LlmConfig | None:
    saved = secrets_store.get("llm")
    if saved and saved.get("api_key"):
        return LlmConfig(**saved, origin="ui")
    key = _env("LLM_API_KEY")
    if not key:
        return None
    protocol = _env("LLM_PROTOCOL") or "anthropic"
    base_url = _env("LLM_BASE_URL") or PRESETS["anthropic" if protocol == "anthropic" else "openrouter"][1]
    if "openrouter.ai" in base_url:
        provider = "openrouter"
    elif "api.anthropic.com" in base_url:
        provider = "anthropic"
    else:
        provider = "custom"
    return LlmConfig(provider, protocol, base_url, key, _env("LLM_MODEL"), "env", "env")


def mask(secret: str) -> str:
    return "••••" + secret[-4:] if len(secret) > 8 else "••••"
