import json
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from app import brand, discovery, prompts
from app.llm import Completion
from app.main import app
from tests.helpers import DataDirTestCase
from tests.test_brand import VALID


class PromptStoreTest(DataDirTestCase):
    def test_both_prompts_are_registered_and_split_into_instructions_and_a_fixed_format(self):
        self.assertEqual({p.id for p in prompts.all_prompts()}, {"brand_brief", "account_sorting", "creator_scoring"})
        for p in prompts.all_prompts():
            self.assertNotIn(p.marker, p.default_instructions, p.id)
            self.assertTrue(p.output_format.startswith(p.marker), p.id)
            self.assertIn("JSON", p.output_format, p.id)
            self.assertEqual(prompts.system(p.id), p.default, p.id)  # untouched, the model gets exactly the built-in prompt

    def test_what_the_user_writes_replaces_the_instructions_and_the_format_is_always_added(self):
        prompts.save("account_sorting", "Treat every cafe as a competitor.")
        full = prompts.system("account_sorting")
        self.assertTrue(full.startswith("Treat every cafe as a competitor."))
        self.assertTrue(full.endswith(prompts.get("account_sorting").output_format))
        self.assertNotIn("A home cook showing recipes", full)
        self.assertEqual(prompts.instructions("account_sorting"), ("Treat every cafe as a competitor.", True))

    def test_an_edit_that_equals_the_built_in_text_is_not_kept_as_an_edit(self):
        prompts.save("brand_brief", "something else")
        prompts.save("brand_brief", prompts.get("brand_brief").default_instructions + "\n\n")
        self.assertFalse(prompts.instructions("brand_brief")[1])

    def test_reset_goes_back_to_the_built_in_text(self):
        prompts.save("brand_brief", "short")
        prompts.reset("brand_brief")
        self.assertEqual(prompts.instructions("brand_brief"), (prompts.get("brand_brief").default_instructions, False))

    def test_empty_and_oversized_instructions_are_refused_and_nothing_is_stored(self):
        for text, word in (("   \n", "empty"), ("x" * (prompts.MAX_CHARS + 1), "too long")):
            with self.assertRaises(ValueError) as caught:
                prompts.save("brand_brief", text)
            self.assertIn(word, str(caught.exception))
        self.assertFalse(prompts.instructions("brand_brief")[1])

    def test_an_unknown_prompt_is_a_key_error(self):
        with self.assertRaises(KeyError):
            prompts.save("nope", "x")

    def test_the_brand_brief_is_written_with_the_saved_instructions(self):
        prompts.save("brand_brief", "Write like a pirate.")
        cfg = mock.Mock(model="m")
        reply = Completion(json.dumps(VALID, ensure_ascii=False), "m", 1, 10, 10, None)
        with mock.patch.object(brand.llm, "complete", return_value=reply) as complete:
            brand.build_profile(None, cfg, [{"url": "https://x.co", "title": "x", "text": "menu"}], None, [])
        system = complete.call_args.args[2]
        self.assertTrue(system.startswith("Write like a pirate."))
        self.assertIn("JSON shape", system)  # the part the code depends on is still there

    def test_the_account_sorting_uses_the_saved_instructions(self):
        prompts.save("account_sorting", "Only people with a face are creators.")
        accounts = discovery.group_creators([{"authorMeta": {"name": "amy", "fans": 5}, "createTimeISO": "2026-10-01T00:00:00+00:00", "text": "hi"}])
        reply = Completion("[]", "m", 1, 1, 1, None)
        with mock.patch.object(discovery.llm, "complete", return_value=reply) as complete:
            discovery.classify(None, mock.Mock(model="m"), {"brand_name": "B", "category": "c", "products": ["p"]}, accounts)
        self.assertTrue(complete.call_args.args[2].startswith("Only people with a face are creators."))
        self.assertIn("Reply with ONE JSON array", complete.call_args.args[2])


class PromptApiTest(DataDirTestCase):
    def setUp(self):
        super().setUp()
        self.client = TestClient(app)

    def test_list_shows_the_instructions_in_use_the_built_in_ones_and_the_fixed_format(self):
        data = {p["id"]: p for p in self.client.get("/api/settings/prompts").json()}
        brief = data["brand_brief"]
        self.assertEqual((brief["edited"], brief["text"] == brief["default"]), (False, True))
        self.assertTrue(brief["output_format"].startswith("- Reply with ONE JSON object"))
        self.assertNotIn("JSON shape", brief["text"])
        self.assertTrue(brief["used_when"])

    def test_saving_and_resetting_over_the_api(self):
        res = self.client.put("/api/settings/prompts/account_sorting", json={"text": "  New rules.  "})
        self.assertEqual((res.status_code, res.json()["text"], res.json()["edited"]), (200, "New rules.", True))
        listed = {p["id"]: p for p in self.client.get("/api/settings/prompts").json()}
        self.assertEqual((listed["account_sorting"]["edited"], listed["brand_brief"]["edited"]), (True, False))
        res = self.client.delete("/api/settings/prompts/account_sorting")
        self.assertEqual((res.status_code, res.json()["edited"], res.json()["text"] == res.json()["default"]), (200, False, True))

    def test_bad_requests_say_what_is_wrong(self):
        res = self.client.put("/api/settings/prompts/brand_brief", json={"text": " "})
        self.assertEqual(res.status_code, 400)
        self.assertIn("can't be empty", res.json()["detail"])
        self.assertEqual(self.client.put("/api/settings/prompts/nope", json={"text": "x"}).status_code, 404)
        self.assertEqual(self.client.delete("/api/settings/prompts/nope").status_code, 404)


if __name__ == "__main__":
    unittest.main()
