"""Find Thai TikTok creators from the brand's hashtags.

One Apify run reads the newest videos under each hashtag; videos are grouped by author into one record per creator.
The hard filters (Thai captions, public account, recent post, follower range) run on the stored records, so turning a
filter on or off never costs anything.
"""
import re
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

from . import analyses, apify_runner, config
from .clients import UpstreamError

ACTOR = "clockworks/tiktok-scraper"
# Pay-per-event price list of the actor on the free plan (read from its pricingInfo, 2026-10-30).
RESULT_USD = 0.0037
START_USD = 0.001
NO_DOWNLOADS = {"shouldDownloadVideos": False, "shouldDownloadCovers": False, "shouldDownloadAvatars": False,
                "shouldDownloadSlideshowImages": False, "shouldDownloadMusicCovers": False}


@dataclass(frozen=True)
class Preset:
    """How wide one search is: the first `hashtags` of the user's list, `per_tag` newest videos each."""
    hashtags: int
    per_tag: int
    label: str


PRESETS = {
    "lean": Preset(3, 25, "Lean"),
    "full": Preset(6, 40, "Full"),
}


# ---------- cost ----------

def plan(profile: dict, preset: str) -> tuple[list[str], dict]:
    """The hashtags a search would use, and the run input."""
    p = PRESETS[preset]
    tiktok = profile["tiktok"]
    tags = [t.lstrip("#") for t in tiktok["hashtags_th"] + tiktok["hashtags_en"]][: p.hashtags]
    return tags, {"hashtags": tags, "resultsPerPage": p.per_tag, **NO_DOWNLOADS}


def estimate(profile: dict, preset: str) -> dict:
    """What a search costs before it runs. Served from the cache it costs nothing."""
    tags, run_input = plan(profile, preset)
    if not tags:
        return {"preset": preset, "hashtags": [], "videos": 0, "usd": 0.0, "cached": False}
    videos = len(tags) * PRESETS[preset].per_tag
    cached = apify_runner.is_cached(ACTOR, run_input)
    return {"preset": preset, "hashtags": tags, "videos": videos, "usd": 0.0 if cached else round(videos * RESULT_USD + START_USD, 4), "cached": cached}


# ---------- privacy ----------

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<![\d@])[+(]?\d(?:[\s().-]{0,2}\d){7,13}(?!\d)")  # digits on both ends only: "ID:0910387533ᴘ" is caught


def mask_contacts(text: str | None) -> str:
    """Phone numbers and e-mail addresses in a creator's bio or caption are personal data we don't keep."""
    if not text:
        return ""
    return _PHONE.sub("[hidden]", _EMAIL.sub("[hidden]", text))


# ---------- grouping ----------

def _iso(value: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None
    except ValueError:
        return None


def group_creators(videos: list[dict]) -> list[dict]:
    """One record per author, built only from public fields of the videos found under the hashtags."""
    by_author: dict[str, list[dict]] = {}
    for video in videos:
        name = (video.get("authorMeta") or {}).get("name")
        if name:
            by_author.setdefault(name, []).append(video)
    creators = []
    for name, vids in by_author.items():
        meta = vids[0]["authorMeta"]
        times = [t for t in (_iso(v.get("createTimeISO")) for v in vids) if t]
        views = [v.get("playCount") or 0 for v in vids]
        top = sorted(vids, key=lambda v: v.get("playCount") or 0, reverse=True)[:2]
        creators.append({
            "username": name,
            "nickname": meta.get("nickName") or name,
            "url": f"https://www.tiktok.com/@{name}",
            "bio": mask_contacts(meta.get("signature")),
            "followers": meta.get("fans"),
            "likes": meta.get("heart"),
            "total_videos": meta.get("video"),
            "verified": bool(meta.get("verified")),
            "private": bool(meta.get("privateAccount")),
            "videos_found": len(vids),
            "thai_share": round(sum(v.get("textLanguage") == "th" for v in vids) / len(vids), 3),
            "last_post": max(times).isoformat() if times else None,
            "median_views": int(statistics.median(views)),
            "ad_videos": sum(bool(v.get("isAd") or v.get("isSponsored")) for v in vids),
            "shop_videos": sum(bool(v.get("hasTikTokShopProduct")) for v in vids),
            "hashtags": sorted({v["searchHashtag"]["name"] if isinstance(v.get("searchHashtag"), dict) else v.get("searchHashtag") for v in vids} - {None}),
            "samples": [{"url": v.get("webVideoUrl"), "text": mask_contacts(v.get("text"))[:160], "views": v.get("playCount") or 0} for v in top],
        })
    return sorted(creators, key=lambda c: -(c["followers"] or 0))


# ---------- hard filters ----------

@dataclass(frozen=True)
class Filters:
    """Each filter is off when its value is None/False. Defaults follow the project's spec."""
    thai_min: float | None = 0.6
    skip_private: bool = True
    max_age_days: int | None = 30
    min_followers: int | None = 10_000
    max_followers: int | None = None


def apply_filters(creators: list[dict], f: Filters, now: datetime | None = None) -> tuple[list[dict], dict[str, int]]:
    """Returns (kept, dropped). `dropped` counts, per filter, the creators that filter alone would remove."""
    now = now or datetime.now(timezone.utc)
    checks = {
        "thai": lambda c: f.thai_min is None or c["thai_share"] >= f.thai_min,
        "private": lambda c: not (f.skip_private and c["private"]),
        "recent": lambda c: f.max_age_days is None or bool(c["last_post"] and now - _iso(c["last_post"]) <= timedelta(days=f.max_age_days)),
        "min_followers": lambda c: f.min_followers is None or (c["followers"] or 0) >= f.min_followers,
        "max_followers": lambda c: f.max_followers is None or (c["followers"] or 0) <= f.max_followers,
    }
    dropped = {name: sum(not ok(c) for c in creators) for name, ok in checks.items()}
    return [c for c in creators if all(ok(c) for ok in checks.values())], dropped


# ---------- the job ----------

def start(aid: str, preset: str) -> dict:
    """Mark the search as running and hand it to a thread. The caller has already checked the profile and the token."""
    state = analyses.update(aid, lambda s: s["creators"].update({**analyses.EMPTY_CREATORS, "status": "running", "preset": preset}))
    analyses.spawn(run, aid, preset)
    return state


def run(aid: str, preset: str) -> None:
    state = analyses.load(aid)
    if state is None or not state["profile"]:
        return
    tags, run_input = plan(state["profile"], preset)
    try:
        videos, usd, cached = apify_runner.run_actor(config.apify_token()[0], ACTOR, run_input)
        creators = group_creators(videos)
    except (UpstreamError, httpx.HTTPError) as exc:
        message = str(exc) if isinstance(exc, UpstreamError) else "Network error while contacting an external service."
        analyses.update(aid, lambda s: s["creators"].update(status="error", error=message))
        return
    except Exception:
        analyses.log.exception("creator search %s failed", aid)
        analyses.update(aid, lambda s: s["creators"].update(status="error", error="Something unexpected went wrong. Check the server log and try again."))
        return

    def done(s):
        s["creators"].update(status="done", hashtags=tags, videos=len(videos), usd=usd, cached=cached, items=creators,
                             searched_at=datetime.now(timezone.utc).isoformat(), error=None)
        s["cost"]["apify_usd"] = round(s["cost"]["apify_usd"] + usd, 5)
        s["cost"]["cached_runs"] += int(cached)
    analyses.update(aid, done)
