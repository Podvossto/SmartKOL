import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import json

from app import analyses, apify_runner, discovery
from app.clients import UpstreamError
from app.llm import Completion
from tests.helpers import DataDirTestCase
from tests.test_analyses import SITE, ApiTestCase

NOW = datetime.now(timezone.utc)


def video(user, days_ago=2, lang="th", fans=50_000, views=1000, private=False, tag="ของหวาน", **extra):
    return {
        "authorMeta": {"name": user, "nickName": user.title(), "fans": fans, "heart": 9, "video": 40, "verified": False,
                       "privateAccount": private, "avatar": f"https://cdn.example/{user}/avatar.jpg", "signature": "รีวิวขนม ติดต่อ 081-234-5678 หรือ me@mail.com"},
        "createTimeISO": (NOW - timedelta(days=days_ago)).isoformat(), "textLanguage": lang, "playCount": views,
        "text": "เมนูใหม่ โทร 0812345678", "videoMeta": {"coverUrl": f"https://cdn.example/{user}/cover.jpg"}, "webVideoUrl": f"https://www.tiktok.com/@{user}/video/1", "searchHashtag": {"name": tag}, **extra,
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
        self.assertEqual([s["views"] for s in amy["samples"]], [900, 300, 100])

    def test_a_bio_keeps_its_contact_details_but_captions_do_not(self):
        amy = discovery.group_creators([video("amy")])[0]
        self.assertIn("081", amy["bio"])
        self.assertIn("@mail", amy["bio"])
        self.assertNotRegex(str([s["text"] for s in amy["samples"]]), r"\d{8}|@mail")

    def test_the_contacts_in_a_text_are_listed_once_in_order(self):
        self.assertEqual(discovery.contacts("งานติดต่อ a@b.com โทร 081-234-5678 หรือ a@b.com"), ["a@b.com", "081-234-5678"])
        self.assertEqual((discovery.contacts(None), discovery.contacts("รีวิว @brand_official 2024")), ([], []))


class PublicTest(unittest.TestCase):
    def test_the_browser_never_gets_a_tiktok_picture_link(self):
        raw = discovery.group_creators([video("amy")])[0]
        self.assertEqual(raw["avatar_src"], "https://cdn.example/amy/avatar.jpg")
        shown = discovery.public_creator(raw)
        self.assertNotIn("cdn.example", str(shown))
        self.assertTrue(shown["has_avatar"])
        self.assertTrue(shown["samples"][0]["has_cover"])
        self.assertNotIn("avatar_src", shown)

    def test_a_creator_without_pictures_says_so(self):
        raw = discovery.group_creators([{**video("amy"), "videoMeta": {}, "authorMeta": {"name": "amy"}}])[0]
        shown = discovery.public_creator(raw)
        self.assertEqual((shown["has_avatar"], shown["samples"][0]["has_cover"]), (False, False))


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
        self.assertEqual(dropped, {"thai": 1, "private": 1, "recent": 1, "min_followers": 1, "max_followers": 0, "shops": 0})

    def test_each_filter_can_be_turned_off_on_its_own(self):
        off = {"thai": dict(thai_min=None), "private": dict(skip_private=False), "recent": dict(max_age_days=None), "min_followers": dict(min_followers=None)}
        for name, change in off.items():
            kept, _ = discovery.apply_filters(self.pool, discovery.Filters(**change), NOW)
            self.assertEqual(len(kept), 3, name)
        kept, _ = discovery.apply_filters(self.pool, discovery.Filters(None, False, None, None, None), NOW)
        self.assertEqual(len(kept), 6)

    def test_shops_and_media_are_hidden_unless_the_filter_is_off_and_unlabelled_accounts_stay(self):
        pool = discovery.group_creators([video(n) for n in ("person", "shop", "page", "mystery", "unsorted")])
        for c in pool:
            c["kind"] = {"person": "creator", "shop": "shop", "page": "media", "mystery": "other"}.get(c["username"])
        kept, dropped = discovery.apply_filters(pool, discovery.Filters(), NOW)
        self.assertEqual((self.names(kept), dropped["shops"]), (["mystery", "person", "unsorted"], 2))
        self.assertEqual(len(discovery.apply_filters(pool, discovery.Filters(skip_shops=False), NOW)[0]), 5)

    def test_follower_range_and_a_missing_value(self):
        kept, dropped = discovery.apply_filters(self.pool, discovery.Filters(max_followers=1_000_000), NOW)
        self.assertEqual((self.names(kept), dropped["max_followers"]), (["good"], 1))
        unknown = [{**self.pool[0], "followers": None, "last_post": None}]
        self.assertEqual(discovery.apply_filters(unknown, discovery.Filters(), NOW)[0], [])


def labelled(**kinds):
    """A language-model reply that labels the accounts named in the prompt. Anyone not named is a creator."""
    def reply(http, cfg, system, user, max_tokens=1500):
        names = [line.split(" | ")[0].lstrip("@") for line in user.splitlines() if line.startswith("@")]
        rows = [{"u": n, "kind": kinds.get(n, "creator"), "competitor": kinds.get(n) == "shop", "reason": "bio sells cakes"} for n in names]
        return Completion(json.dumps(rows), "test-model", 100, 500, 80, 0.0004)
    return reply


class ClassifyTest(DataDirTestCase):
    CFG = mock.Mock(model="test-model")
    PROFILE = {"brand_name": "After You", "category": "Dessert cafe", "products": ["toast"]}

    def accounts(self, *names):
        return discovery.group_creators([video(n) for n in names])

    def run_classify(self, creators, **kw):
        with mock.patch.object(discovery.llm, "complete", **kw) as complete:
            return discovery.classify(None, self.CFG, self.PROFILE, creators), complete

    def test_labels_are_read_back_and_only_a_shop_can_be_a_competitor(self):
        (labels, usage), _ = self.run_classify(self.accounts("amy", "cafe"), side_effect=labelled(cafe="shop"))
        self.assertEqual((labels["amy"]["kind"], labels["amy"]["competitor"]), ("creator", False))
        self.assertEqual((labels["cafe"]["kind"], labels["cafe"]["competitor"], labels["cafe"]["reason"]), ("shop", True, "bio sells cakes"))
        self.assertEqual((usage["input_tokens"], usage["output_tokens"], usage["cost_usd"]), (500, 80, 0.0004))

    def test_a_bad_or_incomplete_reply_labels_nobody_wrongly(self):
        reply = '[{"u": "amy", "kind": "influencer"}, {"u": "ghost", "kind": "shop"}, {"u": "bob", "kind": "media", "competitor": true}, "junk"]'
        (labels, _), _ = self.run_classify(self.accounts("amy", "bob"), return_value=Completion(reply, "m", 1, 1, 1, None))
        self.assertEqual(labels, {"bob": {"kind": "media", "competitor": False, "reason": ""}})
        (labels, _), _ = self.run_classify(self.accounts("amy"), return_value=Completion("sorry, no", "m", 1, 1, 1, None))
        self.assertEqual(labels, {})

    def test_a_reply_cut_off_at_the_token_limit_still_yields_the_complete_rows(self):
        reply = '```json\n[\n{"u": "amy", "kind": "creator", "competitor": false, "reason": "reviewer"},\n{"u": "bob", "kind": "shop", "competitor": true, "reason": "sells cakes"},\n{"u": "cat", "ki'
        (labels, _), _ = self.run_classify(self.accounts("amy", "bob", "cat"), return_value=Completion(reply, "m", 1, 1, 8000, None))
        self.assertEqual({k: v["kind"] for k, v in labels.items()}, {"amy": "creator", "bob": "shop"})

    def test_many_accounts_are_sent_in_batches_and_the_usage_is_summed(self):
        with mock.patch.object(discovery, "CLASSIFY_BATCH", 2):
            (labels, usage), complete = self.run_classify(self.accounts("a", "b", "c", "d", "e"), side_effect=labelled())
        self.assertEqual((complete.call_count, len(labels), usage["input_tokens"]), (3, 5, 1500))

    def test_the_prompt_carries_the_brand_and_what_each_account_says_about_itself(self):
        _, complete = self.run_classify(self.accounts("amy"), side_effect=labelled())
        prompt = complete.call_args.args[3]
        self.assertIn("After You", prompt)
        self.assertIn("@amy | 50000 followers", prompt)
        self.assertIn("[hidden]", prompt)  # contact details never reach the model either


class PlanTest(unittest.TestCase):
    def test_the_choice_is_cleaned_and_a_hashtag_with_no_videos_is_not_searched(self):
        plan = discovery.clean_plan([("#a", 25), (" b c ", 10), ("A", 5), ("d", 0), ("", 9), ("##e", 25)])
        self.assertEqual(plan, [{"hashtag": "a", "videos": 25}, {"hashtag": "bc", "videos": 10}, {"hashtag": "e", "videos": 25}])

    def test_an_unusable_choice_says_what_is_wrong(self):
        for items, text in (([], "at least one"), ([("a", 0)], "at least one"), ([("a", 101)], "100 videos per hashtag"),
                            ([(f"t{i}", 100) for i in range(6)], "500 videos")):
            with self.assertRaises(discovery.PlanError, msg=str(items)) as caught:
                discovery.clean_plan(items)
            self.assertIn(text, str(caught.exception))
        self.assertEqual(sum(p["videos"] for p in discovery.clean_plan([(f"t{i}", 100) for i in range(5)])), 500)  # the limit itself is allowed

    def test_a_hashtag_without_letters_is_refused_but_thai_and_underscores_are_fine(self):
        with self.assertRaises(discovery.PlanError):
            discovery.clean_plan([("????????", 25)])
        plan = discovery.clean_plan([("รีวิวขนม", 10), ("cafe_hopping", 10), ("คากิโกริ", 10)])
        self.assertEqual([p["hashtag"] for p in plan], ["รีวิวขนม", "cafe_hopping", "คากิโกริ"])

    def test_hashtags_with_the_same_count_share_one_run(self):
        plan = discovery.clean_plan([("a", 25), ("b", 10), ("c", 25)])
        runs = discovery.runs(plan)
        self.assertEqual([(r["hashtags"], r["resultsPerPage"]) for r in runs], [(["a", "c"], 25), (["b"], 10)])
        self.assertFalse(runs[0]["shouldDownloadVideos"])

    def test_estimate_prices_every_video_plus_one_start_fee_per_run(self):
        with mock.patch.object(apify_runner, "is_cached", return_value=False):
            one = discovery.estimate(discovery.clean_plan([("a", 25), ("b", 25), ("c", 25)]))
            two = discovery.estimate(discovery.clean_plan([("a", 25), ("b", 10)]))
        self.assertEqual((one["videos"], one["runs"], one["usd"]), (75, 1, round(75 * 0.0037 + 0.001, 4)))
        self.assertEqual((two["videos"], two["runs"], two["usd"]), (35, 2, round(35 * 0.0037 + 2 * 0.001, 4)))

    def test_a_run_already_in_the_cache_costs_nothing(self):
        plan = discovery.clean_plan([("a", 25), ("b", 10)])
        with mock.patch.object(apify_runner, "is_cached", side_effect=lambda actor, run_input: run_input["resultsPerPage"] == 25):
            half = discovery.estimate(plan)
        self.assertEqual((half["cached"], half["usd"]), (False, round(10 * 0.0037 + 0.001, 4)))
        with mock.patch.object(apify_runner, "is_cached", return_value=True):
            free = discovery.estimate(plan)
        self.assertEqual((free["cached"], free["usd"], free["list_usd"]), (True, 0.0, round(35 * 0.0037 + 2 * 0.001, 4)))  # and what it would cost otherwise


class SearchApiTest(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.aid = self.run_analysis(website_url=SITE, facebook_url="https://www.facebook.com/afteryoucafe")["id"]
        self.actor = mock.patch.object(apify_runner, "run_actor", return_value=([video("amy"), video("amy", days_ago=5), video("bob", lang="en")], 0.28, False))
        self.account = mock.patch("app.clients.apify_account", return_value={"remaining_usd": 4.0})
        self.sorter = mock.patch.object(discovery.llm, "complete", side_effect=labelled(bob="shop"))
        self.sort = self.sorter.start()
        self.addCleanup(self.sorter.stop)
        self.run = self.actor.start()
        self.account.start()
        self.addCleanup(self.actor.stop)
        self.addCleanup(self.account.stop)
        self.m["spawn"].side_effect = lambda fn, *a: fn(*a)

    PLAN = [{"hashtag": "ของหวาน", "videos": 25}, {"hashtag": "#คาเฟ่กรุงเทพ", "videos": 25}, {"hashtag": "ขนมหวาน", "videos": 25}]

    def search(self, plan=None):
        return self.client.post(f"/api/analyses/{self.aid}/creators/search", json={"plan": plan or self.PLAN})

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
        self.assertEqual(state["creators"]["plan"], [{"hashtag": h, "videos": 25} for h in ("ของหวาน", "คาเฟ่กรุงเทพ", "ขนมหวาน")])

    def test_hashtags_with_different_counts_run_separately_and_the_costs_add_up(self):
        self.run.side_effect = [([video("amy"), video("bob")], 0.1, False), ([video("amy", days_ago=5)], 0.05, True)]
        self.search([{"hashtag": "a", "videos": 25}, {"hashtag": "b", "videos": 10}])
        self.assertEqual([c.args[2]["resultsPerPage"] for c in self.run.call_args_list], [25, 10])
        creators = self.get(self.aid)["creators"]
        self.assertEqual((creators["videos"], creators["found"], creators["usd"], creators["cached"]), (3, 2, 0.15, False))
        self.assertEqual(creators["hashtags"], ["a", "b"])
    def test_the_filtered_list_comes_from_the_stored_creators_for_free(self):
        self.search()
        self.run.reset_mock()
        listing = self.client.get(f"/api/analyses/{self.aid}/creators").json()
        self.assertEqual((listing["total"], [c["username"] for c in listing["kept"]], listing["dropped"]["thai"]), (2, ["amy"], 1))
        every = self.client.get(f"/api/analyses/{self.aid}/creators", params={"thai_min": 0, "skip_shops": False}).json()
        self.assertEqual(len(every["kept"]), 2)
        self.run.assert_not_called()

    def test_estimate_returns_the_price_and_the_credits_left(self):
        res = self.client.post(f"/api/analyses/{self.aid}/creators/estimate", json={"plan": [{"hashtag": "x", "videos": 40}, {"hashtag": "y", "videos": 40}]}).json()
        self.assertEqual((res["estimate"]["videos"], res["estimate"]["usd"], res["account"]["remaining_usd"]), (80, round(80 * 0.0037 + 0.001, 4), 4.0))
        self.run.assert_not_called()

    def test_refuses_what_it_cannot_afford_or_cannot_search(self):
        with mock.patch("app.clients.apify_account", return_value={"remaining_usd": 0.05}):
            res = self.search()
        self.assertEqual(res.status_code, 400)
        self.assertIn("$0.05", res.json()["detail"]["message"])
        for bad in ([], [{"hashtag": "a", "videos": 0}], [{"hashtag": "a", "videos": 101}], [{"hashtag": f"t{i}", "videos": 100} for i in range(6)]):
            res = self.search(bad) if bad else self.client.post(f"/api/analyses/{self.aid}/creators/search", json={"plan": []})
            self.assertEqual((res.status_code, res.json()["detail"]["field"]), (400, "plan"), bad)
        self.assertEqual(self.client.post("/api/analyses/nope/creators/search", json={"plan": self.PLAN}).status_code, 404)
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

    def test_pictures_are_fetched_once_by_the_server_and_then_kept(self):
        self.search()
        with mock.patch.object(discovery.logos, "fetch", return_value=("image/jpeg", b"JPEG")) as fetch:
            url = f"/api/analyses/{self.aid}/creators/amy/picture"
            first = self.client.get(f"{url}/avatar")
            self.assertEqual((first.status_code, first.content, first.headers["content-type"]), (200, b"JPEG", "image/jpeg"))
            self.assertEqual(self.client.get(f"{url}/0").status_code, 200)
            self.client.get(f"{url}/avatar")
            self.assertEqual([c.args[1] for c in fetch.call_args_list], ["https://cdn.example/amy/avatar.jpg", "https://cdn.example/amy/cover.jpg"])
        with mock.patch.object(discovery.logos, "fetch", return_value=None):
            self.assertEqual(self.client.get(f"{url}/1").status_code, 404)  # nothing to fetch for a video that isn't there
        for bad in ("/creators/nobody/picture/avatar", "/creators/amy/picture/9", "/creators/amy/picture/x"):
            self.assertEqual(self.client.get(f"/api/analyses/{self.aid}{bad}").status_code, 404, bad)

    def test_refreshing_the_brand_pictures_keeps_the_creator_pictures(self):
        self.search()
        with mock.patch.object(discovery.logos, "fetch", return_value=("image/png", b"PNG")):
            self.client.get(f"/api/analyses/{self.aid}/creators/amy/picture/avatar")
        discovery.media.save_all(self.aid, [])
        self.assertIsNotNone(discovery.media.load(self.aid, "c-amy-avatar"))
        self.assertEqual(self.client.get(f"/api/analyses/{self.aid}/media/c-amy-avatar").status_code, 404)  # not reachable as brand media

    def test_one_creator_can_be_read_for_the_detail_page(self):
        self.search()
        res = self.client.get(f"/api/analyses/{self.aid}/creators/amy").json()
        self.assertEqual((res["username"], res["has_avatar"], len(res["samples"])), ("amy", True, 2))
        self.assertEqual(self.client.get(f"/api/analyses/{self.aid}/creators/zed").status_code, 404)

    def test_shops_are_labelled_hidden_by_default_and_the_model_cost_is_added(self):
        before = self.get(self.aid)["cost"]
        self.search()
        everyone = self.client.get(f"/api/analyses/{self.aid}/creators", params={"thai_min": 0, "skip_shops": False}).json()["kept"]
        self.assertEqual({c["username"]: (c["kind"], c["competitor"], c["kind_reason"]) for c in everyone},
                         {"amy": ("creator", False, "bio sells cakes"), "bob": ("shop", True, "bio sells cakes")})
        listing = self.client.get(f"/api/analyses/{self.aid}/creators", params={"thai_min": 0}).json()
        self.assertEqual(([c["username"] for c in listing["kept"]], listing["dropped"]["shops"]), (["amy"], 1))
        after = self.get(self.aid)
        self.assertEqual((after["creators"]["classify_error"], after["creators"]["phase"]), (None, None))
        self.assertEqual((after["cost"]["llm_input_tokens"] - before["llm_input_tokens"], round(after["cost"]["llm_usd"] - before["llm_usd"], 6)), (500, 0.0004))

    def test_searching_again_keeps_the_labels_without_asking_the_model_again(self):
        self.search()
        self.sort.reset_mock()
        self.search()
        self.sort.assert_not_called()
        self.assertEqual(self.client.get(f"/api/analyses/{self.aid}/creators/bob").json()["kind"], "shop")

    def test_a_model_failure_does_not_fail_the_search_or_hide_anything(self):
        self.sort.side_effect = UpstreamError("LLM provider error 402")
        self.search()
        creators = self.get(self.aid)["creators"]
        self.assertEqual((creators["status"], creators["found"]), ("done", 2))
        self.assertIn("402", creators["classify_error"])
        self.assertEqual(len(self.client.get(f"/api/analyses/{self.aid}/creators", params={"thai_min": 0}).json()["kept"]), 2)

    def test_an_incomplete_labelling_is_reported(self):
        self.sort.side_effect = lambda http, cfg, system, user, max_tokens=1500: Completion('[{"u": "amy", "kind": "creator"}]', "m", 1, 1, 1, None)
        self.search()
        self.assertIn("1 of 2", self.get(self.aid)["creators"]["classify_error"])

    def test_old_analyses_without_the_field_still_open(self):
        analyses.update(self.aid, lambda s: s.pop("creators"))
        self.assertEqual(self.get(self.aid)["creators"]["status"], "idle")


if __name__ == "__main__":
    unittest.main()
