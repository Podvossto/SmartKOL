import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from app import analyses, apify_runner, discovery
from app.clients import UpstreamError
from tests.test_analyses import SITE, ApiTestCase

NOW = datetime.now(timezone.utc)


def video(user, days_ago=2, lang="th", fans=50_000, views=1000, private=False, tag="ของหวาน", **extra):
    return {
        "authorMeta": {"name": user, "nickName": user.title(), "fans": fans, "heart": 9, "video": 40, "verified": False,
                       "privateAccount": private, "signature": "รีวิวขนม ติดต่อ 081-234-5678 หรือ me@mail.com"},
        "createTimeISO": (NOW - timedelta(days=days_ago)).isoformat(), "textLanguage": lang, "playCount": views,
        "text": "เมนูใหม่ โทร 0812345678", "webVideoUrl": f"https://www.tiktok.com/@{user}/video/1", "searchHashtag": {"name": tag}, **extra,
    }


class MaskTest(unittest.TestCase):
    def test_hides_phone_numbers_and_emails_but_keeps_the_rest(self):
        for raw in ("โทร 081-234-5678 นะ", "call +66 81 234 5678", "0812345678", "(02) 123 4567", "mail me@example.co.th now", "ʟɪɴᴇ ɪᴅ:0910387533ᴘ"):
            self.assertIn("[hidden]", discovery.mask_contacts(raw), raw)
        self.assertNotRegex(discovery.mask_contacts("โทร 081-234-5678 หรือ a@b.com"), r"\d{3}|@")
        self.assertEqual(discovery.mask_contacts("รีวิวขนมทุกวัน 2024 ✨ @brand_official"), "รีวิวขนมทุกวัน 2024 ✨ @brand_official")
        self.assertEqual(discovery.mask_contacts(None), "")


class GroupTest(unittest.TestCase):
    def test_one_record_per_author_with_stats_from_their_videos(self):
        creators = discovery.group_creators([
            video("amy", days_ago=9, views=100, tag="a"), video("amy", days_ago=1, lang="en", views=300, tag="b"),
            video("amy", days_ago=3, views=900, isAd=True, hasTikTokShopProduct=True), video("bob", fans=900_000),
            {"authorMeta": {}, "text": "no author"},
        ])
        self.assertEqual([c["username"] for c in creators], ["bob", "amy"])  # biggest first
        amy = creators[1]
        self.assertEqual((amy["videos_found"], amy["thai_share"], amy["median_views"], amy["ad_videos"], amy["shop_videos"]), (3, 0.667, 300, 1, 1))
        self.assertEqual(amy["url"], "https://www.tiktok.com/@amy")
        self.assertEqual(amy["hashtags"], ["a", "b", "ของหวาน"])
        self.assertEqual(amy["last_post"], (NOW - timedelta(days=1)).isoformat())
        self.assertEqual([s["views"] for s in amy["samples"]], [900, 300])

    def test_no_phone_or_email_survives_in_a_stored_record(self):
        stored = str(discovery.group_creators([video("amy")]))
        self.assertNotIn("081", stored)
        self.assertNotIn("@mail", stored)
        self.assertIn("[hidden]", stored)


class FilterTest(unittest.TestCase):
    def setUp(self):
        self.pool = discovery.group_creators([
            video("good"), video("english", lang="en"), video("hidden", private=True), video("stale", days_ago=90),
            video("tiny", fans=2_000), video("giant", fans=5_000_000),
        ])
        self.names = lambda kept: sorted(c["username"] for c in kept)

    def test_defaults_follow_the_spec(self):
        kept, dropped = discovery.apply_filters(self.pool, discovery.Filters(), NOW)
        self.assertEqual(self.names(kept), ["giant", "good"])
        self.assertEqual(dropped, {"thai": 1, "private": 1, "recent": 1, "min_followers": 1, "max_followers": 0})

    def test_each_filter_can_be_turned_off_on_its_own(self):
        off = {"thai": dict(thai_min=None), "private": dict(skip_private=False), "recent": dict(max_age_days=None), "min_followers": dict(min_followers=None)}
        for name, change in off.items():
            kept, _ = discovery.apply_filters(self.pool, discovery.Filters(**change), NOW)
            self.assertEqual(len(kept), 3, name)
        kept, _ = discovery.apply_filters(self.pool, discovery.Filters(None, False, None, None, None), NOW)
        self.assertEqual(len(kept), 6)

    def test_follower_range_and_a_missing_value(self):
        kept, dropped = discovery.apply_filters(self.pool, discovery.Filters(max_followers=1_000_000), NOW)
        self.assertEqual((self.names(kept), dropped["max_followers"]), (["good"], 1))
        unknown = [{**self.pool[0], "followers": None, "last_post": None}]
        self.assertEqual(discovery.apply_filters(unknown, discovery.Filters(), NOW)[0], [])


class PlanTest(unittest.TestCase):
    PROFILE = {"tiktok": {"hashtags_th": ["#a", "b", "c"], "hashtags_en": ["d", "e", "f", "g"]}}

    def test_a_preset_takes_the_first_hashtags_of_the_list(self):
        tags, run_input = discovery.plan(self.PROFILE, "lean")
        self.assertEqual(tags, ["a", "b", "c"])
        self.assertEqual(run_input["resultsPerPage"], 25)
        self.assertFalse(run_input["shouldDownloadVideos"])
        self.assertEqual(discovery.plan(self.PROFILE, "full")[0], ["a", "b", "c", "d", "e", "f"])

    def test_estimate_prices_every_video_plus_the_start_fee_and_is_free_when_cached(self):
        with mock.patch.object(apify_runner, "is_cached", return_value=False):
            lean, full = discovery.estimate(self.PROFILE, "lean"), discovery.estimate(self.PROFILE, "full")
        self.assertEqual((lean["videos"], lean["usd"]), (75, round(75 * 0.0037 + 0.001, 4)))
        self.assertEqual((full["videos"], full["usd"]), (240, round(240 * 0.0037 + 0.001, 4)))
        with mock.patch.object(apify_runner, "is_cached", return_value=True):
            self.assertEqual(discovery.estimate(self.PROFILE, "lean")["usd"], 0.0)


class SearchApiTest(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.aid = self.run_analysis(website_url=SITE, facebook_url="https://www.facebook.com/afteryoucafe")["id"]
        self.actor = mock.patch.object(apify_runner, "run_actor", return_value=([video("amy"), video("amy", days_ago=5), video("bob", lang="en")], 0.28, False))
        self.account = mock.patch("app.clients.apify_account", return_value={"remaining_usd": 4.0})
        self.run = self.actor.start()
        self.account.start()
        self.addCleanup(self.actor.stop)
        self.addCleanup(self.account.stop)
        self.m["spawn"].side_effect = lambda fn, *a: fn(*a)

    def search(self, preset="lean"):
        return self.client.post(f"/api/analyses/{self.aid}/creators/search", json={"preset": preset})

    def test_a_search_stores_creators_adds_the_cost_and_keeps_the_polled_state_light(self):
        before = self.get(self.aid)["cost"]["apify_usd"]
        self.assertEqual(self.search().status_code, 200)
        state = self.get(self.aid)
        self.assertEqual((state["creators"]["status"], state["creators"]["found"], state["creators"]["videos"]), ("done", 2, 3))
        self.assertNotIn("items", state["creators"])
        self.assertEqual(state["cost"]["apify_usd"], round(before + 0.28, 5))
        called = self.run.call_args.args
        self.assertEqual(called[1], discovery.ACTOR)
        self.assertEqual(called[2]["hashtags"], ["ของหวาน", "คาเฟ่กรุงเทพ", "ขนมหวาน"])

    def test_the_filtered_list_comes_from_the_stored_creators_for_free(self):
        self.search()
        self.run.reset_mock()
        listing = self.client.get(f"/api/analyses/{self.aid}/creators").json()
        self.assertEqual((listing["total"], [c["username"] for c in listing["kept"]], listing["dropped"]["thai"]), (2, ["amy"], 1))
        every = self.client.get(f"/api/analyses/{self.aid}/creators", params={"thai_min": 0}).json()
        self.assertEqual(len(every["kept"]), 2)
        self.run.assert_not_called()

    def test_estimate_returns_the_price_and_the_credits_left(self):
        res = self.client.post(f"/api/analyses/{self.aid}/creators/estimate", json={"preset": "full"}).json()
        self.assertEqual((res["estimate"]["videos"], res["account"]["remaining_usd"]), (160, 4.0))  # the test profile has 4 hashtags
        self.run.assert_not_called()

    def test_refuses_what_it_cannot_afford_or_cannot_search(self):
        with mock.patch("app.clients.apify_account", return_value={"remaining_usd": 0.05}):
            res = self.search()
        self.assertEqual(res.status_code, 400)
        self.assertIn("$0.05", res.json()["detail"]["message"])
        self.assertEqual(self.search("huge").json()["detail"]["field"], "preset")
        self.assertEqual(self.client.post("/api/analyses/nope/creators/search", json={}).status_code, 404)
        self.run.assert_not_called()

    def test_a_failed_search_says_why_and_can_be_repeated(self):
        self.run.side_effect = UpstreamError("Apify run failed (clockworks/tiktok-scraper): quota")
        self.search()
        creators = self.get(self.aid)["creators"]
        self.assertEqual((creators["status"], creators["error"]), ("error", "Apify run failed (clockworks/tiktok-scraper): quota"))
        self.run.side_effect = None
        self.search()
        self.assertEqual(self.get(self.aid)["creators"]["status"], "done")

    def test_a_search_cut_off_by_a_restart_is_marked_as_failed(self):
        analyses.update(self.aid, lambda s: s["creators"].update(status="running"))
        analyses.mark_interrupted()
        self.assertEqual(self.get(self.aid)["creators"]["status"], "error")

    def test_old_analyses_without_the_field_still_open(self):
        analyses.update(self.aid, lambda s: s.pop("creators"))
        self.assertEqual(self.get(self.aid)["creators"]["status"], "idle")


if __name__ == "__main__":
    unittest.main()
