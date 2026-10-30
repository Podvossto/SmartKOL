"""One chat-completion call over either supported protocol (OpenAI-compatible or Anthropic)."""
import time
from dataclasses import dataclass

import httpx

from .clients import UpstreamError, _short
from .config import LlmConfig


@dataclass
class Completion:
    text: str
    model: str
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None  # only OpenRouter reports it


def complete(http: httpx.Client, cfg: LlmConfig, system: str, user: str, max_tokens: int = 1500) -> Completion:
    base = cfg.base_url.rstrip("/")
    started = time.perf_counter()
    if cfg.protocol == "anthropic":
        resp = http.post(
            f"{base}/v1/messages",
            headers={"x-api-key": cfg.api_key, "anthropic-version": "2023-06-01"},
            json={"model": cfg.model, "max_tokens": max_tokens, "system": system,
                  "messages": [{"role": "user", "content": user}]},
        )
    else:
        resp = http.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {cfg.api_key}"},
            json={"model": cfg.model, "max_tokens": max_tokens, "usage": {"include": True},
                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
        )
    latency_ms = round((time.perf_counter() - started) * 1000)
    if resp.is_error:
        raise UpstreamError(f"LLM provider error {resp.status_code}: {_short(resp)}")
    body = resp.json()
    usage = body.get("usage", {})
    if cfg.protocol == "anthropic":
        text = "".join(b.get("text", "") for b in body.get("content", []) if b.get("type") == "text")
        tokens, cost = (usage.get("input_tokens"), usage.get("output_tokens")), None
    else:
        text = body["choices"][0]["message"]["content"] or ""
        tokens, cost = (usage.get("prompt_tokens"), usage.get("completion_tokens")), usage.get("cost")
    return Completion(text.strip(), body.get("model", cfg.model), latency_ms, tokens[0], tokens[1], cost)
