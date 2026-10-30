"""Settings API: save / mask / test the Apify token and the LLM provider. Keys never leave the backend."""
from collections.abc import Iterator
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from .. import clients, config, secrets_store

router = APIRouter(prefix="/api/settings", tags=["settings"])


def get_http() -> Iterator[httpx.Client]:
    with httpx.Client(timeout=30) as client:
        yield client


def _clean(value: str) -> str:
    return "".join(value.split())  # keys never contain whitespace; strips pasted newlines


class ApifyIn(BaseModel):
    token: str

    @field_validator("token")
    @classmethod
    def _token(cls, v: str) -> str:
        v = _clean(v)
        if not v:
            raise ValueError("token is empty")
        return v


class LlmIn(BaseModel):
    provider: str
    api_key: str | None = None  # omitted = keep the saved key, change only model/base URL
    model: str | None = None
    protocol: str | None = None  # custom provider only
    base_url: str | None = None  # custom provider only

    @field_validator("provider")
    @classmethod
    def _provider(cls, v: str) -> str:
        if v not in ("openrouter", "anthropic", "custom"):
            raise ValueError("provider must be openrouter, anthropic or custom")
        return v


class ExchangeIn(BaseModel):
    code: str
    code_verifier: str


def _bad(message: str) -> HTTPException:
    return HTTPException(status_code=400, detail=message)


def _view() -> dict:
    token, token_origin = config.apify_token()
    llm = config.llm_config()
    return {
        "apify": {"configured": bool(token), "source": token_origin, "masked": config.mask(token) if token else None},
        "llm": {
            "configured": llm is not None,
            "source": llm.origin if llm else "none",
            "auth": llm.auth if llm else None,
            "provider": llm.provider if llm else None,
            "protocol": llm.protocol if llm else None,
            "base_url": llm.base_url if llm else None,
            "model": llm.model if llm else None,
            "masked": config.mask(llm.api_key) if llm else None,
        },
        "presets": {k: {"protocol": p, "base_url": b, "model": m} for k, (p, b, m) in config.PRESETS.items()},
    }


@router.get("")
def read_settings() -> dict:
    return _view()


@router.put("/apify")
def save_apify(body: ApifyIn) -> dict:
    secrets_store.put("apify", {"token": body.token})
    return _view()


@router.delete("/apify")
def clear_apify() -> dict:
    secrets_store.delete("apify")
    return _view()


@router.post("/apify/test")
def test_apify(http: httpx.Client = Depends(get_http)) -> dict:
    token, _ = config.apify_token()
    if not token:
        raise _bad("No Apify token configured")
    try:
        return clients.apify_account(http, token)
    except (clients.UpstreamError, httpx.HTTPError) as exc:
        raise _bad(str(exc) if isinstance(exc, clients.UpstreamError) else "Could not reach Apify")


@router.put("/llm")
def save_llm(body: LlmIn) -> dict:
    saved = secrets_store.get("llm") or {}
    # Only reuse saved values for the same provider — never send one provider's key to another.
    existing = saved if saved.get("provider") == body.provider else {}
    if not existing:
        # a key that came from credential/.env counts too, so the model can be changed without pasting it again
        active = config.llm_config()
        if active and active.provider == body.provider:
            existing = {"api_key": active.api_key, "model": active.model, "protocol": active.protocol, "base_url": active.base_url}
    if body.provider == "custom":
        protocol = body.protocol or existing.get("protocol")
        base_url = (body.base_url or existing.get("base_url") or "").strip().rstrip("/")
        if protocol not in config.PROTOCOLS:
            raise _bad("Custom provider needs protocol 'openai' or 'anthropic'")
        if urlparse(base_url).scheme not in ("http", "https") or not urlparse(base_url).netloc:
            raise _bad("Custom provider needs a valid http(s) base URL")
        default_model = ""
    else:
        protocol, base_url, default_model = config.PRESETS[body.provider]

    api_key = _clean(body.api_key) if body.api_key else existing.get("api_key", "")
    if not api_key:
        raise _bad("API key is required")
    model = (body.model or "").strip() or existing.get("model") or default_model
    if not model:
        raise _bad("Model is required")

    manual_replaced = bool(body.api_key)
    secrets_store.put(
        "llm",
        {
            "provider": body.provider,
            "protocol": protocol,
            "base_url": base_url,
            "api_key": api_key,
            "model": model,
            "auth": "manual" if manual_replaced else existing.get("auth", "manual"),
        },
    )
    return _view()


@router.delete("/llm")
def clear_llm() -> dict:
    secrets_store.delete("llm")
    return _view()


@router.post("/llm/test")
def test_llm(http: httpx.Client = Depends(get_http)) -> dict:
    cfg = config.llm_config()
    if not cfg:
        raise _bad("No LLM configured")
    if not cfg.model:
        raise _bad("No model set")
    try:
        return clients.llm_ping(http, cfg)
    except (clients.UpstreamError, httpx.HTTPError) as exc:
        raise _bad(str(exc) if isinstance(exc, clients.UpstreamError) else "Could not reach the LLM provider")


@router.post("/llm/balance")
def llm_balance(http: httpx.Client = Depends(get_http)) -> dict:
    """Credit left with the model provider, when it says (OpenRouter). Empty values when it does not."""
    cfg = config.llm_config()
    if not cfg:
        raise _bad("No LLM configured")
    try:
        return clients.llm_balance(http, cfg) or {"usage_usd": None, "limit_usd": None, "remaining_usd": None}
    except (clients.UpstreamError, httpx.HTTPError) as exc:
        raise _bad(str(exc) if isinstance(exc, clients.UpstreamError) else "Could not reach the LLM provider")


@router.post("/openrouter/exchange")
def openrouter_exchange(body: ExchangeIn, http: httpx.Client = Depends(get_http)) -> dict:
    try:
        key = clients.openrouter_exchange(http, body.code.strip(), body.code_verifier.strip())
    except (clients.UpstreamError, httpx.HTTPError) as exc:
        raise _bad(str(exc) if isinstance(exc, clients.UpstreamError) else "Could not reach OpenRouter")
    protocol, base_url, model = config.PRESETS["openrouter"]
    saved = secrets_store.get("llm") or {}
    if saved.get("provider") == "openrouter" and saved.get("model"):
        model = saved["model"]  # signing in again must not undo the model that was chosen
    secrets_store.put(
        "llm",
        {"provider": "openrouter", "protocol": protocol, "base_url": base_url, "api_key": key, "model": model, "auth": "oauth"},
    )
    return _view()
