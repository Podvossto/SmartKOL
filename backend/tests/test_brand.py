import json
import unittest
from unittest import mock

from app import brand
from app.clients import UpstreamError
from app.config import LlmConfig
from app.llm import Completion

CFG = LlmConfig("openrouter", "openai", "https://openrouter.ai/api/v1", "k", "anthropic/claude-haiku-5.5", "manual", "ui")

VALID = {
    "brand_name": "After You", "category": "Dessert cafe", "price_tier": "mid",
    "positioning": "For young urban dessert lovers, After You is the Bangkok cafe that makes signature toast desserts.",
    "summary": "Signature desserts in Bangkok.",
    "products": ["Shibuya Honey Toast", "Chocolate Lava Cake"],
    "audience": {"description": "Young urban dessert lovers", "age_range": "18-34", "gender": "mostly female",
                 "interests": ["cafe hopping"], "lifestyle": "social, Instagram-driven", "media_habits": ["Facebook", "delivery apps"]},
    "voice": {"traits": ["playful", "indulgent"], "style": "short Thai captions with emoji", "dos": ["show the product"], "donts": ["claim it is healthy"]},
    "pillars": [{"theme": "Seasonal menus", "detail": "Matcha launch", "performance": "strong"}, {"theme": "Collabs", "detail": "BB Taro Ball"}],
    "formats": ["short video / reels"],
    "creator_fit": {"niches": ["cafe and dessert reviewer"], "content_styles": ["eating close-ups"], "audience_match": "Women 18-34 in Bangkok",
                    "language": "Thai", "avoid": ["diet-focused creators"]},
    "language": "Thai",
    "tiktok": {"hashtags_th": ["#ของหวาน", "คาเฟ่กรุงเทพ", "ขนมหวาน"], "hashtags_en": ["dessert"], "keywords": ["รีวิวขนม", "รีวิวขนม"]},
    "evidence": [{"fact": "24 branches in Bangkok", "source": "website"}], "gaps": ["Prices were not found"],
    "by_source": {"website": {"summary": "Menu and branches.", "key_points": ["24 branches"]},
                  "facebook": {"summary": "Playful launch posts.", "key_points": ["new menu every week"]}},
}


def reply(data, **kw) -> Completion:
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return Completion(text, "m", 100, kw.get("tin", 1000), kw.get("tout", 300), kw.get("cost", 0.001))


class ParseProfileTest(unittest.TestCase):
    def test_accepts_json_wrapped_in_text_and_fences(self):
        p = brand.parse_profile("Here you go:\n```json\n" + json.dumps(VALID, ensure_ascii=False) + "\n```")
        self.assertEqual(p.brand_name, "After You")

    def test_hashtags_are_cleaned_and_keywords_deduped(self):
        p = brand.parse_profile(json.dumps(VALID, ensure_ascii=False))
        self.assertEqual(p.tiktok.hashtags_th, ["ของหวาน", "คาเฟ่กรุงเทพ", "ขนมหวาน"])
        self.assertEqual(p.tiktok.keywords, ["รีวิวขนม"])

    def test_rejects_missing_or_empty_required_fields(self):
        for mutate in (lambda d: d.update(products=[]), lambda d: d["tiktok"].update(hashtags_th=[]),
                       lambda d: d.update(positioning=" "), lambda d: d["voice"].update(traits=[]), lambda d: d.update(pillars=[]),
                       lambda d: d["creator_fit"].update(niches=[]), lambda d: d.pop("creator_fit"),
                       lambda d: d.update(summary="  "), lambda d: d.pop("audience"), lambda d: d.update(price_tier="cheap")):
            data = json.loads(json.dumps(VALID))
            mutate(data)
            with self.assertRaises(ValueError):
                brand.parse_profile(json.dumps(data))

    def test_every_source_that_was_read_needs_its_own_summary(self):
        both = {"website", "facebook"}
        self.assertEqual(set(brand.parse_profile(json.dumps(VALID, ensure_ascii=False), both).by_source), both)
        for drop in ("website", "facebook"):
            data = json.loads(json.dumps(VALID))
            del data["by_source"][drop]
            with self.assertRaisesRegex(ValueError, f"by_source.{drop}"):
                brand.parse_profile(json.dumps(data), both)

    def test_summaries_for_sources_that_were_not_read_are_dropped(self):
        profile = brand.parse_profile(json.dumps(VALID, ensure_ascii=False), {"website"})
        self.assertEqual(list(profile.by_source), ["website"])

    def test_gaps_and_evidence_sources_are_kept_and_evidence_sources_are_restricted(self):
        p = brand.parse_profile(json.dumps(VALID, ensure_ascii=False))
        self.assertEqual((p.gaps, p.evidence[0].source), (["Prices were not found"], "website"))
        data = json.loads(json.dumps(VALID))
        data["evidence"][0]["source"] = "instagram"
        with self.assertRaises(ValueError):
            brand.parse_profile(json.dumps(data))

    def test_a_profile_saved_before_the_brief_structure_still_opens(self):
        old = {k: v for k, v in VALID.items() if k not in ("positioning", "voice", "pillars", "formats", "creator_fit", "gaps")}
        old.update(tone=["warm"], content_style="photo-led", brand_values=["quality"], evidence=["24 branches"])
        p = brand.BrandProfile.model_validate(old)
        self.assertEqual((p.voice.traits, p.voice.style, p.evidence[0].fact, p.pillars, p.positioning), (["warm"], "photo-led", "24 branches", [], ""))

    def test_rejects_non_json(self):
        with self.assertRaises(ValueError):
            brand.parse_profile("Sorry, I cannot help with that.")


class BuildProfileTest(unittest.TestCase):
    def test_retries_once_and_sums_usage(self):
        with mock.patch.object(brand.llm, "complete", side_effect=[reply("not json", cost=0.002), reply(VALID, cost=0.003)]) as m:
            profile, usage = brand.build_profile(mock.Mock(), CFG, [{"url": "u", "text": "t"}], None, [])
        self.assertEqual(profile.category, "Dessert cafe")
        self.assertEqual(list(profile.by_source), ["website"])  # only a website was read
        self.assertEqual((usage["calls"], usage["input_tokens"], usage["output_tokens"]), (2, 2000, 600))
        self.assertAlmostEqual(usage["cost_usd"], 0.005)
        self.assertIn("rejected", m.call_args_list[1].args[3])  # the retry tells the model what was wrong

    def test_gives_up_after_two_bad_replies(self):
        with mock.patch.object(brand.llm, "complete", return_value=reply("nope")):
            with self.assertRaises(UpstreamError):
                brand.build_profile(mock.Mock(), CFG, [], None, [])

    def test_prompt_contains_website_and_facebook_evidence_truncated(self):
        pages = [{"url": "https://b.com", "title": "B", "description": "d", "text": "x" * 20000}]
        fb = {"title": "B Bangkok", "category": "Dessert Shop", "followers": 355000, "address": "Bangkok", "intro": "hi"}
        posts = [{"time": "2026-10-28T12:00:00Z", "likes": 5, "comments": 1, "shares": 0, "text": "y" * 1000}]
        text = brand.build_evidence(pages, fb, posts)
        self.assertIn("https://b.com", text)
        self.assertIn("355000", text)
        self.assertLess(len(text), brand.PAGE_CHARS + brand.POST_CHARS + 1000)


if __name__ == "__main__":
    unittest.main()
