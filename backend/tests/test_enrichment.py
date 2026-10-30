import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from app import analyses, apify_runner, discovery, enrichment
from app.clients import UpstreamError
from tests.test_analyses import SITE, ApiTestCase
from tests.test_discovery import labelled, video

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)


def post(user, days_ago, views=1000, likes=0, comments=0, shares=0, **extra):
    return {"authorMeta": {"name": user}, "createTimeISO": (NOW - timedelta(days=days_ago)).isoformat(), "playCount": views,
            "diggCount": likes, "commentCount": comments, "shareCount": shares, **extra}


class MetricsTest(unittest.TestCase):
    def test_numbers_come_from_the_latest_videos(self):
        vids = [post("amy", 1, 1000, likes=80, comments=10, shares=10), post("amy", 8, 2000, likes=100, comments=50, shares=50, isAd=True),
                post("amy", 15, 4000, likes=40, comments=0, shares=0, hasTikTokShopProduct=True), post("amy", 22, 500, isSponsored=True)]
        m = enrichment.metrics(vids, now=NOW)
        self.assertEqual((m["videos"], m["median_views"]), (4, 1500))
        self.assertEqual(m["median_er"], 0.055)  # per video 0.1, 0.1, 0.01, 0.0 -> median of the four
        self.assertEqual(m["posts_per_week"], 1.0)  # 3 gaps over 21 days
        self.assertEqual((m["days_since_last_post"], m["ad_share"], m["shop_share"]), (1, 0.5, 0.25))

    def test_a_single_video_or_zero_views_gives_no_made_up_numbers(self):
        m = enrichment.metrics([post("amy", 3, views=0)], now=NOW)
        self.assertEqual((m["median_er"], m["posts_per_week"], m["median_views"]), (None, None, 0))

    def test_apply_fills_the_creators_found_and_makes_last_post_real(self):
        creators = discovery.group_creators([video("amy", days_ago=40), video("bob")])
        filled = enrichment.apply(creators, [post("amy", 2), post("amy", 9), post("ghost", 1)])
        amy = next(c for c in creators if c["username"] == "amy")
        bob = next(c for c in creators if c["username"] == "bob")
        self.assertEqual((filled, "metrics" in bob), (1, False))
        self.assertEqual(amy["last_post"], amy["metrics"]["last_post"])
        self.assertEqual(amy["metrics"]["videos"], 2)


class CleanTest(unittest.TestCase):
    known = {"amy", "bob"}

    def test_the_choice_is_cleaned_and_limited(self):
        self.assertEqual(enrichment.clean(["@bob", "amy", "bob"], 10, self.known), ["amy", "bob"])
        for users, videos in (([], 10), (["amy"], 2), (["amy"], 31), (["ghost"], 10), ([f"u{i}" for i in range(51)], 3)):
            with self.assertRaises(enrichment.EnrichError, msg=(users, videos)):
                enrichment.clean(users, videos, self.known | (set(users) if len(users) > 5 else set()))

    def test_estimate_is_every_video_plus_the_start_fee_and_free_when_cached(self):
        e = enrichment.estimate(["amy", "bob"], 10)
        self.assertEqual((e["videos"], e["usd"]), (20, round(20 * 0.0037 + 0.001, 4)))
        with mock.patch.object(apify_runner, "is_cached", return_value=True):
            free = enrichment.estimate(["amy", "bob"], 10)
        self.assertEqual((free["usd"], free["list_usd"], free["cached"]), (0.0, e["list_usd"], True))


class EnrichApiTest(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.aid = self.run_analysis(website_url=SITE, facebook_url="https://www.facebook.com/afteryoucafe")["id"]
        self.m["spawn"].side_effect = lambda fn, *a: fn(*a)
        self.run = mock.patch.object(apify_runner, "run_actor", return_value=([video("amy"), video("bob")], 0.28, False)).start()
        mock.patch("app.clients.apify_account", return_value={"remaining_usd": 4.0}).start()
        mock.patch.object(discovery.llm, "complete", side_effect=labelled()).start()
        self.addCleanup(mock.patch.stopall)
        self.client.post(f"/api/analyses/{self.aid}/creators/search", json={"plan": [{"hashtag": "a", "videos": 10}]})
        self.run.reset_mock()
        self.run.return_value = ([post("amy", 2, 900, likes=90), post("amy", 9, 1100, likes=110), post("bob", 3)], 0.0407, False)

    def enrich(self, users=("amy", "bob"), videos=10):
        return self.client.post(f"/api/analyses/{self.aid}/creators/enrich", json={"usernames": list(users), "videos": videos})

    def test_reads_the_latest_videos_stores_metrics_and_adds_the_cost(self):
        before = self.get(self.aid)["cost"]["apify_usd"]
        self.assertEqual(self.enrich().status_code, 200)
        called = self.run.call_args.args[2]
        self.assertEqual((called["profiles"], called["resultsPerPage"], called["profileSorting"]), (["amy", "bob"], 10, "latest"))
        state = self.get(self.aid)
        self.assertEqual((state["creators"]["enrich"]["status"], state["creators"]["enrich"]["usd"]), ("done", 0.0407))
        self.assertEqual(state["cost"]["apify_usd"], round(before + 0.0407, 5))
        amy = self.client.get(f"/api/analyses/{self.aid}/creators/amy").json()
        self.assertEqual((amy["metrics"]["videos"], amy["metrics"]["median_views"], amy["metrics"]["median_er"]), (2, 1000, 0.1))

    def test_creators_without_videos_are_reported_not_invented(self):
        self.run.return_value = ([post("amy", 2)], 0.01, False)
        self.enrich()
        enrich = self.get(self.aid)["creators"]["enrich"]
        self.assertEqual((enrich["missing"], enrich["filled"]), (["bob"], 1))

    def test_estimate_and_refusals(self):
        res = self.client.post(f"/api/analyses/{self.aid}/creators/enrich/estimate", json={"usernames": ["amy"], "videos": 20}).json()
        self.assertEqual((res["estimate"]["usd"], res["account"]["remaining_usd"]), (round(20 * 0.0037 + 0.001, 4), 4.0))
        with mock.patch("app.clients.apify_account", return_value={"remaining_usd": 0.01}):
            self.assertEqual(self.enrich().status_code, 400)
        for users, videos in (([], 10), (["ghost"], 10), (["amy"], 99)):
            res = self.enrich(users, videos)
            self.assertEqual((res.status_code, res.json()["detail"]["field"]), (400, "usernames"))
        self.run.assert_not_called()

    def test_a_failed_read_says_why_and_a_new_search_keeps_the_numbers(self):
        self.run.side_effect = UpstreamError("Apify run failed (x): quota")
        self.enrich()
        self.assertEqual(self.get(self.aid)["creators"]["enrich"]["error"], "Apify run failed (x): quota")
        self.run.side_effect = None
        self.enrich()
        self.run.side_effect = None
        self.run.return_value = ([video("amy"), video("bob")], 0.1, False)
        self.client.post(f"/api/analyses/{self.aid}/creators/search", json={"plan": [{"hashtag": "b", "videos": 10}]})
        amy = self.client.get(f"/api/analyses/{self.aid}/creators/amy").json()
        self.assertEqual(amy["metrics"]["videos"], 2)
        self.assertEqual(self.get(self.aid)["creators"]["enrich"]["status"], "done")


if __name__ == "__main__":
    unittest.main()
