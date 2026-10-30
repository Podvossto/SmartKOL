import unittest

from app.apify_runner import expected_usd


def run_with(events: dict) -> dict:
    return {"pricingInfo": {"pricingPerEvent": {"actorChargeEvents": events}}, "usageTotalUsd": 0.001}


TIKTOK = run_with({"result": {"eventPriceUsd": 0.0037, "isPrimaryEvent": True},
                   "actor-start": {"eventPriceUsd": 0.001, "isOneTimeEvent": True},
                   "video-download": {"eventPriceUsd": 0.0013}})
FB_POSTS = run_with({"post": {"eventPriceUsd": 0.005, "isPrimaryEvent": True}, "actor-start": {"eventPriceUsd": 0.001}})
FB_PAGES = run_with({"apify-default-dataset-item": {"eventPriceUsd": 0.012, "isPrimaryEvent": True}})


class ExpectedUsdTest(unittest.TestCase):
    """Expected values are the amounts Apify actually billed for real runs (2026-10-29)."""

    def test_matches_real_billed_runs(self):
        self.assertEqual(expected_usd(TIKTOK, 40), 0.149)
        self.assertEqual(expected_usd(TIKTOK, 25), 0.0935)
        self.assertEqual(expected_usd(FB_POSTS, 10), 0.051)
        self.assertEqual(expected_usd(FB_POSTS, 4), 0.021)
        self.assertEqual(expected_usd(FB_PAGES, 2), 0.024)

    def test_addons_are_not_counted_and_missing_price_info_is_zero(self):
        self.assertEqual(expected_usd(TIKTOK, 0), 0.001)  # start fee only
        self.assertEqual(expected_usd({}, 10), 0.0)


if __name__ == "__main__":
    unittest.main()
