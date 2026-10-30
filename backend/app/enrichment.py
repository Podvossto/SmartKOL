"""Read the latest videos of shortlisted creators and turn them into numbers.

A hashtag search shows one video per creator, so its dates and views say little about the creator. Here one Apify run
reads each chosen creator's own newest videos; the metrics come from those videos only (never lifetime totals) and are
stored on the creator record, so showing or filtering by them costs nothing.
"""
import statistics
from datetime import datetime, timezone

import httpx

from . import analyses, apify_runner, config, discovery
from .clients import UpstreamError

MIN_VIDEOS, MAX_VIDEOS = 3, 30
MAX_CREATORS = 50
MAX_TOTAL = 500  # videos in one run, as for the search: a slip of the finger should not cost more than about $2
DEFAULT_VIDEOS = 10


class EnrichError(ValueError):
    """The requested read is not allowed. The message is shown to the user as it is."""


def run_input(usernames: list[str], videos: int) -> dict:
    return {"profiles": usernames, "resultsPerPage": videos, "profileSorting": "latest", "excludePinnedPosts": True, **discovery.NO_DOWNLOADS}


def clean(usernames: list[str], videos: int, known: set[str]) -> list[str]:
    seen = list(dict.fromkeys(u.lstrip("@") for u in usernames))
    if not seen:
        raise EnrichError("Choose at least one creator.")
    if len(seen) > MAX_CREATORS:
        raise EnrichError(f"At most {MAX_CREATORS} creators in one read.")
    if not MIN_VIDEOS <= videos <= MAX_VIDEOS:
        raise EnrichError(f"Read between {MIN_VIDEOS} and {MAX_VIDEOS} videos per creator.")
    if len(seen) * videos > MAX_TOTAL:
        raise EnrichError(f"At most {MAX_TOTAL} videos in one read.")
    unknown = [u for u in seen if u not in known]
    if unknown:
        raise EnrichError(f"Not in this search: {', '.join(unknown[:3])}.")
    return sorted(seen)  # same set, same order -> same cache entry


def estimate(usernames: list[str], videos: int) -> dict:
    """Every video, plus the start fee of the run. `usd` is 0 when the same read is already in the cache."""
    inp = run_input(usernames, videos)
    list_usd = round(len(usernames) * videos * discovery.RESULT_USD + discovery.START_USD, 4)
    cached = apify_runner.is_cached(discovery.ACTOR, inp)
    return {"creators": len(usernames), "videos_each": videos, "videos": len(usernames) * videos,
            "usd": 0.0 if cached else list_usd, "list_usd": list_usd, "cached": cached}


def metrics(vids: list[dict], now: datetime | None = None) -> dict:
    """Numbers from a creator's newest videos. Engagement rate is (likes + comments + shares) / views, per video,
    then the median, so one viral video does not set the figure."""
    now = now or datetime.now(timezone.utc)
    dated = sorted(((discovery._iso(v.get("createTimeISO")), v) for v in vids if discovery._iso(v.get("createTimeISO"))), key=lambda p: p[0], reverse=True)
    views = [v.get("playCount") or 0 for v in vids]
    rates = [((v.get("diggCount") or 0) + (v.get("commentCount") or 0) + (v.get("shareCount") or 0)) / v["playCount"] for v in vids if v.get("playCount")]
    newest = dated[0][0] if dated else None
    span_days = (dated[0][0] - dated[-1][0]).total_seconds() / 86400 if len(dated) > 1 else 0
    return {
        "videos": len(vids),
        "median_views": int(statistics.median(views)) if views else 0,
        "median_er": round(statistics.median(rates), 4) if rates else None,
        "posts_per_week": round((len(dated) - 1) / span_days * 7, 2) if span_days >= 1 else None,
        "last_post": newest.isoformat() if newest else None,
        "days_since_last_post": (now - newest).days if newest else None,
        "ad_share": round(sum(bool(v.get("isAd") or v.get("isSponsored")) for v in vids) / len(vids), 3) if vids else 0.0,
        "shop_share": round(sum(bool(v.get("hasTikTokShopProduct")) for v in vids) / len(vids), 3) if vids else 0.0,
        "read_at": now.isoformat(),
    }


def apply(creators: list[dict], items: list[dict]) -> int:
    """Put the metrics on each creator found in `items`. Returns how many creators were filled in. The creator's
    last_post becomes the real newest video, so the recency filter can be trusted from here on."""
    by_user: dict[str, list[dict]] = {}
    for item in items:
        name = (item.get("authorMeta") or {}).get("name")
        if name:
            by_user.setdefault(name, []).append(item)
    filled = 0
    for c in creators:
        vids = by_user.get(c["username"])
        if not vids:
            continue
        c["metrics"] = metrics(vids)
        if c["metrics"]["last_post"]:
            c["last_post"] = c["metrics"]["last_post"]
        filled += 1
    return filled


# ---------- the job ----------

def start(aid: str, usernames: list[str], videos: int) -> dict:
    state = analyses.update(aid, lambda s: s["creators"].update(enrich={"status": "running", "usernames": usernames, "videos_each": videos, "error": None, "usd": 0.0, "cached": False, "missing": [], "read_at": None}))
    analyses.spawn(run, aid, usernames, videos)
    return state


def run(aid: str, usernames: list[str], videos: int) -> None:
    try:
        items, usd, cached = apify_runner.run_actor(config.apify_token()[0], discovery.ACTOR, run_input(usernames, videos))
    except (UpstreamError, httpx.HTTPError) as exc:
        message = str(exc) if isinstance(exc, UpstreamError) else "Network error while contacting an external service."
        analyses.update(aid, lambda s: s["creators"]["enrich"].update(status="error", error=message))
        return
    except Exception:
        analyses.log.exception("creator read %s failed", aid)
        analyses.update(aid, lambda s: s["creators"]["enrich"].update(status="error", error="Something unexpected went wrong. Check the server log and try again."))
        return

    def done(s):
        filled = apply(s["creators"]["items"], items)
        missing = [u for u in usernames if not any(c["username"] == u and "metrics" in c for c in s["creators"]["items"])]
        s["creators"]["enrich"].update(status="done", usd=round(usd, 5), cached=cached, missing=missing, filled=filled, read_at=datetime.now(timezone.utc).isoformat())
        s["cost"]["apify_usd"] = round(s["cost"]["apify_usd"] + usd, 5)
        s["cost"]["cached_runs"] += int(cached)
    analyses.update(aid, done)
