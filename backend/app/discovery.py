"""Find Thai TikTok creators from the brand's hashtags.

One Apify run reads the newest videos under each hashtag; videos are grouped by author into one record per creator.
The hard filters (Thai captions, public account, recent post, follower range) run on the stored records, so turning a
filter on or off never costs anything.
"""
import json
import re
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

from . import analyses, apify_runner, config, llm, logos, media
from .clients import UpstreamError

ACTOR = "clockworks/tiktok-scraper"
# Pay-per-event price list of the actor on the free plan (read from its pricingInfo, 2026-10-30).
SAMPLES = 3  # videos kept per creator for the cards and the detail page
RESULT_USD = 0.0037
START_USD = 0.001
NO_DOWNLOADS = {"shouldDownloadVideos": False, "shouldDownloadCovers": False, "shouldDownloadAvatars": False,
                "shouldDownloadSlideshowImages": False, "shouldDownloadMusicCovers": False}


MAX_PER_TAG = 100
MAX_TOTAL = 500  # videos in one search: a slip of the finger should not cost more than about $2


class PlanError(ValueError):
    """The requested search is not allowed. The message is shown to the user as it is."""


def clean_plan(items: list[tuple[str, int]]) -> list[dict]:
    """The user's choice of hashtags and how many videos to read from each, made safe: no '#', no spaces, each
    hashtag once, a hashtag with 0 videos is simply not searched."""
    plan, seen = [], set()
    for tag, videos in items:
        tag = "".join(tag.split()).lstrip("#")
        if not tag or tag.lower() in seen or videos <= 0:
            continue
        if not re.search(r"\w", tag):  # e.g. "????": a garbled tag would be searched, and paid for, for nothing
            raise PlanError(f"'{tag}' is not a hashtag: it has no letters or digits.")
        if videos > MAX_PER_TAG:
            raise PlanError(f"At most {MAX_PER_TAG} videos per hashtag.")
        seen.add(tag.lower())
        plan.append({"hashtag": tag, "videos": videos})
    if not plan:
        raise PlanError("Choose at least one hashtag and how many videos to read from it.")
    if sum(p["videos"] for p in plan) > MAX_TOTAL:
        raise PlanError(f"At most {MAX_TOTAL} videos in one search.")
    return plan


# ---------- cost ----------

def runs(plan: list[dict]) -> list[dict]:
    """The actor takes one video count per run, so hashtags with the same count share a run."""
    groups: dict[int, list[str]] = {}
    for item in plan:
        groups.setdefault(item["videos"], []).append(item["hashtag"])
    return [{"hashtags": tags, "resultsPerPage": n, **NO_DOWNLOADS} for n, tags in sorted(groups.items(), reverse=True)]


def estimate(plan: list[dict]) -> dict:
    """What a search costs before it runs: every video, plus the start fee of each run. A run already in the cache is
    free; `list_usd` is what the same search would cost with nothing cached."""
    usd, list_usd, cached = 0.0, 0.0, True
    for run_input in runs(plan):
        price = len(run_input["hashtags"]) * run_input["resultsPerPage"] * RESULT_USD + START_USD
        list_usd += price
        if not apify_runner.is_cached(ACTOR, run_input):
            cached = False
            usd += price
    return {"plan": plan, "hashtags": [p["hashtag"] for p in plan], "videos": sum(p["videos"] for p in plan),
            "runs": len(runs(plan)), "usd": round(usd, 4), "list_usd": round(list_usd, 4), "cached": cached}


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


def _cover(video: dict) -> str | None:
    meta = video.get("videoMeta") or {}
    return meta.get("originalCoverUrl") or meta.get("coverUrl")


def public_creator(c: dict) -> dict:
    """What the browser gets. The picture links are signed, expiring and TikTok's: the server fetches them itself
    (see picture()), so the browser only learns whether a picture exists."""
    out = {k: v for k, v in c.items() if k != "avatar_src"}
    out["has_avatar"] = bool(c.get("avatar_src"))
    out["samples"] = [{**{k: v for k, v in s.items() if k != "cover_src"}, "has_cover": bool(s.get("cover_src"))} for s in c["samples"]]
    return out


def picture(http: httpx.Client, aid: str, creator: dict, kind: str) -> tuple[str, bytes] | None:
    """A creator's avatar (`kind` "avatar") or the cover of one of their videos ("0", "1", ...), fetched on first use
    and kept, so it keeps working after TikTok's link expires."""
    key = f"c-{creator['username']}-{kind}"
    found = media.load(aid, key)
    if found:
        return found
    if kind == "avatar":
        src = creator.get("avatar_src")
    else:
        index = int(kind)
        src = creator["samples"][index].get("cover_src") if index < len(creator["samples"]) else None
    fetched = logos.fetch(http, src, max_bytes=media.MAX_BYTES) if src else None
    if fetched:
        media.save_one(aid, key, *fetched)
    return fetched


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
        top = sorted(vids, key=lambda v: v.get("playCount") or 0, reverse=True)[:SAMPLES]
        creators.append({
            "username": name,
            "nickname": meta.get("nickName") or name,
            "url": f"https://www.tiktok.com/@{name}",
            "avatar_src": meta.get("originalAvatarUrl") or meta.get("avatar"),
            "bio": mask_contacts(meta.get("signature")),
            "followers": meta.get("fans"),
            "likes": meta.get("heart"),
            "total_videos": meta.get("video"),
            "verified": bool(meta.get("verified")),
            "private": bool(meta.get("privateAccount")),
            "kind": None,  # creator | shop | media | other, written by the model (see classify)
            "competitor": False,
            "kind_reason": "",
            "videos_found": len(vids),
            "thai_share": round(sum(v.get("textLanguage") == "th" for v in vids) / len(vids), 3),
            "last_post": max(times).isoformat() if times else None,
            "median_views": int(statistics.median(views)),
            "ad_videos": sum(bool(v.get("isAd") or v.get("isSponsored")) for v in vids),
            "shop_videos": sum(bool(v.get("hasTikTokShopProduct")) for v in vids),
            "hashtags": sorted({v["searchHashtag"]["name"] if isinstance(v.get("searchHashtag"), dict) else v.get("searchHashtag") for v in vids} - {None}),
            "samples": [{"url": v.get("webVideoUrl"), "text": mask_contacts(v.get("text"))[:160], "views": v.get("playCount") or 0, "cover_src": _cover(v)} for v in top],
        })
    return sorted(creators, key=lambda c: -(c["followers"] or 0))


# ---------- who is a creator ----------

KINDS = ("creator", "shop", "media", "other")
CLASSIFY_BATCH = 25  # the model spends part of its output budget thinking, so a batch must leave it room
CLASSIFY_SYSTEM = """You sort TikTok accounts for an influencer-marketing agency. The agency wants individual CREATORS who could promote the brand below, and wants to leave out businesses, above all the brand's competitors.

For each account decide "kind":
- "creator": a person or small team whose content is reviews, vlogs, cooking, lifestyle or entertainment, who could be hired to promote something. A home cook showing recipes is a creator.
- "shop": a business or its official account: restaurant, cafe, bakery, brand, product seller, or a person whose account mainly sells or promotes their own shop or products (opening hours, branch, address, order links, "our menu").
- "media": a page, channel, agency, news, meme or aggregator that is not one creator.
- "other": you cannot tell from what is given.
"competitor" is true only for a "shop" that sells the same kind of thing as the brand. "reason": at most 10 words, English.

Use only what is given. Reply with ONE JSON array and nothing else, one object per account, in this shape:
[{"u": "<username>", "kind": "creator"|"shop"|"media"|"other", "competitor": bool, "reason": str}]"""


def _account_line(c: dict) -> str:
    captions = " / ".join(s["text"] for s in c["samples"][:2] if s.get("text"))
    return f"@{c['username']} | {c['followers']} followers | name: {c['nickname']} | bio: {' '.join(c['bio'].split())[:200]} | captions: {captions[:240]}"


def classify(http: httpx.Client, cfg, profile: dict, creators: list[dict]) -> tuple[dict[str, dict], dict]:
    """Ask the model what each account is. Returns ({username: {kind, competitor, reason}}, usage). Accounts the
    model skips or mislabels are simply left out, so a bad reply never costs more than the sorting itself."""
    usage = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "model": cfg.model}
    brand = f"Brand: {profile['brand_name']}. Category: {profile['category']}. Sells: {', '.join(profile['products'][:6])}."
    sorted_out: dict[str, dict] = {}
    for start in range(0, len(creators), CLASSIFY_BATCH):
        batch = creators[start : start + CLASSIFY_BATCH]
        out = llm.complete(http, cfg, CLASSIFY_SYSTEM, brand + "\n\nAccounts:\n" + "\n".join(_account_line(c) for c in batch), max_tokens=8000)
        usage["input_tokens"] += out.input_tokens or 0
        usage["output_tokens"] += out.output_tokens or 0
        usage["cost_usd"] += out.cost_usd or 0.0
        usage["model"] = out.model
        rows = []
        for found in re.finditer(r"\{[^{}]*\}", out.text):  # every complete object, so a reply cut off at the limit still counts
            try:
                rows.append(json.loads(found.group()))
            except ValueError:
                continue
        known = {c["username"] for c in batch}
        for row in rows:
            name = str(row.get("u", "")).lstrip("@") if isinstance(row, dict) else ""
            if name in known and row.get("kind") in KINDS:
                sorted_out[name] = {"kind": row["kind"], "competitor": bool(row.get("competitor")) and row["kind"] == "shop",
                                    "reason": str(row.get("reason") or "")[:100]}
    return sorted_out, usage


# ---------- hard filters ----------

@dataclass(frozen=True)
class Filters:
    """Each filter is off when its value is None/False. Defaults follow the project's spec."""
    thai_min: float | None = 0.6
    skip_private: bool = True
    max_age_days: int | None = 30
    min_followers: int | None = 10_000
    max_followers: int | None = None
    skip_shops: bool = True  # shops, brands and media pages (competitors included), as sorted by the model


def apply_filters(creators: list[dict], f: Filters, now: datetime | None = None) -> tuple[list[dict], dict[str, int]]:
    """Returns (kept, dropped). `dropped` counts, per filter, the creators that filter alone would remove."""
    now = now or datetime.now(timezone.utc)
    checks = {
        "thai": lambda c: f.thai_min is None or c["thai_share"] >= f.thai_min,
        "private": lambda c: not (f.skip_private and c["private"]),
        "recent": lambda c: f.max_age_days is None or bool(c["last_post"] and now - _iso(c["last_post"]) <= timedelta(days=f.max_age_days)),
        "min_followers": lambda c: f.min_followers is None or (c["followers"] or 0) >= f.min_followers,
        "max_followers": lambda c: f.max_followers is None or (c["followers"] or 0) <= f.max_followers,
        "shops": lambda c: not (f.skip_shops and c.get("kind") in ("shop", "media")),
    }
    dropped = {name: sum(not ok(c) for c in creators) for name, ok in checks.items()}
    return [c for c in creators if all(ok(c) for ok in checks.values())], dropped


# ---------- the job ----------

def start(aid: str, plan: list[dict]) -> dict:
    """Mark the search as running and hand it to a thread. The caller has already checked the profile and the token."""
    state = analyses.update(aid, lambda s: s["creators"].update({**analyses.EMPTY_CREATORS, "status": "running", "plan": plan, "items": s["creators"]["items"]}))  # the old list stays until the new one replaces it
    analyses.spawn(run, aid, plan)
    return state


def _sort_accounts(aid: str, profile: dict, creators: list[dict], earlier: list[dict]) -> str | None:
    """Label each creator as a creator, shop, media page or other. Best effort: a failure leaves them unlabelled
    (nothing is hidden) and is reported. Accounts labelled by an earlier search keep their label for free."""
    before = {c["username"]: c for c in earlier if c.get("kind")}
    for c in creators:
        old = before.get(c["username"])
        if old:
            c.update(kind=old["kind"], competitor=old["competitor"], kind_reason=old["kind_reason"])
    todo = [c for c in creators if not c["kind"]]
    cfg = config.llm_config()
    if not todo:
        return None
    if not cfg:
        return "No language model is set, so shops could not be told apart from creators."
    analyses.update(aid, lambda s: s["creators"].update(phase="sorting"))
    try:
        with httpx.Client(timeout=120) as http:
            labels, usage = classify(http, cfg, profile, todo)
    except (UpstreamError, httpx.HTTPError) as exc:
        return f"Shops could not be told apart from creators: {exc if isinstance(exc, UpstreamError) else 'network error'}."
    for c in todo:
        label = labels.get(c["username"])
        if label:
            c.update(kind=label["kind"], competitor=label["competitor"], kind_reason=label["reason"])

    def cost(s):
        c = s["cost"]
        c["llm_input_tokens"] += usage["input_tokens"]
        c["llm_output_tokens"] += usage["output_tokens"]
        c["llm_model"] = usage["model"]
        if usage["cost_usd"]:
            c["llm_usd"] = round(c["llm_usd"] + usage["cost_usd"], 6)
        else:
            c["llm_known"] = False  # the provider does not report cost
    analyses.update(aid, cost)
    return None if len(labels) == len(todo) else f"The model labelled {len(labels)} of {len(todo)} accounts; the rest are shown unlabelled."


def run(aid: str, plan: list[dict]) -> None:
    state = analyses.load(aid)
    if state is None or not state["profile"]:
        return
    tags = [p["hashtag"] for p in plan]
    try:
        analyses.update(aid, lambda s: s["creators"].update(phase="searching"))
        found, usd, cached = [], 0.0, True
        for run_input in runs(plan):
            items, spent, from_cache = apify_runner.run_actor(config.apify_token()[0], ACTOR, run_input)
            found += items
            usd += spent
            cached = cached and from_cache
        usd = round(usd, 5)
        videos = list({v.get("id") or id(v): v for v in found}.values())  # a video under two hashtags counts once
        creators = group_creators(videos)
        problem = _sort_accounts(aid, state["profile"], creators, state["creators"]["items"])
    except (UpstreamError, httpx.HTTPError) as exc:
        message = str(exc) if isinstance(exc, UpstreamError) else "Network error while contacting an external service."
        analyses.update(aid, lambda s: s["creators"].update(status="error", phase=None, error=message))
        return
    except Exception:
        analyses.log.exception("creator search %s failed", aid)
        analyses.update(aid, lambda s: s["creators"].update(status="error", phase=None, error="Something unexpected went wrong. Check the server log and try again."))
        return

    def done(s):
        s["creators"].update(status="done", phase=None, plan=plan, hashtags=tags, videos=len(videos), usd=usd, cached=cached, items=creators,
                             searched_at=datetime.now(timezone.utc).isoformat(), error=None, classify_error=problem)
        s["cost"]["apify_usd"] = round(s["cost"]["apify_usd"] + usd, 5)
        s["cost"]["cached_runs"] += int(cached)
    analyses.update(aid, done)
