import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import httpx
from fastapi.testclient import TestClient

from app import analyses, apify_runner, crawler, logos, media, preflight
from app.clients import UpstreamError
from app.llm import Completion
from app.main import app
from app.routers.settings import get_http
from tests.test_brand import VALID

GOOD = "https://www.facebook.com/afteryoucafe"
FOREIGN = "https://www.facebook.com/afteryoudessertcafe"
SITE = "https://www.afteryoudessertcafe.com"
NOW = datetime.now(timezone.utc)


def iso(days_ago: int) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat()


def site_data(facebook=(GOOD, FOREIGN)):
    return crawler.SiteData(
        SITE,
        [crawler.Page(SITE, "After You", "Desserts", "# Menu\nHoney toast " * 50), crawler.Page(SITE + "/menu", "Menu", None, "Lava cake")],
        {"facebook": list(facebook), "tiktok": [], "instagram": [], "youtube": [], "line": []},
    )


PAGES = [
    {"facebookUrl": GOOD, "title": "After You | Bangkok", "category": "Dessert Shop", "followers": 355000,
     "website": "http://www.afteryoudessertcafe.com/", "address": "Bangkok, Thailand", "intro": "desserts",
     "profilePictureUrl": "https://scontent.fbcdn.net/logo.jpg"},
    {"facebookUrl": FOREIGN, "title": "AFter You Bangladesh", "category": "Food", "followers": 4214,
     "website": "http://www.afteryoudessertcafe.com/", "address": "Dhaka"},
]
POSTS = [
    {"inputUrl": GOOD, "time": iso(2), "likes": 100, "comments": 5, "shares": 2, "text": "new menu", "url": "https://fb.com/p/1"},
    {"inputUrl": GOOD, "time": iso(9), "likes": 80, "comments": 1, "shares": 0, "text": "promo"},
    {"inputUrl": GOOD, "time": iso(16), "likes": 600, "comments": 50, "shares": 40, "text": "viral toast"},
    {"inputUrl": FOREIGN, "time": iso(2200), "likes": 18, "comments": 5, "shares": 1, "text": "old"},
]


def fake_pages(token, urls):
    return [p for p in PAGES if p["facebookUrl"] in urls], 0.012 * len(urls), False


def fake_posts(token, urls, limit):
    return [p for p in POSTS if p["inputUrl"] in urls][: limit * len(urls)], 0.01, False


def fake_llm(*args, **kwargs):
    return Completion(json.dumps(VALID, ensure_ascii=False), "anthropic/claude-haiku-5.5", 900, 5000, 700, 0.0007)


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        env = mock.patch.dict(os.environ, {"SMARTKOL_DATA_DIR": self.tmp.name, "APIFY_TOKEN": "apify_api_TESTTOKEN",
                                           "LLM_API_KEY": "sk-or-v1-TESTKEY1234", "LLM_PROTOCOL": "openai",
                                           "LLM_BASE_URL": "https://openrouter.ai/api/v1", "LLM_MODEL": "anthropic/claude-haiku-5.5"})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(self.tmp.cleanup)
        patches = {
            "crawl": mock.patch.object(analyses.crawler, "crawl_site", side_effect=lambda url: site_data()),
            "pages": mock.patch.object(apify_runner, "facebook_pages", side_effect=fake_pages),
            "posts": mock.patch.object(apify_runner, "facebook_posts", side_effect=fake_posts),
            "llm": mock.patch.object(analyses.brand.llm, "complete", side_effect=fake_llm),
            "spawn": mock.patch.object(analyses, "spawn", side_effect=lambda fn, *a: fn(*a)),
            "site_check": mock.patch.object(preflight, "check_website", side_effect=lambda url, http: preflight.Check(url)),
            "fb_check": mock.patch.object(preflight, "check_facebook", side_effect=lambda url: preflight.Check(url)),
            "logo": mock.patch.object(logos, "find", return_value=None),  # no real network in tests
        }
        self.m = {name: patch.start() for name, patch in patches.items()}
        for patch in patches.values():
            self.addCleanup(patch.stop)
        app.dependency_overrides[get_http] = lambda: None
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)

    def start(self, **body):
        return self.client.post("/api/analyses", json=body)

    def run_analysis(self, **body) -> dict:
        res = self.start(**body)
        self.assertEqual(res.status_code, 200, res.text)
        return self.client.get(f"/api/analyses/{res.json()['id']}").json()

    def get(self, aid: str) -> dict:
        return self.client.get(f"/api/analyses/{aid}").json()


class StartValidationTest(ApiTestCase):
    def detail(self, res):
        self.assertEqual(res.status_code, 400, res.text)
        return res.json()["detail"]

    def test_needs_at_least_one_input(self):
        for body in ({}, {"website_url": "  ", "facebook_url": ""}):
            self.assertEqual(self.detail(self.start(**body))["field"], "website_url")

    def test_refuses_to_start_without_credentials(self):
        with mock.patch.dict(os.environ, {"APIFY_TOKEN": ""}):
            self.assertIn("Apify", self.detail(self.start(website_url=SITE, find_facebook=True))["message"])
        with mock.patch.dict(os.environ, {"LLM_API_KEY": ""}):
            self.assertIn("language model", self.detail(self.start(website_url=SITE, find_facebook=True))["message"])

    def test_unusable_website_links_are_blamed_on_the_website_field_and_cost_nothing(self):
        self.m["site_check"].side_effect = preflight.LinkError("That page doesn't exist (HTTP 404). Check the address.")
        d = self.detail(self.start(website_url=SITE + "/nope", facebook_url=GOOD))
        self.assertEqual((d["field"], d["message"]), ("website_url", "That page doesn't exist (HTTP 404). Check the address."))
        self.assertEqual(self.detail(self.start(website_url="http://localhost:8000"))["field"], "website_url")
        for name in ("pages", "posts", "llm", "crawl", "fb_check"):
            self.m[name].assert_not_called()

    def test_unusable_facebook_links_are_blamed_on_the_facebook_field_and_cost_nothing(self):
        d = self.detail(self.start(facebook_url="https://www.facebook.com/sharer/sharer.php?u=1"))
        self.assertEqual(d["field"], "facebook_url")
        self.m["fb_check"].side_effect = preflight.LinkError("We couldn't find a public Facebook page at this address.")
        self.assertEqual(self.detail(self.start(facebook_url=GOOD))["field"], "facebook_url")
        for name in ("pages", "posts", "llm", "crawl"):
            self.m[name].assert_not_called()

    def test_a_bad_website_stops_before_facebook_is_even_checked(self):
        self.m["site_check"].side_effect = preflight.LinkError("x")
        self.start(website_url=SITE, facebook_url=GOOD)
        self.m["fb_check"].assert_not_called()

    def test_warnings_from_the_link_checks_are_kept(self):
        self.m["site_check"].side_effect = lambda url, http: preflight.Check(url, "This website restricts automated visitors.")
        s = self.run_analysis(website_url=SITE, find_facebook=True)
        self.assertEqual(s["warnings"], ["This website restricts automated visitors."])

    def test_the_checked_final_address_is_the_one_analysed(self):
        self.m["site_check"].side_effect = lambda url, http: preflight.Check("https://www.brand.com/th")
        self.assertEqual(self.run_analysis(website_url="brand.com")["website_url"], "https://www.brand.com/th")


class WebsiteOnlyFlowTest(ApiTestCase):
    def test_discovery_lists_candidates_with_details_and_recommends_the_live_page(self):
        s = self.run_analysis(website_url=SITE, find_facebook=True)
        self.assertEqual((s["mode"], s["status"]), ("website", "awaiting_facebook"))
        self.assertNotIn("internal", s)
        good, foreign = s["facebook_candidates"]
        self.assertEqual([c["url"] for c in s["facebook_candidates"]], [GOOD, FOREIGN])
        self.assertEqual((good["title"], good["followers"], good["source"]), ("After You | Bangkok", 355000, "website"))
        self.assertEqual(good["warnings"], [])
        self.assertTrue(any("over a year" in w for w in foreign["warnings"]))
        self.assertEqual(s["recommended"], GOOD)
        self.assertEqual([x["state"] for x in s["steps"]], ["done", "done", "done"])
        self.assertEqual(len(s["website"]["pages"]), 2)

    def test_no_facebook_link_on_the_site_waits_for_the_user(self):
        self.m["crawl"].side_effect = lambda url: site_data(facebook=())
        s = self.run_analysis(website_url=SITE, find_facebook=True)
        self.assertEqual((s["status"], s["facebook_candidates"], s["recommended"]), ("awaiting_facebook", [], None))
        self.m["pages"].assert_not_called()

    def test_confirming_a_page_builds_a_combined_profile_with_a_summary_per_source(self):
        aid = self.run_analysis(website_url=SITE, find_facebook=True)["id"]
        self.assertEqual(self.client.post(f"/api/analyses/{aid}/profile", json={"facebook_url": GOOD}).status_code, 200)
        s = self.get(aid)
        self.assertEqual((s["status"], s["selected_facebook"]), ("done", GOOD))
        self.assertEqual(sorted(s["profile"]["by_source"]), ["facebook", "website"])
        self.assertEqual(s["facebook"]["stats"]["posts_read"], 3)
        self.assertEqual(s["facebook"]["title"], "After You | Bangkok")
        self.assertAlmostEqual(s["cost"]["llm_usd"], 0.0007)
        prompt = self.m["llm"].call_args.args[3]
        self.assertIn("new menu", prompt)
        self.assertIn("WEBSITE PAGE", prompt)

    def test_website_only_profile_has_no_facebook_summary(self):
        aid = self.run_analysis(website_url=SITE, find_facebook=True)["id"]
        self.client.post(f"/api/analyses/{aid}/profile", json={"facebook_url": None})
        s = self.get(aid)
        self.assertEqual((s["status"], s["steps"][0]["state"], list(s["profile"]["by_source"])), ("done", "skipped", ["website"]))
        self.assertIsNone(s["facebook"])
        self.assertNotIn("FACEBOOK PAGE", self.m["llm"].call_args.args[3])

    def test_pasted_unknown_page_is_looked_up_before_profiling(self):
        aid = self.run_analysis(website_url=SITE, find_facebook=True)["id"]
        other = "https://www.facebook.com/afteryou.th"
        with mock.patch.object(apify_runner, "facebook_pages", return_value=([{"facebookUrl": other, "title": "After You TH", "followers": 10}], 0.0, False)) as pages:
            self.client.post(f"/api/analyses/{aid}/profile", json={"facebook_url": other})
        pages.assert_called_once()
        self.assertEqual(self.get(aid)["status"], "done")

    def test_confirm_validation(self):
        self.assertEqual(self.client.post("/api/analyses/nope/profile", json={}).status_code, 404)
        aid = self.run_analysis(website_url=SITE, find_facebook=True)["id"]
        bad = self.client.post(f"/api/analyses/{aid}/profile", json={"facebook_url": "https://example.com/x"})
        self.assertEqual(bad.status_code, 400)
        self.m["crawl"].side_effect = UpstreamError("down")
        failed = self.run_analysis(website_url=SITE, find_facebook=True)["id"]
        self.assertEqual(self.client.post(f"/api/analyses/{failed}/profile", json={}).status_code, 409)

    def test_crawl_failure_becomes_a_readable_error(self):
        self.m["crawl"].side_effect = UpstreamError("Could not open the website: timeout")
        s = self.run_analysis(website_url=SITE, find_facebook=True)
        self.assertEqual((s["status"], s["error"], s["steps"][0]["state"]), ("error", "Could not open the website: timeout", "error"))

    def test_unexpected_failure_does_not_leak_details(self):
        self.m["crawl"].side_effect = RuntimeError("secret apify_api_TESTTOKEN in traceback")
        s = self.run_analysis(website_url=SITE, find_facebook=True)
        self.assertEqual(s["status"], "error")
        self.assertNotIn("TESTTOKEN", json.dumps(s))

    def test_llm_failure_then_retry_resumes_from_the_confirmed_page(self):
        aid = self.run_analysis(website_url=SITE, find_facebook=True)["id"]
        self.m["llm"].side_effect = UpstreamError("LLM provider error 402: no credits")
        self.client.post(f"/api/analyses/{aid}/profile", json={"facebook_url": GOOD})
        s = self.get(aid)
        self.assertEqual((s["status"], s["error"], s["requested_facebook"]), ("error", "LLM provider error 402: no credits", GOOD))
        self.m["llm"].side_effect = fake_llm
        self.assertEqual(self.client.post(f"/api/analyses/{aid}/retry").status_code, 200)
        self.assertEqual(self.get(aid)["status"], "done")
        self.assertEqual(self.m["crawl"].call_count, 1)  # no re-crawl


class DirectFlowTest(ApiTestCase):
    def test_website_and_facebook_together_skip_the_confirmation_step(self):
        s = self.run_analysis(website_url=SITE, facebook_url="facebook.com/afteryoucafe/about")
        self.assertEqual((s["mode"], s["status"]), ("both", "done"))
        self.assertEqual([x["key"] for x in s["steps"]], ["crawl", "facebook", "profile"])
        self.assertTrue(all(x["state"] == "done" for x in s["steps"]))
        self.assertEqual(s["facebook_candidates"], [])
        self.assertEqual(s["selected_facebook"], GOOD)
        self.assertEqual(sorted(s["profile"]["by_source"]), ["facebook", "website"])
        prompt = self.m["llm"].call_args.args[3]
        self.assertIn("WEBSITE PAGE", prompt)
        self.assertIn("FACEBOOK PAGE", prompt)
        self.m["site_check"].assert_called_once()
        self.m["fb_check"].assert_called_once()

    def test_the_pages_last_post_date_comes_from_the_posts_that_were_read(self):
        page = self.run_analysis(facebook_url=GOOD)["facebook"]
        self.assertTrue(page["last_post_at"].startswith(iso(2)[:10]))
        self.assertEqual(page["warnings"], [])  # "No public posts could be read" was only true before the posts were fetched

    def test_an_inactive_page_keeps_its_warning(self):
        with mock.patch.object(apify_runner, "facebook_pages", return_value=([PAGES[1]], 0.0, False)):
            page = self.run_analysis(facebook_url=FOREIGN)["facebook"]
        self.assertTrue(any("over a year" in w for w in page["warnings"]))

    def test_facebook_stats_are_computed_from_the_posts_read(self):
        stats = self.run_analysis(website_url=SITE, facebook_url=GOOD)["facebook"]["stats"]
        self.assertEqual((stats["posts_read"], stats["avg_likes"], stats["avg_comments"], stats["avg_shares"]), (3, 260, 19, 14))
        self.assertEqual(stats["posts_last_30d"], 3)
        self.assertEqual(stats["top_post"]["text"], "viral toast")
        self.assertAlmostEqual(stats["engagement_rate_pct"], round((260 + 19 + 14) / 355000 * 100, 2))

    def test_facebook_only_never_touches_the_website(self):
        s = self.run_analysis(facebook_url=GOOD)
        self.assertEqual((s["mode"], s["status"], s["website"], s["website_url"]), ("facebook", "done", None, None))
        self.assertEqual([x["key"] for x in s["steps"]], ["facebook", "profile"])
        self.assertEqual(list(s["profile"]["by_source"]), ["facebook"])
        self.m["crawl"].assert_not_called()
        self.m["site_check"].assert_not_called()
        self.assertNotIn("WEBSITE PAGE", self.m["llm"].call_args.args[3])

    def test_a_facebook_page_apify_cannot_read_fails_before_the_model_is_called(self):
        with mock.patch.object(apify_runner, "facebook_pages", return_value=([], 0.0, False)):
            s = self.run_analysis(facebook_url="https://www.facebook.com/privatepage")
        self.assertEqual(s["status"], "error")
        self.assertIn("couldn't read that Facebook page", s["error"])
        self.m["llm"].assert_not_called()

    def test_a_website_failure_in_a_combined_run_is_reported(self):
        self.m["crawl"].side_effect = UpstreamError("The website took too long to load.")
        s = self.run_analysis(website_url=SITE, facebook_url=GOOD)
        self.assertEqual((s["status"], s["error"]), ("error", "The website took too long to load."))
        self.m["llm"].assert_not_called()

    def test_retry_runs_a_failed_combined_analysis_again(self):
        self.m["llm"].side_effect = UpstreamError("LLM provider error 500")
        aid = self.run_analysis(website_url=SITE, facebook_url=GOOD)["id"]
        self.assertEqual(self.get(aid)["status"], "error")
        self.m["llm"].side_effect = fake_llm
        self.client.post(f"/api/analyses/{aid}/retry")
        s = self.get(aid)
        self.assertEqual((s["status"], s["error"]), ("done", None))
        self.assertEqual(self.client.post(f"/api/analyses/{aid}/retry").status_code, 409)  # nothing to retry any more

    def test_confirm_endpoint_is_only_for_website_only_analyses(self):
        aid = self.run_analysis(website_url=SITE, facebook_url=GOOD)["id"]
        self.assertEqual(self.client.post(f"/api/analyses/{aid}/profile", json={"facebook_url": GOOD}).status_code, 409)


class WebsiteOnlyWithoutFacebookTest(ApiTestCase):
    def test_a_website_alone_reads_only_the_website_and_never_touches_apify(self):
        s = self.run_analysis(website_url=SITE)
        self.assertEqual((s["mode"], s["discover"], s["status"]), ("website", False, "done"))
        self.assertEqual([x["key"] for x in s["steps"]], ["crawl", "profile"])
        self.assertEqual((s["cost"]["apify_usd"], s["facebook"], s["facebook_candidates"]), (0.0, None, []))
        self.m["pages"].assert_not_called()
        self.m["posts"].assert_not_called()
        self.assertEqual(list(s["profile"]["by_source"]), ["website"])

    def test_the_user_can_ask_us_to_look_for_the_page(self):
        s = self.run_analysis(website_url=SITE, find_facebook=True)
        self.assertEqual((s["discover"], s["status"]), (True, "awaiting_facebook"))

    def test_the_option_is_ignored_when_a_facebook_link_is_given(self):
        s = self.run_analysis(website_url=SITE, facebook_url=GOOD, find_facebook=True)
        self.assertEqual((s["mode"], s["discover"], s["status"]), ("both", False, "done"))

    def test_a_failed_website_only_run_retries_as_website_only(self):
        with mock.patch.object(analyses.crawler, "crawl_site", side_effect=UpstreamError("down")):
            aid = self.run_analysis(website_url=SITE)["id"]
        self.assertEqual(self.get(aid)["status"], "error")
        self.assertEqual(self.client.post(f"/api/analyses/{aid}/retry").json()["steps"][0]["key"], "crawl")
        self.assertEqual(self.get(aid)["status"], "done")

    def test_the_estimate_for_a_website_alone_is_free(self):
        with mock.patch("app.clients.apify_account", return_value=None):
            apify = self.client.post("/api/analyses/estimate", json={"website_url": SITE}).json()["apify"]
        self.assertEqual((apify["low_usd"], apify["high_usd"]), (0.0, 0.0))

    def test_every_run_carries_a_rough_wait_time(self):
        for body in ({"website_url": SITE}, {"website_url": SITE, "find_facebook": True}, {"facebook_url": GOOD}):
            low, high = self.run_analysis(**body)["eta"]
            self.assertTrue(0 < low < high, body)

    def test_analyses_saved_before_the_option_existed_keep_their_behaviour(self):
        old = analyses.create(SITE, None)
        analyses.update(old["id"], lambda s: (s.pop("discover"), s.pop("eta")))
        self.assertEqual((analyses.load(old["id"])["discover"], analyses.load(old["id"])["eta"]), (True, None))


class SameBrandTest(ApiTestCase):
    def pages_with(self, website):
        page = {**PAGES[0], "website": website}
        return mock.patch.object(apify_runner, "facebook_pages", side_effect=lambda token, urls: ([page], 0.012, False))

    def test_matching_website_gives_no_warning(self):
        self.assertEqual(self.run_analysis(website_url=SITE, facebook_url=GOOD)["warnings"], [])

    def test_a_different_website_on_the_page_is_flagged(self):
        with self.pages_with("https://another-brand.com"), mock.patch.object(analyses.crawler, "crawl_site", side_effect=lambda url: site_data(facebook=())):
            s = self.run_analysis(website_url=SITE, facebook_url=GOOD)
        self.assertEqual(s["status"], "done")  # a warning, not a block: the user may know better
        self.assertTrue(any("another-brand.com" in w and "same brand" in w for w in s["warnings"]), s["warnings"])

    def test_a_site_that_links_to_the_page_outweighs_a_different_listed_website(self):
        with self.pages_with("https://another-brand.com"):
            self.assertEqual(self.run_analysis(website_url=SITE, facebook_url=GOOD)["warnings"], [])

    def test_no_website_on_the_page_is_fine_when_the_site_links_to_the_page(self):
        with self.pages_with(None):
            self.assertEqual(self.run_analysis(website_url=SITE, facebook_url=GOOD)["warnings"], [])

    def test_no_evidence_either_way_is_flagged_as_unconfirmed(self):
        with self.pages_with(None), mock.patch.object(analyses.crawler, "crawl_site", side_effect=lambda url: site_data(facebook=())):
            s = self.run_analysis(website_url=SITE, facebook_url=GOOD)
        self.assertTrue(any("couldn't confirm" in w for w in s["warnings"]), s["warnings"])

    def test_the_model_is_told_what_to_do_with_two_different_businesses(self):
        self.assertIn("different businesses", analyses.brand.SYSTEM)


class EstimateTest(ApiTestCase):
    def estimate(self, **body):
        with mock.patch("app.clients.apify_account",
                               return_value={"remaining_usd": 4.2, "limit_usd": 5.0}):
            return self.client.post("/api/analyses/estimate", json=body)

    def test_facebook_page_costs_one_page_read_and_ten_posts(self):
        res = self.estimate(facebook_url=GOOD).json()
        self.assertEqual(res["apify"]["low_usd"], 0.063)  # 0.012 page + 0.001 start + 10 x 0.005
        self.assertEqual(res["account"]["remaining_usd"], 4.2)
        self.assertEqual(res["llm"]["model"], "anthropic/claude-haiku-5.5")

    def test_website_only_gives_a_range_because_the_page_is_not_known_yet(self):
        apify = self.estimate(website_url=SITE, find_facebook=True).json()["apify"]
        self.assertLess(apify["low_usd"], apify["high_usd"])

    def test_a_cached_page_costs_nothing(self):
        with mock.patch.object(apify_runner, "facebook_cached", return_value=True):
            apify = self.estimate(facebook_url=GOOD).json()["apify"]
        self.assertEqual((apify["low_usd"], apify["high_usd"], apify["cached"]), (0.0, 0.0, True))

    def test_nothing_entered_has_no_estimate_and_a_bad_link_does_not_error(self):
        self.assertIsNone(self.estimate().json()["apify"])
        self.assertEqual(self.estimate(facebook_url="https://example.com/x").status_code, 200)

    def test_an_unreachable_apify_account_is_reported_as_unknown(self):
        with mock.patch("app.clients.apify_account", side_effect=UpstreamError("down")):
            res = self.client.post("/api/analyses/estimate", json={"facebook_url": GOOD}).json()
        self.assertIsNone(res["account"])
        self.assertIsNotNone(res["apify"])


class LogoTest(ApiTestCase):
    def test_a_found_logo_is_stored_and_served_with_locked_down_headers(self):
        self.m["logo"].return_value = ("image/svg+xml", b"<svg onload='alert(1)'/>")
        s = self.run_analysis(website_url=SITE, facebook_url=GOOD)
        self.assertTrue(s["has_logo"])
        res = self.client.get(f"/api/analyses/{s['id']}/logo")
        self.assertEqual((res.status_code, res.content, res.headers["content-type"]), (200, b"<svg onload='alert(1)'/>", "image/svg+xml"))
        self.assertEqual(res.headers["x-content-type-options"], "nosniff")
        self.assertIn("sandbox", res.headers["content-security-policy"])

    def test_no_logo_found_is_not_an_error(self):
        s = self.run_analysis(website_url=SITE, facebook_url=GOOD)
        self.assertEqual((s["status"], s["has_logo"]), ("done", False))
        self.assertEqual(self.client.get(f"/api/analyses/{s['id']}/logo").status_code, 404)

    def test_a_logo_lookup_crash_never_fails_the_analysis(self):
        self.m["logo"].side_effect = RuntimeError("boom")
        self.assertEqual(self.run_analysis(website_url=SITE, facebook_url=GOOD)["status"], "done")

    def test_facebook_picture_is_a_candidate_and_site_icons_win_when_crisp(self):
        self.run_analysis(facebook_url=GOOD)
        self.assertEqual(self.m["logo"].call_args.args[1], ["https://scontent.fbcdn.net/logo.jpg"])
        crisp = crawler.Page(SITE, "After You", "d", "text", [{"href": "/apple.png", "rel": "apple-touch-icon", "sizes": "180x180"}], None)
        self.m["crawl"].side_effect = lambda url: crawler.SiteData(SITE, [crisp], {"facebook": [], "tiktok": [], "instagram": [], "youtube": [], "line": []})
        self.run_analysis(website_url=SITE, facebook_url=GOOD)
        urls = self.m["logo"].call_args.args[1]
        self.assertEqual(urls[:2], [SITE + "/apple.png", "https://scontent.fbcdn.net/logo.jpg"])

    def test_website_only_looks_for_the_logo_again_once_a_page_is_chosen(self):
        aid = self.run_analysis(website_url=SITE, find_facebook=True)["id"]
        self.assertEqual(self.m["logo"].call_count, 1)  # website icons only, while the user is still choosing
        self.client.post(f"/api/analyses/{aid}/profile", json={"facebook_url": GOOD})
        self.assertEqual(self.m["logo"].call_count, 2)
        self.assertIn("https://scontent.fbcdn.net/logo.jpg", self.m["logo"].call_args.args[1])


class MediaTest(ApiTestCase):
    COVER = "https://scontent.fbcdn.net/cover.jpg"
    SHOT = "https://scontent.fbcdn.net/shot.jpg"

    def setUp(self):
        super().setUp()
        page = {**PAGES[0], "coverPhotoUrl": self.COVER}
        post = {**POSTS[0], "media": [{"__typename": "Video", "thumbnail": self.SHOT}]}
        for patch in (mock.patch.object(apify_runner, "facebook_pages", side_effect=lambda token, urls: ([page], 0.012, False)),
                      mock.patch.object(apify_runner, "facebook_posts", side_effect=lambda token, urls, limit: ([post], 0.01, False)),
                      mock.patch.object(logos, "fetch", side_effect=lambda http, url, **kw: ("image/jpeg", b"\xff\xd8" + url.encode()))):
            patch.start()
            self.addCleanup(patch.stop)

    def test_cover_becomes_the_banner_and_post_pictures_are_stored_and_served(self):
        s = self.run_analysis(website_url=SITE, facebook_url=GOOD)
        self.assertEqual([(m["key"], m["role"], m["source"]) for m in s["media"]][:2], [("banner", "banner", "facebook"), ("s0", "sample", "facebook")])
        self.assertTrue(s["media"][1]["video"])
        res = self.client.get(f"/api/analyses/{s['id']}/media/banner")
        self.assertEqual((res.status_code, res.headers["content-type"], res.headers["x-content-type-options"]), (200, "image/jpeg", "nosniff"))
        self.assertIn(self.COVER.encode(), res.content)
        self.assertNotIn("fbcdn", json.dumps(s["media"]))  # the expiring address never reaches the browser

    def test_unknown_or_malformed_keys_are_404(self):
        aid = self.run_analysis(facebook_url=GOOD)["id"]
        for key in ("s9", "nope", "..%2Fx"):
            self.assertEqual(self.client.get(f"/api/analyses/{aid}/media/{key}").status_code, 404, key)

    def test_a_failing_picture_download_never_fails_the_analysis(self):
        with mock.patch.object(media, "download", side_effect=RuntimeError("boom")):
            s = self.run_analysis(facebook_url=GOOD)
        self.assertEqual((s["status"], s["media"]), ("done", []))

    def test_deleting_the_analysis_deletes_its_pictures(self):
        aid = self.run_analysis(facebook_url=GOOD)["id"]
        self.client.delete(f"/api/analyses/{aid}")
        self.assertIsNone(media.load(aid, "banner"))


class OlderVersionTest(ApiTestCase):
    """The database outlives releases: an analysis saved before newer fields existed must still list and open."""

    OLD = {  # shape written by the first brand-analysis release
        "id": "old000000001", "status": "done", "website_url": SITE, "facebook_url_input": None,
        "steps": [], "website": {"url": SITE, "title": "After You", "description": None, "pages": [], "socials": {}},
        "facebook_candidates": [], "recommended": None, "selected_facebook": GOOD, "requested_facebook": GOOD,
        "profile": {**VALID, "by_source": None}, "cost": {"apify_usd": 0.1, "llm_usd": 0.0, "llm_known": True, "llm_input_tokens": 0,
                                                     "llm_output_tokens": 0, "llm_model": None, "cached_runs": 0},
        "error": None, "internal": {"site_pages": [{"url": SITE, "title": "t", "description": None, "text": "x"}]},
        "created_at": "2026-10-29T00:00:00+00:00",
    }

    def setUp(self):
        super().setUp()
        old = {k: v for k, v in self.OLD.items()}
        old["profile"] = {k: v for k, v in VALID.items() if k != "by_source"}
        with analyses.connect() as conn:
            conn.execute("INSERT INTO analyses (id, state, created_at, updated_at) VALUES (?, ?, ?, ?)",
                         (old["id"], json.dumps(old), old["created_at"], old["created_at"]))

    def test_old_analyses_appear_in_the_list_and_open(self):
        item = self.client.get("/api/analyses").json()[0]
        self.assertEqual((item["id"], item["mode"], item["has_logo"], item["title"]), ("old000000001", "website", False, "After You"))
        opened = self.get("old000000001")
        self.assertEqual((opened["mode"], opened["warnings"], opened["has_logo"]), ("website", [], False))
        self.assertEqual(opened["profile"]["by_source"], {})

    def test_old_analyses_can_still_be_edited_retried_and_deleted(self):
        edited = json.loads(json.dumps(VALID)); edited["tiktok"]["hashtags_th"] = ["#a", "#b"]
        self.assertEqual(self.client.put("/api/analyses/old000000001/profile", json=edited).status_code, 200)
        self.assertEqual(self.client.delete("/api/analyses/old000000001").status_code, 200)


class HistoryTest(ApiTestCase):
    def test_recent_lists_newest_first_with_a_readable_title(self):
        first = self.run_analysis(website_url=SITE, facebook_url=GOOD)["id"]
        second = self.run_analysis(facebook_url=GOOD)["id"]
        items = self.client.get("/api/analyses").json()
        self.assertEqual([i["id"] for i in items], [second, first])
        self.assertEqual((items[1]["title"], items[1]["mode"], items[1]["status"]), ("After You", "both", "done"))
        self.assertEqual((items[1]["website"], items[1]["facebook"]), ("afteryoudessertcafe.com", "afteryoucafe"))
        self.assertNotIn("state", items[0])

    def test_unfinished_analyses_get_a_title_from_what_is_known(self):
        self.m["crawl"].side_effect = UpstreamError("down")
        self.run_analysis(website_url=SITE, find_facebook=True)
        self.assertEqual(self.client.get("/api/analyses").json()[0]["title"], "afteryoudessertcafe.com")

    def test_delete_removes_the_analysis_and_its_logo(self):
        self.m["logo"].return_value = ("image/png", b"png")
        aid = self.run_analysis(website_url=SITE, facebook_url=GOOD)["id"]
        self.assertEqual(self.client.delete(f"/api/analyses/{aid}").status_code, 200)
        self.assertEqual(self.client.get(f"/api/analyses/{aid}").status_code, 404)
        self.assertEqual(self.client.get(f"/api/analyses/{aid}/logo").status_code, 404)
        self.assertEqual(self.client.get("/api/analyses").json(), [])
        self.assertEqual(self.client.delete(f"/api/analyses/{aid}").status_code, 404)

    def test_deleting_while_a_job_is_running_does_not_break_the_job(self):
        with mock.patch.object(analyses, "spawn"):
            aid = self.start(website_url=SITE, find_facebook=True).json()["id"]
        self.client.delete(f"/api/analyses/{aid}")
        analyses.run_discovery(aid)  # the job still finishes without raising
        self.assertEqual(self.client.get("/api/analyses").json(), [])


class ProfileEditAndHousekeepingTest(ApiTestCase):
    def test_hashtags_can_be_edited_without_losing_the_per_source_summaries(self):
        aid = self.run_analysis(website_url=SITE, facebook_url=GOOD)["id"]
        edited = json.loads(json.dumps(VALID))
        edited["tiktok"]["hashtags_th"] = ["#เค้กช็อกโกแลต", "#คาเฟ่"]
        del edited["by_source"]  # a client that only sends the TikTok plan
        res = self.client.put(f"/api/analyses/{aid}/profile", json=edited)
        self.assertEqual(res.json()["profile"]["tiktok"]["hashtags_th"], ["เค้กช็อกโกแลต", "คาเฟ่"])
        self.assertEqual(sorted(res.json()["profile"]["by_source"]), ["facebook", "website"])
        edited["tiktok"].pop("keywords")
        self.assertEqual(self.client.put(f"/api/analyses/{aid}/profile", json=edited).status_code, 422)

    def test_the_ideal_creator_can_be_edited_and_only_that_and_the_hashtags_change(self):
        aid = self.run_analysis(website_url=SITE, facebook_url=GOOD)["id"]
        before = self.get(aid)["profile"]
        self.assertEqual(before["edited"], [])
        edited = json.loads(json.dumps(before))
        edited["creator_fit"]["niches"] = ["vegan dessert reviewer"]
        edited["creator_fit"]["avoid"] = []
        edited["summary"] = "tampered"  # not editable: must be ignored
        res = self.client.put(f"/api/analyses/{aid}/profile", json=edited).json()["profile"]
        self.assertEqual((res["creator_fit"]["niches"], res["creator_fit"]["avoid"]), (["vegan dessert reviewer"], []))
        self.assertEqual((res["summary"], res["edited"]), (before["summary"], ["creator_fit"]))
        edited["tiktok"]["hashtags_th"] = ["#ขนม"]
        again = self.client.put(f"/api/analyses/{aid}/profile", json=edited).json()["profile"]
        self.assertEqual(again["edited"], ["creator_fit", "tiktok"])

    def test_saving_without_changes_does_not_mark_anything_as_edited(self):
        aid = self.run_analysis(website_url=SITE, facebook_url=GOOD)["id"]
        same = self.get(aid)["profile"]
        self.assertEqual(self.client.put(f"/api/analyses/{aid}/profile", json=same).json()["profile"]["edited"], [])

    def test_nothing_to_edit_before_a_profile_exists(self):
        aid = self.run_analysis(website_url=SITE, find_facebook=True)["id"]
        self.assertEqual(self.client.put(f"/api/analyses/{aid}/profile", json=VALID).status_code, 409)

    def test_restart_marks_running_analyses_as_interrupted(self):
        with mock.patch.object(analyses, "spawn"):  # job never runs -> stays "running"
            aid = self.start(website_url=SITE, find_facebook=True).json()["id"]
        analyses.mark_interrupted()
        s = self.get(aid)
        self.assertEqual(s["status"], "error")
        self.assertIn("restarted", s["error"])


class HelpersTest(unittest.TestCase):
    def test_recommend_prefers_matching_site_then_recent_then_big(self):
        base = dict(readable=True, website_match=True, followers=10, last_post_at=iso(400))
        a = {**base, "url": "a", "followers": 999}
        b = {**base, "url": "b", "last_post_at": iso(5)}
        c = {**base, "url": "c", "website_match": False, "last_post_at": iso(1), "followers": 10**7}
        self.assertEqual(analyses.recommend([a, b, c]), "b")
        self.assertIsNone(analyses.recommend([{**a, "readable": False}]))

    def test_same_site_ignores_www_and_scheme(self):
        self.assertTrue(analyses._same_site("http://www.brand.com/", "https://brand.com/menu"))
        self.assertTrue(analyses._same_site("shop.brand.com", "brand.com"))
        self.assertFalse(analyses._same_site("brandx.com", "brand.com"))
        self.assertFalse(analyses._same_site(None, "brand.com"))

    def test_facebook_stats_with_no_posts_or_no_followers(self):
        self.assertEqual(analyses.facebook_stats([], 1000), {"posts_read": 0})
        stats = analyses.facebook_stats([{"time": iso(1), "likes": 10}], None)
        self.assertIsNone(stats["engagement_rate_pct"])
        self.assertIsNone(stats["posts_per_week"])  # one post cannot define a rhythm


if __name__ == "__main__":
    unittest.main()
