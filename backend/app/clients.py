"""Outbound calls used by Settings: Apify account check, LLM ping, OpenRouter OAuth exchange."""
import time

import httpx

from .config import LlmConfig

APIFY = "https://api.apify.com/v2"
OPENROUTER_KEYS = "https://openrouter.ai/api/v1/auth/keys"


class UpstreamError(Exception):
    """Safe-to-show message; never contains a credential."""


def _short(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        err = body.get("error", body)
        text = err.get("message", err) if isinstance(err, dict) else err
    except ValueError:
        text = resp.text
    return str(text)[:200]


def apify_account(http: httpx.Client, token: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    me = http.get(f"{APIFY}/users/me", headers=headers)
    if me.status_code in (401, 403):
        raise UpstreamError("Apify rejected this token")
    if me.is_error:
        raise UpstreamError(f"Apify error {me.status_code}: {_short(me)}")
    limits = http.get(f"{APIFY}/users/me/limits", headers=headers)
    if limits.is_error:
        raise UpstreamError(f"Apify error {limits.status_code}: {_short(limits)}")
    user, lim = me.json()["data"], limits.json()["data"]
    used, cap = lim["current"]["monthlyUsageUsd"], lim["limits"]["maxMonthlyUsageUsd"]
    return {
        "username": user.get("username"),
        "plan": (user.get("plan") or {}).get("id"),
        "usage_usd": used,
        "limit_usd": cap,
        "remaining_usd": round(cap - used, 4),
        "cycle_end": (lim.get("monthlyUsageCycle") or {}).get("endAt"),
    }


def llm_ping(http: httpx.Client, cfg: LlmConfig) -> dict:
    prompt = "Reply with the single word: ok"
    base = cfg.base_url.rstrip("/")
    started = time.perf_counter()
    if cfg.protocol == "anthropic":
        resp = http.post(
            f"{base}/v1/messages",
            headers={"x-api-key": cfg.api_key, "anthropic-version": "2023-06-01"},
            json={"model": cfg.model, "max_tokens": 16, "messages": [{"role": "user", "content": prompt}]},
        )
    else:
        resp = http.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {cfg.api_key}"},
            json={
                "model": cfg.model,
                "max_tokens": 16,
                "usage": {"include": True},
                "messages": [{"role": "user", "content": prompt}],
            },
        )
    latency_ms = round((time.perf_counter() - started) * 1000)
    if resp.is_error:
        raise UpstreamError(f"LLM provider error {resp.status_code}: {_short(resp)}")
    body = resp.json()
    if cfg.protocol == "anthropic":
        reply = "".join(b.get("text", "") for b in body.get("content", []) if b.get("type") == "text")
        usage = body.get("usage", {})
        tokens = (usage.get("input_tokens"), usage.get("output_tokens"))
        cost = None
    else:
        reply = body["choices"][0]["message"]["content"] or ""
        usage = body.get("usage", {})
        tokens = (usage.get("prompt_tokens"), usage.get("completion_tokens"))
        cost = usage.get("cost")
    return {
        "model": body.get("model", cfg.model),
        "reply": reply.strip()[:80],
        "latency_ms": latency_ms,
        "input_tokens": tokens[0],
        "output_tokens": tokens[1],
        "cost_usd": cost,
    }


def openrouter_exchange(http: httpx.Client, code: str, verifier: str) -> str:
    resp = http.post(
        OPENROUTER_KEYS,
        json={"code": code, "code_verifier": verifier, "code_challenge_method": "S256"},
    )
    if resp.is_error:
        raise UpstreamError(f"OpenRouter could not exchange the code ({resp.status_code}): {_short(resp)}")
    key = resp.json().get("key")
    if not key:
        raise UpstreamError("OpenRouter returned no key")
    return key
