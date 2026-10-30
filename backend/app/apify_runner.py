"""Run Apify actors with a persistent result cache, so repeating the same analysis costs $0."""
import hashlib
import json
from datetime import datetime, timedelta, timezone

from apify_client import ApifyClient

from .clients import UpstreamError
from .db import connect

CACHE_TTL = timedelta(days=7)
FB_PAGES = "apify/facebook-pages-scraper"
FB_POSTS = "apify/facebook-posts-scraper"


def _key(actor: str, run_input: dict) -> str:
    return hashlib.sha256(f"{actor}|{json.dumps(run_input, sort_keys=True)}".encode()).hexdigest()


def expected_usd(run: dict, n_items: int) -> float:
    """What a pay-per-event run costs: primary-event price x results + the one-time start fee.

    The `usageTotalUsd` on a just-finished run undercounts (Apify books these charges late, measured 2-8x low
    right after the run and still low 17 s later), so the cost is derived from the run's own price list.
    Matches the final billed amount on every run checked (TikTok 40 results = $0.149, 10 FB posts = $0.051)."""
    events = ((run.get("pricingInfo") or {}).get("pricingPerEvent") or {}).get("actorChargeEvents") or {}
    primary = next((e.get("eventPriceUsd", 0.0) for e in events.values() if e.get("isPrimaryEvent")), 0.0)
    start = (events.get("actor-start") or {}).get("eventPriceUsd", 0.0)
    return round(n_items * primary + start, 5)


def is_cached(actor: str, run_input: dict) -> bool:
    with connect() as conn:
        row = conn.execute("SELECT created_at FROM apify_cache WHERE key = ?", (_key(actor, run_input),)).fetchone()
    return bool(row and datetime.now(timezone.utc) - datetime.fromisoformat(row[0]) < CACHE_TTL)


def run_actor(token: str, actor: str, run_input: dict) -> tuple[list[dict], float, bool]:
    """Returns (items, usd_charged, from_cache)."""
    key = _key(actor, run_input)
    with connect() as conn:
        row = conn.execute("SELECT items, created_at FROM apify_cache WHERE key = ?", (key,)).fetchone()
    if row and datetime.now(timezone.utc) - datetime.fromisoformat(row[1]) < CACHE_TTL:
        return json.loads(row[0]), 0.0, True

    client = ApifyClient(token)
    try:
        run = client.actor(actor).call(run_input=run_input, logger=None)
    except Exception as exc:  # apify-client raises its own error types; never echo the token
        raise UpstreamError(f"Apify run failed ({actor}): {str(exc)[:160]}") from None
    if not run or run.get("status") != "SUCCEEDED":
        raise UpstreamError(f"Apify run did not succeed ({actor}): {run and run.get('status')}")
    items = client.dataset(run["defaultDatasetId"]).list_items().items
    usd = max(expected_usd(run, len(items)), float(run.get("usageTotalUsd") or 0))
    if items:  # never cache an empty result — it may be a transient scrape failure
        with connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO apify_cache (key, items, usd, created_at) VALUES (?, ?, ?, ?)",
                (key, json.dumps(items, default=str), usd, datetime.now(timezone.utc).isoformat()),
            )
    return items, usd, False


def _pages_input(urls: list[str]) -> dict:
    return {"startUrls": [{"url": u} for u in urls]}


def _posts_input(urls: list[str], limit: int) -> dict:
    return {"startUrls": [{"url": u} for u in urls], "resultsLimit": limit}


def facebook_pages(token: str, urls: list[str]) -> tuple[list[dict], float, bool]:
    return run_actor(token, FB_PAGES, _pages_input(urls))


def facebook_posts(token: str, urls: list[str], limit: int) -> tuple[list[dict], float, bool]:
    return run_actor(token, FB_POSTS, _posts_input(urls, limit))


def facebook_cached(url: str, posts_limit: int) -> bool:
    """True when reading this page and its posts would be served from the cache (costs nothing)."""
    return is_cached(FB_PAGES, _pages_input([url])) and is_cached(FB_POSTS, _posts_input([url], posts_limit))


# Price list of the actors above (pay-per-event, as read from each run's pricingInfo): USD.
FB_PAGE_USD = 0.012
FB_POST_USD = 0.005
FB_POSTS_START_USD = 0.001
