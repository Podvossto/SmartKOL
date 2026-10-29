import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.routers.settings import get_http

APIFY_KEY = "apify_api_SECRETTOKEN1234"
LLM_KEY = "sk-or-v1-SECRETLLMKEY9876"


def fake_upstream(request: httpx.Request) -> httpx.Response:
    url, auth = str(request.url), request.headers.get("authorization", "")
    if url.endswith("/users/me"):
        if auth != f"Bearer {APIFY_KEY}":
            return httpx.Response(401, json={"error": {"message": "bad token"}})
        return httpx.Response(200, json={"data": {"username": "tester", "plan": {"id": "FREE"}}})
    if url.endswith("/users/me/limits"):
        return httpx.Response(
            200,
            json={"data": {"current": {"monthlyUsageUsd": 0.4}, "limits": {"maxMonthlyUsageUsd": 5},
                           "monthlyUsageCycle": {"endAt": "2026-11-28T23:59:59.999Z"}}},
        )
    if url.endswith("/chat/completions"):
        body = json.loads(request.content)
        if auth != f"Bearer {LLM_KEY}":
            return httpx.Response(401, json={"error": {"message": "invalid key"}})
        return httpx.Response(
            200,
            json={"model": body["model"], "choices": [{"message": {"content": "ok"}}],
                  "usage": {"prompt_tokens": 12, "completion_tokens": 1, "cost": 0.00001}},
        )
    if url.endswith("/v1/messages"):
        return httpx.Response(
            200, json={"model": "claude-x", "content": [{"type": "text", "text": "ok"}],
                       "usage": {"input_tokens": 9, "output_tokens": 1}},
        )
    if url.endswith("/auth/keys"):
        body = json.loads(request.content)
        if body["code"] != "good-code" or body["code_verifier"] != "verifier":
            return httpx.Response(400, json={"error": {"message": "invalid code"}})
        return httpx.Response(200, json={"key": LLM_KEY})
    return httpx.Response(404)


class SettingsApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        patcher = mock.patch.dict(os.environ, {"SMARTKOL_DATA_DIR": self.tmp.name}, clear=False)
        patcher.start()
        for name in ("APIFY_TOKEN", "LLM_PROTOCOL", "LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "SMARTKOL_SECRET_KEY"):
            os.environ.pop(name, None)
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

        def override():
            with httpx.Client(transport=httpx.MockTransport(fake_upstream)) as client:
                yield client

        app.dependency_overrides[get_http] = override
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)

    def test_fresh_install_has_nothing_configured(self):
        data = self.client.get("/api/settings").json()
        self.assertFalse(data["apify"]["configured"])
        self.assertFalse(data["llm"]["configured"])
        self.assertIn("openrouter", data["presets"])

    def test_apify_token_is_masked_and_encrypted_at_rest(self):
        res = self.client.put("/api/settings/apify", json={"token": f"  {APIFY_KEY}\n"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["apify"]["masked"], "••••1234")
        self.assertNotIn(APIFY_KEY, self.client.get("/api/settings").text)
        for path in Path(self.tmp.name).glob("*.db"):
            self.assertNotIn(APIFY_KEY.encode(), path.read_bytes())

    def test_apify_test_returns_account_and_credit(self):
        self.client.put("/api/settings/apify", json={"token": APIFY_KEY})
        data = self.client.post("/api/settings/apify/test").json()
        self.assertEqual((data["username"], data["plan"], data["remaining_usd"]), ("tester", "FREE", 4.6))

    def test_bad_apify_token_gives_safe_error(self):
        self.client.put("/api/settings/apify", json={"token": "wrong-token-value"})
        res = self.client.post("/api/settings/apify/test")
        self.assertEqual(res.status_code, 400)
        self.assertNotIn("wrong-token-value", res.text)

    def test_env_is_the_fallback_and_ui_overrides_it(self):
        with mock.patch.dict(os.environ, {"APIFY_TOKEN": "env-token-5555"}):
            self.assertEqual(self.client.get("/api/settings").json()["apify"]["source"], "env")
            self.client.put("/api/settings/apify", json={"token": APIFY_KEY})
            self.assertEqual(self.client.get("/api/settings").json()["apify"]["source"], "ui")
            self.client.delete("/api/settings/apify")
            self.assertEqual(self.client.get("/api/settings").json()["apify"]["source"], "env")

    def test_openrouter_preset_and_llm_ping(self):
        res = self.client.put("/api/settings/llm", json={"provider": "openrouter", "api_key": LLM_KEY})
        llm = res.json()["llm"]
        self.assertEqual((llm["protocol"], llm["model"]), ("openai", "anthropic/claude-haiku-5.5"))
        self.assertNotIn(LLM_KEY, res.text)
        ping = self.client.post("/api/settings/llm/test").json()
        self.assertEqual((ping["reply"], ping["input_tokens"], ping["cost_usd"]), ("ok", 12, 0.00001))

    def test_changing_model_keeps_saved_key(self):
        self.client.put("/api/settings/llm", json={"provider": "openrouter", "api_key": LLM_KEY})
        self.client.put("/api/settings/llm", json={"provider": "openrouter", "model": "google/gemini-2.5-flash-lite"})
        self.assertEqual(self.client.post("/api/settings/llm/test").json()["model"], "google/gemini-2.5-flash-lite")

    def test_switching_provider_never_reuses_another_providers_key(self):
        self.client.put("/api/settings/llm", json={"provider": "openrouter", "api_key": LLM_KEY})
        res = self.client.put("/api/settings/llm", json={"provider": "anthropic"})
        self.assertEqual(res.status_code, 400)

    def test_custom_provider_validates_base_url_and_uses_anthropic_protocol(self):
        bad = self.client.put("/api/settings/llm", json={"provider": "custom", "protocol": "openai", "api_key": "k1234567", "base_url": "ftp://x", "model": "m"})
        self.assertEqual(bad.status_code, 400)
        ok = self.client.put("/api/settings/llm", json={"provider": "custom", "protocol": "anthropic", "api_key": "k1234567", "base_url": "https://api.z.ai/api/anthropic/", "model": "glm"})
        self.assertEqual(ok.json()["llm"]["base_url"], "https://api.z.ai/api/anthropic")
        self.assertEqual(self.client.post("/api/settings/llm/test").json()["reply"], "ok")

    def test_openrouter_oauth_exchange_stores_key_as_oauth(self):
        res = self.client.post("/api/settings/openrouter/exchange", json={"code": "good-code", "code_verifier": "verifier"})
        llm = res.json()["llm"]
        self.assertEqual((llm["auth"], llm["provider"]), ("oauth", "openrouter"))
        self.assertNotIn(LLM_KEY, res.text)
        self.assertEqual(self.client.post("/api/settings/llm/test").json()["reply"], "ok")

    def test_oauth_exchange_with_bad_code_fails_cleanly(self):
        res = self.client.post("/api/settings/openrouter/exchange", json={"code": "nope", "code_verifier": "verifier"})
        self.assertEqual(res.status_code, 400)
        self.assertFalse(self.client.get("/api/settings").json()["llm"]["configured"])


if __name__ == "__main__":
    unittest.main()
