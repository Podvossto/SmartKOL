import json
import unittest
from unittest import mock

from app import apify_runner, discovery, scoring
from app.clients import UpstreamError
from app.llm import Completion
from tests.test_analyses import SITE, ApiTestCase
from tests.test_discovery import labelled, video
from tests.test_enrichment import post


def creator(user, followers=50_000, **metrics):
    m = {"videos": 10, "median_views": 5000, "median_er": 0.05, "posts_per_week": 3.0, "days_since_last_post": 2, "ad_share": 0.0,
         "shop_share": 0.0, "views_cv": 0.4, **metrics}
    return {"username": user, "followers": followers, "metrics": m}


class WeightsTest(unittest.TestCase):
    def test_weights_become_whole_numbers_that_add_up_to_100(self):
        self.assertEqual(scoring.clean_weights({"relevance": 40, "engagement": 25, "audience": 20, "activity": 15}), {"relevance": 40, "engagement": 25, "audience": 20, "activity": 15})
        w = scoring.clean_weights({"relevance": 1, "engagement": 1, "audience": 1, "activity": 0})
        self.assertEqual((sum(w.values()), w["activity"]), (100, 0))
        with self.assertRaises(scoring.ScoreError):
            scoring.clean_weights({"relevance": 0, "engagement": 0, "audience": 0, "activity": 0})

    def test_total_and_rank_follow_the_weights_and_skip_the_unscored(self):
        a = {"username": "a", "score": {"relevance": 90, "engagement": 20, "audience": 50, "activity": 50}}
        b = {"username": "b", "score": {"relevance": 40, "engagement": 90, "audience": 50, "activity": 50}}
        c = {"username": "c"}
        by_rel = {x["username"]: x for x in scoring.attach([a, b, c], {"relevance": 100, "engagement": 0, "audience": 0, "activity": 0})}
        self.assertEqual((by_rel["a"]["total"], by_rel["a"]["rank"], by_rel["b"]["rank"], by_rel["c"]["total"]), (90, 1, 2, None))
        by_eng = {x["username"]: x for x in scoring.attach([a, b], {"relevance": 0, "engagement": 100, "audience": 0, "activity": 0})}
        self.assertEqual((by_eng["b"]["rank"], by_eng["a"]["rank"]), (1, 2))


class AxesTest(unittest.TestCase):
    def test_engagement_is_a_percentile_among_creators_of_the_same_size(self):
        pool = [creator(f"p{i}", median_er=0.01 * (i + 1)) for i in range(4)] + [creator("big", followers=2_000_000, median_er=0.001)]
        top, bottom = pool[3], pool[0]
        self.assertGreater(scoring.engagement(top, pool)[0], scoring.engagement(bottom, pool)[0])
        self.assertIn("micro creators", scoring.engagement(top, pool)[1])
        self.assertIn("all creators", scoring.engagement(pool[4], pool)[1])  # alone in its size: compared with everyone

    def test_activity_rewards_steady_recent_posting_and_flags_ads_and_inflated_followers(self):
        good, _, g_flags = scoring.activity(creator("a"))
        self.assertEqual((good, g_flags), (100, []))
        stale = scoring.activity(creator("b", days_since_last_post=90, posts_per_week=0.2))[0]
        self.assertLess(stale, 50)
        adsy = scoring.activity(creator("c", ad_share=0.6))
        self.assertTrue(any("ads" in f for f in adsy[2]))
        fake = scoring.activity(creator("d", followers=5_000_000))
        self.assertTrue(any("inflated" in f for f in fake[2]))
        self.assertLess(fake[0], good)

    def test_an_unsafe_creator_is_capped_however_well_they_fit(self):
        score, flags = scoring.relevance({"category": 95, "style": 95, "product": 95, "safety": 20})
        self.assertEqual((score, len(flags)), (40, 1))
        self.assertEqual(scoring.relevance({"category": 80, "style": 60, "product": 70, "safety": 90}), (75, []))


def reply(**rows):
    def fn(http, cfg, system, user, max_tokens=1500):
        items = [{"u": u, "category": 80, "style": 70, "product": 60, "safety": 90, "audience": 65, "confidence": "medium",
                  "reason": f"{u} fits", "audience_reason": "bio says students", **over} for u, over in rows.items()]
        return Completion(json.dumps(items), "m", 1, 800, 300, 0.0006)
    return fn


class JudgeTest(unittest.TestCase):
    cfg = mock.Mock(model="m")
    profile = {"brand_name": "B", "category": "cafe", "price_tier": "mid", "products": ["tea"], "audience": {"description": "d", "age_range": "20-30", "interests": []},
               "voice": {"traits": ["fun"], "style": "s"}, "creator_fit": {"niches": ["cafe"], "content_styles": ["vlog"], "audience_match": "students", "language": "Thai", "avoid": ["shops"]}}

    def creators(self, *names):
        return [dict(creator(n), nickname=n, bio="รีวิว", hashtags=["x"], samples=[{"text": "caption"}], kind="creator") for n in names]

    def test_each_answer_is_read_back_and_bad_ones_get_no_score(self):
        with mock.patch.object(scoring.llm, "complete", side_effect=reply(amy={}, bob={"safety": "high"}, ghost={})):
            judged, usage = scoring.judge(None, self.cfg, self.profile, self.creators("amy", "bob"))
        self.assertEqual(list(judged), ["amy"])  # bob's safety is not a number; ghost was never asked about
        self.assertEqual((judged["amy"]["audience"], judged["amy"]["confidence"], usage["cost_usd"]), (65, "medium", 0.0006))

    def test_scores_are_kept_in_range(self):
        with mock.patch.object(scoring.llm, "complete", side_effect=reply(amy={"audience": 140, "style": -5})):
            judged, _ = scoring.judge(None, self.cfg, self.profile, self.creators("amy"))
        self.assertEqual((judged["amy"]["audience"], judged["amy"]["style"]), (100, 0))

    def test_creators_are_sent_in_batches(self):
        names = [f"u{i}" for i in range(23)]
        with mock.patch.object(scoring.llm, "complete", side_effect=reply(**{n: {} for n in names})) as complete:
            judged, _ = scoring.judge(None, self.cfg, self.profile, self.creators(*names))
        self.assertEqual((complete.call_count, len(judged)), (3, 23))


class ScoreApiTest(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.aid = self.run_analysis(website_url=SITE, facebook_url="https://www.facebook.com/afteryoucafe")["id"]
        self.m["spawn"].side_effect = lambda fn, *a: fn(*a)
        self.actor = mock.patch.object(apify_runner, "run_actor", return_value=([video("amy"), video("bob")], 0.28, False)).start()
        mock.patch("app.clients.apify_account", return_value={"remaining_usd": 4.0}).start()
        mock.patch.object(discovery.llm, "complete", side_effect=labelled()).start()
        self.addCleanup(mock.patch.stopall)
        self.client.post(f"/api/analyses/{self.aid}/creators/search", json={"plan": [{"hashtag": "a", "videos": 10}]})
        self.actor.return_value = ([post("amy", 2, 900, likes=90), post("amy", 9, 1100, likes=110), post("bob", 3, 500, likes=5)], 0.04, False)

    def read(self):
        return self.client.post(f"/api/analyses/{self.aid}/creators/enrich", json={"usernames": ["amy", "bob"], "videos": 5})

    def score(self, **body):
        return self.client.post(f"/api/analyses/{self.aid}/creators/score", json=body)

    def listing(self):
        return self.client.get(f"/api/analyses/{self.aid}/creators", params={"thai_min": 0, "skip_shops": False, "min_followers": 0}).json()

    def test_scoring_needs_videos_to_have_been_read_first(self):
        res = self.score()
        self.assertEqual((res.status_code, res.json()["detail"]["field"]), (400, "usernames"))
        self.read()
        self.assertEqual(self.score(usernames=["ghost"]).status_code, 400)

    def test_scores_rank_the_creators_and_the_model_is_asked_only_once(self):
        self.read()
        with mock.patch.object(scoring.llm, "complete", side_effect=reply(amy={"category": 90, "style": 90, "product": 90}, bob={})) as complete:
            self.assertEqual(self.score().status_code, 200)
            state = self.get(self.aid)
            self.assertEqual((state["creators"]["scoring"]["status"], state["creators"]["scoring"]["scored"], state["cost"]["llm_usd"] > 0), ("done", 2, True))
            ranked = {c["username"]: c for c in self.listing()["kept"]}
            self.assertEqual((ranked["amy"]["rank"], ranked["bob"]["rank"]), (1, 2))
            self.assertTrue(set(ranked["amy"]["score"]) >= {"relevance", "engagement", "audience", "activity", "reason", "confidence", "flags"})
            self.score()
            self.assertEqual(complete.call_count, 1)  # judged once, not again
            self.score(redo=True)
            self.assertEqual(complete.call_count, 2)

    def test_changing_the_weights_changes_the_ranking_for_free(self):
        self.read()
        with mock.patch.object(scoring.llm, "complete", side_effect=reply(amy={"category": 90, "style": 90, "product": 90}, bob={"category": 20, "style": 20, "product": 20})) as complete:
            self.score()
            res = self.client.put(f"/api/analyses/{self.aid}/creators/weights", json={"relevance": 0, "engagement": 0, "audience": 0, "activity": 3})
            self.assertEqual(res.json()["weights"]["activity"], 100)
            self.assertEqual(self.listing()["weights"]["activity"], 100)
            self.assertEqual(complete.call_count, 1)
        bad = self.client.put(f"/api/analyses/{self.aid}/creators/weights", json={"relevance": 0, "engagement": 0, "audience": 0, "activity": 0})
        self.assertEqual(bad.status_code, 400)

    def test_a_model_failure_is_reported_and_nothing_is_scored(self):
        self.read()
        with mock.patch.object(scoring.llm, "complete", side_effect=UpstreamError("LLM provider error 402")):
            self.score()
        scoring_state = self.get(self.aid)["creators"]["scoring"]
        self.assertEqual((scoring_state["status"], scoring_state["error"]), ("error", "LLM provider error 402"))
        self.assertNotIn("score", self.client.get(f"/api/analyses/{self.aid}/creators/amy").json())

    def test_reading_again_and_searching_again_keep_the_judgement(self):
        self.read()
        with mock.patch.object(scoring.llm, "complete", side_effect=reply(amy={}, bob={})):
            self.score()
        self.read()
        self.assertEqual(self.client.get(f"/api/analyses/{self.aid}/creators/amy").json()["score"]["reason"], "amy fits")
        self.actor.return_value = ([video("amy"), video("bob")], 0.1, False)
        self.client.post(f"/api/analyses/{self.aid}/creators/search", json={"plan": [{"hashtag": "b", "videos": 10}]})
        amy = self.client.get(f"/api/analyses/{self.aid}/creators/amy").json()
        self.assertEqual((amy["rank"] in (1, 2), amy["score"]["reason"]), (True, "amy fits"))


if __name__ == "__main__":
    unittest.main()
