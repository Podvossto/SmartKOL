import csv
import io
import unittest
from unittest import mock

from app import apify_runner, discovery, exporting
from tests.test_analyses import SITE, ApiTestCase
from tests.test_discovery import labelled, video


def rows(text):
    return list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))


class CsvTest(unittest.TestCase):
    def test_ranked_first_then_the_rest_and_no_bio(self):
        a = {"username": "a", "nickname": "Alpha", "url": "https://www.tiktok.com/@a", "followers": 10, "bio": "งานติดต่อ a@b.com โทร 081-234-5678", "median_views": 5, "last_post": "2026-10-01T00:00:00+00:00"}
        b = dict(a, username="b", nickname="Beta", followers=99, rank=1, total=80, score={"relevance": 90, "engagement": 70, "audience": 60, "activity": 50, "confidence": "low", "viewers": {"age": "18-24", "gender": "mostly women", "interests": ["Desserts", "Cafes"]}, "reason": "good", "audience_reason": "x", "flags": ["w1", "w2"]},
                 metrics={"median_views": 700, "median_er": 0.0512, "posts_per_week": 3.5, "last_post": "2026-10-29T10:00:00+00:00", "ad_share": 0.2, "videos": 5})
        text = exporting.creators_csv([a, b])
        self.assertTrue(text.startswith("\ufeff"))
        table = rows(text)
        head = table[0]
        self.assertNotIn("bio", head)
        self.assertEqual([r[1] for r in table[1:]], ["b", "a"])
        first = dict(zip(head, table[1]))
        self.assertEqual((first["rank"], first["total_score"], first["typical_views"], first["engagement_rate_pct"], first["last_post"], first["warnings"]), ("1", "80", "700", "5.1", "2026-10-29", "w1 | w2"))
        self.assertEqual(dict(zip(head, table[2]))["total_score"], "")
        self.assertEqual((first["audience_age_estimated"], first["audience_gender_estimated"], first["audience_interests_estimated"]), ("18-24", "mostly women", "Desserts, Cafes"))
        self.assertEqual(first["contact_in_bio"], "a@b.com | 081-234-5678")  # the bio is not in the file, but the way to reach them is
        self.assertEqual(dict(zip(head, table[2]))["audience_age_estimated"], "")  # a creator that was never scored has no guess

    def test_a_cell_can_never_be_a_formula(self):
        c = {"username": "x", "nickname": "=HYPERLINK(\"http://evil\")", "url": "u", "followers": 1, "median_views": 1, "last_post": None}
        self.assertEqual(rows(exporting.creators_csv([c]))[1][2], "'=HYPERLINK(\"http://evil\")")


class ExportApiTest(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.aid = self.run_analysis(website_url=SITE, facebook_url="https://www.facebook.com/afteryoucafe")["id"]
        self.m["spawn"].side_effect = lambda fn, *a: fn(*a)
        mock.patch.object(apify_runner, "run_actor", return_value=([video("amy"), video("bob", lang="en")], 0.1, False)).start()
        mock.patch("app.clients.apify_account", return_value={"remaining_usd": 4.0}).start()
        mock.patch.object(discovery.llm, "complete", side_effect=labelled()).start()
        self.addCleanup(mock.patch.stopall)
        self.client.post(f"/api/analyses/{self.aid}/creators/search", json={"plan": [{"hashtag": "a", "videos": 10}]})

    def test_the_file_follows_the_filters_and_costs_nothing(self):
        res = self.client.get(f"/api/analyses/{self.aid}/creators/export.csv")
        self.assertEqual((res.status_code, res.headers["content-type"].split(";")[0]), (200, "text/csv"))
        self.assertIn("attachment", res.headers["content-disposition"])
        self.assertEqual([r[1] for r in rows(res.text)[1:]], ["amy"])  # bob's captions are not Thai
        every = self.client.get(f"/api/analyses/{self.aid}/creators/export.csv", params={"thai_min": 0, "min_followers": 0})
        self.assertEqual(len(rows(every.text)) - 1, 2)
        self.assertEqual({r[3] for r in rows(every.text)[1:]}, {"https://www.tiktok.com/@amy", "https://www.tiktok.com/@bob"})

    def test_nothing_to_export_says_so(self):
        res = self.client.get(f"/api/analyses/{self.aid}/creators/export.csv", params={"min_followers": 10**9})
        self.assertEqual(res.status_code, 409)
        self.assertEqual(self.client.get("/api/analyses/nope/creators/export.csv").status_code, 404)


if __name__ == "__main__":
    unittest.main()
