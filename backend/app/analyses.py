"""Brand analysis pipeline. State lives in SQLite so the UI can poll it; heavy work runs in a thread.

Three ways in, depending on what the user typed:
  website + Facebook -> read both in parallel -> profile            (run_direct)
  Facebook only      -> read the page and its posts -> profile      (run_direct)
  website only       -> read the site, find Facebook links, let the user confirm one -> profile
                        (run_discovery, then run_profile after the confirmation)
"""
import json
import logging
import statistics
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx

from . import apify_runner, brand, config, crawler, logos, media
from .clients import UpstreamError
from .db import connect
from .social import normalize_facebook

log = logging.getLogger("smartkol.analyses")
_lock = threading.Lock()

DISCOVERY_STEPS = [("crawl", "Reading the website"), ("find", "Finding Facebook pages"), ("check", "Checking Facebook pages")]
PROFILE_STEPS = [("posts", "Reading recent Facebook posts"), ("profile", "Writing the brand profile")]
MAX_CANDIDATES = 3
STORED_PAGE_CHARS = 8000
POSTS_TO_READ = 10
# The TikTok creator search of one analysis (app/discovery.py fills it in).
EMPTY_CREATORS = {"status": "idle", "phase": None, "plan": [], "hashtags": [], "videos": 0, "usd": 0.0, "cached": False,
                  "searched_at": None, "error": None, "classify_error": None, "items": []}


def spawn(fn, *args) -> None:
    threading.Thread(target=fn, args=args, daemon=True).start()


# ---------- state store ----------

def _steps(defs) -> list[dict]:
    return [{"key": k, "label": label, "state": "pending", "detail": None} for k, label in defs]


def direct_steps(has_site: bool, has_facebook: bool) -> list[tuple[str, str]]:
    steps = []
    if has_site:
        steps.append(("crawl", "Reading the website"))
    if has_facebook:
        steps.append(("facebook", "Reading the Facebook page and posts"))
    return steps + [("profile", "Writing the brand profile")]


def create(website_url: str | None, facebook_url: str | None, warnings: list[str] | None = None,
           discover: bool = False, eta: tuple[int, int] | None = None) -> dict:
    """`discover`: website only, and the user asked us to look for its Facebook page (they then confirm one)."""
    now = datetime.now(timezone.utc).isoformat()
    mode = "both" if website_url and facebook_url else "website" if website_url else "facebook"
    discover = discover and mode == "website"
    state = {
        "id": uuid.uuid4().hex[:12],
        "mode": mode,
        "discover": discover,
        "eta": list(eta) if eta else None,
        "status": "running",
        "website_url": website_url,
        "facebook_url": facebook_url,
        "warnings": warnings or [],
        "steps": _steps(DISCOVERY_STEPS if discover else direct_steps(bool(website_url), bool(facebook_url))),
        "website": None,
        "facebook": None,
        "facebook_candidates": [],
        "recommended": None,
        "selected_facebook": None,
        "requested_facebook": None,
        "profile": None,
        "creators": dict(EMPTY_CREATORS, hashtags=[], items=[]),
        "has_logo": False,
        "media": [],
        "cost": {"apify_usd": 0.0, "llm_usd": 0.0, "llm_known": True, "llm_input_tokens": 0, "llm_output_tokens": 0,
                 "llm_model": None, "cached_runs": 0},
        "error": None,
        "internal": {"site_pages": []},
        "created_at": now,
    }
    with _lock, connect() as conn:
        conn.execute("INSERT INTO analyses (id, state, created_at, updated_at) VALUES (?, ?, ?, ?)",
                     (state["id"], json.dumps(state), now, now))
    return state


def _normalize(s: dict) -> dict:
    """Analyses saved by an older version lack newer keys; fill them in so old analyses keep opening."""
    s.setdefault("facebook_url", s.get("facebook_url_input"))
    s.setdefault("discover", s.get("mode") == "website")  # before this option existed, a website alone always went looking
    s.setdefault("eta", None)
    s.setdefault("mode", "both" if s.get("website_url") and s["facebook_url"] else "website" if s.get("website_url") else "facebook")
    for key, default in (("has_logo", False), ("media", []), ("warnings", []), ("facebook", None), ("facebook_candidates", []), ("selected_facebook", None),
                         ("requested_facebook", None), ("recommended", None), ("profile", None), ("website", None), ("error", None)):
        s.setdefault(key, default)
    s.setdefault("creators", dict(EMPTY_CREATORS, hashtags=[], items=[]))
    for key, default in EMPTY_CREATORS.items():  # a search saved by an older version lacks newer fields
        s["creators"].setdefault(key, type(default)() if isinstance(default, (list, dict)) else default)
    s.setdefault("internal", {}).setdefault("site_pages", [])
    if s["profile"]:
        try:  # a profile written by an older version is carried into the current structure
            s["profile"] = brand.BrandProfile.model_validate(s["profile"]).model_dump()
        except ValueError:
            log.warning("profile of analysis %s does not fit the current structure", s.get("id"))
    return s


def load(aid: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT state FROM analyses WHERE id = ?", (aid,)).fetchone()
    return _normalize(json.loads(row[0])) if row else None


def update(aid: str, mutate) -> dict:
    with _lock, connect() as conn:
        row = conn.execute("SELECT state FROM analyses WHERE id = ?", (aid,)).fetchone()
        if row is None:  # deleted while a job was still running
            return {}
        state = _normalize(json.loads(row[0]))
        mutate(state)
        conn.execute("UPDATE analyses SET state = ?, updated_at = ? WHERE id = ?",
                     (json.dumps(state), datetime.now(timezone.utc).isoformat(), aid))
    return state


def public(state: dict) -> dict:
    """The creator list is served by its own endpoint (filtered), so polling an analysis stays light."""
    out = {k: v for k, v in state.items() if k != "internal"}
    out["creators"] = {**{k: v for k, v in state["creators"].items() if k != "items"}, "found": len(state["creators"]["items"])}
    return out


def mark_interrupted() -> None:
    """Jobs die with the process; don't leave analyses spinning forever after a restart."""
    with connect() as conn:
        rows = conn.execute("SELECT id, state FROM analyses").fetchall()
    for aid, raw in rows:
        state = json.loads(raw)
        if state["status"] in ("running", "profiling"):
            update(aid, lambda s: s.update(status="error", error="The server restarted while this analysis was running. Start it again."))
        if (state.get("creators") or {}).get("status") == "running":
            update(aid, lambda s: s["creators"].update(status="error", error="The server restarted during the search. Search again."))


def _step(aid: str, key: str, state_name: str, detail: str | None = None) -> None:
    def mutate(s):
        for step in s["steps"]:
            if step["key"] == key:
                step["state"], step["detail"] = state_name, detail
    update(aid, mutate)


def _fail(aid: str, message: str) -> None:
    def mutate(s):
        s["status"], s["error"] = "error", message
        for step in s["steps"]:
            if step["state"] == "running":
                step["state"] = "error"
    update(aid, mutate)


def _add_apify_cost(aid: str, usd: float, cached: bool) -> None:
    def mutate(s):
        s["cost"]["apify_usd"] = round(s["cost"]["apify_usd"] + usd, 5)
        s["cost"]["cached_runs"] += int(cached)
    update(aid, mutate)


def _guard(job):
    """Run a job; turn any failure into a user-readable error state instead of a stuck spinner."""
    def wrapper(aid, *args):
        if load(aid) is None:  # deleted before the job got going
            return
        try:
            job(aid, *args)
        except (UpstreamError, httpx.HTTPError) as exc:
            if load(aid) is None:  # cancelled while it ran: nobody is waiting for an answer
                return
            _fail(aid, str(exc) if isinstance(exc, UpstreamError) else "Network error while contacting an external service.")
        except Exception:
            if load(aid) is None:
                return
            log.exception("analysis %s failed", aid)
            _fail(aid, "Something unexpected went wrong. Check the server log and try again.")
    return wrapper


# ---------- facebook page helpers ----------

def _parse_time(value: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None
    except ValueError:
        return None


def _host(url: str | None) -> str:
    return (urlparse(url if url and "://" in url else f"https://{url or ''}").hostname or "").removeprefix("www.")


def _same_site(a: str | None, b: str | None) -> bool:
    ha, hb = _host(a), _host(b)
    return bool(ha and hb and (ha == hb or ha.endswith("." + hb) or hb.endswith("." + ha)))


def build_candidates(urls: list[str], pages: list[dict], posts: list[dict], site_url: str | None, provided: bool) -> list[dict]:
    def key(raw: str | None) -> str:
        return (normalize_facebook(raw or "") or "").lower()

    pages_by = {key(p.get("facebookUrl") or p.get("pageUrl")): p for p in pages}
    posts_by: dict[str, list[dict]] = {}
    for post in posts:
        posts_by.setdefault(key(post.get("inputUrl") or post.get("facebookUrl")), []).append(post)

    now, candidates = datetime.now(timezone.utc), []
    for i, url in enumerate(urls):
        page = pages_by.get(url.lower()) or (pages[i] if len(pages) == len(urls) else None)
        mine = posts_by.get(url.lower()) or (posts if len(urls) == 1 else [])
        times = [t for t in (_parse_time(p.get("time")) for p in mine) if t]
        last = max(times) if times else None
        warnings = []
        if page is None:
            warnings.append("Could not read this page")
        else:
            if last is None:
                warnings.append("No public posts could be read")
            elif now - last > timedelta(days=365):
                warnings.append("No posts in over a year — may be an inactive or foreign page")
            if site_url and page.get("website") and not _same_site(page["website"], site_url):
                warnings.append("The website listed on this page is different from yours")
        candidates.append({
            "url": url,
            "source": "provided" if provided else "website",
            "readable": page is not None,
            "title": (page or {}).get("title"),
            "category": (page or {}).get("category"),
            "followers": (page or {}).get("followers"),
            "address": (page or {}).get("address"),
            "website": (page or {}).get("website"),
            "intro": ((page or {}).get("intro") or "")[:600],
            "picture": (page or {}).get("profilePictureUrl"),
            "cover": (page or {}).get("coverPhotoUrl"),
            "created": (page or {}).get("creation_date"),
            "last_post_at": last.isoformat() if last else None,
            "website_match": bool(site_url and page and _same_site(page.get("website"), site_url)),
            "warnings": warnings,
        })
    return candidates


def eta_seconds(fb_url: str | None, discover: bool) -> tuple[int, int]:
    """Rough (low, high) wait in seconds, from a handful of earlier runs: cached or website-only runs finished in
    15-60 s; reading a Facebook page fresh adds about a minute; looking for the page adds another half minute."""
    if discover:
        return (45, 120)
    if fb_url and not apify_runner.facebook_cached(fb_url, POSTS_TO_READ):
        return (60, 120)
    return (20, 60)


def brand_link_warning(site_url: str, site_facebook_links: list[str], page: dict) -> str | None:
    """Do this website and this Facebook page look like the same brand? Evidence only, no guessing:
    the page lists the website, or the website links to the page. Returns a warning when neither holds."""
    mine = normalize_facebook(page.get("url") or "") or ""
    if _same_site(page.get("website"), site_url) or any((normalize_facebook(u) or "").lower() == mine.lower() for u in site_facebook_links):
        return None
    if page.get("website"):
        return (f"The Facebook page lists {_host(page['website'])} as its website, not {_host(site_url)}. "
                "Check both belong to the same brand, or the profile will mix two businesses.")
    return ("We couldn't confirm that this Facebook page belongs to this website: the page lists no website and the site "
            "doesn't link to it. Check both are the same brand.")


def estimate(site_url: str | None, fb_url: str | None, find_facebook: bool = False) -> dict:
    """Apify cost range for an analysis before it runs. `high` is what it costs if nothing is cached."""
    page, posts = apify_runner.FB_PAGE_USD, apify_runner.FB_POSTS_START_USD
    each = apify_runner.FB_POST_USD
    full_read = page + posts + POSTS_TO_READ * each
    if fb_url:
        cached = apify_runner.facebook_cached(fb_url, POSTS_TO_READ)
        low = high = 0.0 if cached else round(full_read, 4)
        return {"low_usd": low, "high_usd": high, "cached": cached,
                "note": "Reads the Facebook page and its latest posts" + (" (served from cache)" if cached else "")}
    if not find_facebook:
        return {"low_usd": 0.0, "high_usd": 0.0, "cached": False, "note": "Reads the website only, which is free"}
    # website only: check up to MAX_CANDIDATES pages it links to (2 posts each), then read the one you pick
    discover = lambda n: n * page + posts + 2 * n * each
    return {"low_usd": round(discover(1) + posts + POSTS_TO_READ * each, 4),
            "high_usd": round(discover(MAX_CANDIDATES) + posts + POSTS_TO_READ * each, 4), "cached": False,
            "note": "Looks for the brand's Facebook page on its website, then reads the one you pick"}


def recommend(candidates: list[dict]) -> str | None:
    def score(c: dict) -> tuple:
        recent = bool(c["last_post_at"] and datetime.now(timezone.utc) - _parse_time(c["last_post_at"]) < timedelta(days=90))
        return (c["readable"], 3 * c["website_match"] + 2 * recent, c["followers"] or 0)
    readable = [c for c in candidates if c["readable"]]
    return max(readable, key=score)["url"] if readable else None


def facebook_stats(posts: list[dict], followers: int | None) -> dict:
    """Plain numbers from the posts we read — not model output."""
    if not posts:
        return {"posts_read": 0}

    def num(p: dict, k: str) -> int:
        return p.get(k) or 0

    now = datetime.now(timezone.utc)
    times = sorted(t for t in (_parse_time(p.get("time")) for p in posts) if t)
    span_days = (times[-1] - times[0]).total_seconds() / 86400 if len(times) > 1 else 0
    avg_interactions = statistics.mean(num(p, "likes") + num(p, "comments") + num(p, "shares") for p in posts)
    top = max(posts, key=lambda p: num(p, "likes") + 2 * num(p, "comments") + 3 * num(p, "shares"))
    return {
        "posts_read": len(posts),
        "avg_likes": round(statistics.mean(num(p, "likes") for p in posts)),
        "avg_comments": round(statistics.mean(num(p, "comments") for p in posts)),
        "avg_shares": round(statistics.mean(num(p, "shares") for p in posts)),
        "posts_last_30d": sum(1 for t in times if now - t <= timedelta(days=30)),
        "posts_per_week": round(len(times) / (span_days / 7), 1) if span_days >= 1 else None,
        "engagement_rate_pct": round(avg_interactions / followers * 100, 2) if followers else None,
        "top_post": {"text": " ".join(str(top.get("text") or "").split())[:160], "likes": num(top, "likes"),
                     "comments": num(top, "comments"), "shares": num(top, "shares"), "url": top.get("url") or top.get("topLevelUrl")},
    }


# ---------- building blocks ----------

def _read_website(aid: str, url: str) -> crawler.SiteData:
    _step(aid, "crawl", "running")
    site = crawler.crawl_site(url)

    def store(s):
        s["website"] = {
            "url": site.start_url,
            "title": site.pages[0].title if site.pages else None,
            "description": site.pages[0].description if site.pages else None,
            "pages": [{"url": p.url, "title": p.title, "chars": len(p.markdown)} for p in site.pages],
            "socials": site.socials,
        }
        s["internal"]["site_pages"] = [
            {"url": p.url, "title": p.title, "description": p.description, "text": p.markdown[:STORED_PAGE_CHARS], "og_image": p.og_image}
            for p in site.pages
        ]
        home = site.pages[0]
        s["internal"]["site_icons"] = {"url": site.start_url, "icons": home.icons, "og_image": home.og_image}
    update(aid, store)
    _step(aid, "crawl", "done", f"{len(site.pages)} pages")
    return site


def _read_facebook(aid: str, token: str, url: str, site_url: str | None, known: dict | None = None) -> tuple[dict, list[dict], bool]:
    """Page details (reused from discovery when known) + recent posts -> (candidate, posts, posts_from_cache)."""
    candidate = known
    if candidate is None:
        pages, usd, cached = apify_runner.facebook_pages(token, [url])
        _add_apify_cost(aid, usd, cached)
        candidate = build_candidates([url], pages, [], site_url, provided=True)[0]
        if not candidate["readable"]:
            raise UpstreamError("We couldn't read that Facebook page. Check that the link is a public page.")
    posts, usd, cached = apify_runner.facebook_posts(token, [url], POSTS_TO_READ)
    _add_apify_cost(aid, usd, cached)
    posts.sort(key=lambda p: p.get("time") or "", reverse=True)
    return candidate, posts, cached


def _store_facebook(aid: str, url: str, candidate: dict, posts: list[dict]) -> None:
    # The page details were read before its posts, so fill in what the posts tell us.
    times = [t for t in (_parse_time(p.get("time")) for p in posts) if t]
    warnings = [w for w in candidate["warnings"] if not (posts and w.startswith("No public posts"))]
    if times and datetime.now(timezone.utc) - max(times) > timedelta(days=365):
        warnings.append("No posts in over a year — may be an inactive or foreign page")

    def store(s):
        s["facebook"] = {**candidate, "last_post_at": max(times).isoformat() if times else candidate.get("last_post_at"),
                         "warnings": list(dict.fromkeys(warnings)), "stats": facebook_stats(posts, candidate.get("followers"))}
        s["selected_facebook"] = url
    update(aid, store)


def _write_profile(aid: str, site_pages: list[dict], candidate: dict | None, posts: list[dict]) -> None:
    cfg = config.llm_config()
    _step(aid, "profile", "running")
    with httpx.Client(timeout=120) as http:
        profile, usage = brand.build_profile(http, cfg, site_pages, candidate, posts)

    def store(s):
        s["profile"] = profile.model_dump()
        s["status"] = "done"
        c = s["cost"]
        c["llm_input_tokens"] += usage["input_tokens"]
        c["llm_output_tokens"] += usage["output_tokens"]
        c["llm_model"] = usage["model"]
        if usage["cost_usd"]:
            c["llm_usd"] = round(c["llm_usd"] + usage["cost_usd"], 6)
        else:
            c["llm_known"] = False  # provider does not report cost
    update(aid, store)
    _step(aid, "profile", "done", f"{usage['calls']} model call(s)")


def _refresh_logo(aid: str) -> None:
    """Best effort: a missing logo must never fail an analysis. Runs once, with whatever we know by then."""
    try:
        state = load(aid)
        if state["has_logo"]:
            return
        site = state["internal"].get("site_icons") or {}
        page = state.get("facebook")
        urls = logos.candidates(site.get("icons", []), site.get("og_image"), (page or {}).get("picture"), site.get("url"))
        with httpx.Client(timeout=8) as http:
            found = logos.find(http, urls) if urls else None
        if found:
            logos.save(aid, *found)
            update(aid, lambda s: s.update(has_logo=True))
    except Exception:
        log.warning("logo lookup failed for %s", aid, exc_info=True)


def _refresh_media(aid: str, candidate: dict | None, posts: list[dict]) -> None:
    """Best effort, like the logo: a banner and a few sample pictures from what was just read."""
    try:
        specs = media.plan((candidate or {}).get("cover"), load(aid)["internal"]["site_pages"], posts)
        if not specs:
            return
        with httpx.Client(timeout=10) as http:
            described = media.save_all(aid, media.download(http, specs))
        update(aid, lambda s: s.update(media=described))
    except Exception:
        log.warning("media lookup failed for %s", aid, exc_info=True)


def _title(state: dict) -> str:
    profile, page, site = state.get("profile"), state.get("facebook"), state.get("website")
    if profile:
        return profile["brand_name"]
    if page and page.get("title"):
        return page["title"].split("|")[0].strip()
    if site and site.get("title"):
        return site["title"].split("|")[-1].strip()
    return _host(state.get("website_url")) or (state.get("facebook_url") or "").rsplit("/", 1)[-1] or "Untitled analysis"


def recent(limit: int = 12) -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT state FROM analyses ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for (raw,) in rows:
        s = _normalize(json.loads(raw))
        out.append({
            "id": s["id"], "title": _title(s), "mode": s["mode"], "status": s["status"], "has_logo": s["has_logo"],
            "created_at": s["created_at"], "website": _host(s.get("website_url")) or None,
            "facebook": (s.get("facebook_url") or s.get("selected_facebook") or "").rsplit("/", 1)[-1] or None,
        })
    return out


def remove(aid: str) -> bool:
    with _lock, connect() as conn:
        deleted = conn.execute("DELETE FROM analyses WHERE id = ?", (aid,)).rowcount > 0
        conn.execute("DELETE FROM analysis_logos WHERE analysis_id = ?", (aid,))
        conn.execute("DELETE FROM analysis_media WHERE analysis_id = ?", (aid,))
    return deleted


# ---------- jobs ----------

@_guard
def run_direct(aid: str) -> None:
    """Website and/or Facebook page given up front: no confirmation needed, read both at the same time."""
    state = load(aid)
    token = config.apify_token()[0]
    site_url, fb_url = state["website_url"], state["facebook_url"]
    result: dict = {}

    def website_job():
        result["site"] = _read_website(aid, site_url)

    def facebook_job():
        _step(aid, "facebook", "running")
        candidate, posts, cached = _read_facebook(aid, token, fb_url, site_url)
        _store_facebook(aid, fb_url, candidate, posts)
        result["fb"] = (candidate, posts)
        _step(aid, "facebook", "done", f"{len(posts)} posts" + (" (cached)" if cached else ""))

    jobs = ([website_job] if site_url else []) + ([facebook_job] if fb_url else [])
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        for future in [pool.submit(job) for job in jobs]:
            future.result()  # re-raises the first failure

    candidate, posts = result.get("fb", (None, []))
    if candidate and "site" in result:
        warning = brand_link_warning(site_url, result["site"].socials["facebook"], candidate)
        if warning:
            update(aid, lambda s: s["warnings"].append(warning))
    _refresh_logo(aid)
    _refresh_media(aid, candidate, posts)
    _write_profile(aid, load(aid)["internal"]["site_pages"], candidate, posts)


@_guard
def run_discovery(aid: str) -> None:
    """Website only: read it, then list the Facebook pages it links to so the user can confirm one."""
    state = load(aid)
    token = config.apify_token()[0]
    site = _read_website(aid, state["website_url"])
    _refresh_logo(aid)  # website icons only for now; the Facebook picture is added once a page is chosen

    urls = site.socials["facebook"][:MAX_CANDIDATES]
    _step(aid, "find", "done", f"{len(urls)} found" if urls else "none found on the website")
    if not urls:
        update(aid, lambda s: s.update(status="awaiting_facebook"))
        return

    _step(aid, "check", "running")
    pages, usd_pages, cached_pages = apify_runner.facebook_pages(token, urls)
    _add_apify_cost(aid, usd_pages, cached_pages)
    posts, usd_posts, cached_posts = apify_runner.facebook_posts(token, urls, 2)
    _add_apify_cost(aid, usd_posts, cached_posts)
    candidates = build_candidates(urls, pages, posts, site.start_url, provided=False)

    def store_candidates(s):
        s["facebook_candidates"] = candidates
        s["recommended"] = recommend(candidates)
        s["status"] = "awaiting_facebook"
    update(aid, store_candidates)
    _step(aid, "check", "done", "from cache" if cached_pages and cached_posts else None)


@_guard
def run_profile(aid: str, facebook_url: str | None) -> None:
    """After the user confirmed (or skipped) a Facebook page found from the website."""
    state = load(aid)
    token = config.apify_token()[0]
    candidate, posts = None, []
    if facebook_url:
        _step(aid, "posts", "running")
        known = next((c for c in state["facebook_candidates"] if c["url"].lower() == facebook_url.lower() and c["readable"]), None)
        candidate, posts, cached = _read_facebook(aid, token, facebook_url, state["website_url"], known)
        _store_facebook(aid, facebook_url, candidate, posts)
        _step(aid, "posts", "done", f"{len(posts)} posts" + (" (cached)" if cached else ""))
    else:
        _step(aid, "posts", "skipped", "no Facebook page selected")
    _refresh_logo(aid)
    _refresh_media(aid, candidate, posts)
    _write_profile(aid, state["internal"]["site_pages"], candidate, posts)


def retry(aid: str) -> dict:
    """Run a failed analysis again from the right place. Apify results are cached, so re-reading costs nothing."""
    state = load(aid)
    if state["discover"] and state["steps"][0]["key"] == "posts":  # failed after the user confirmed a page
        return begin_profile(aid, state["requested_facebook"])

    def reset(s):
        defs = DISCOVERY_STEPS if s["discover"] else direct_steps(bool(s["website_url"]), bool(s["facebook_url"]))
        s["status"], s["error"], s["steps"] = "running", None, _steps(defs)
    restarted = update(aid, reset)
    spawn(run_discovery if state["discover"] else run_direct, aid)
    return restarted


def begin_profile(aid: str, facebook_url: str | None) -> dict:
    def mutate(s):
        s["status"], s["error"], s["steps"] = "profiling", None, _steps(PROFILE_STEPS)
        s["requested_facebook"] = facebook_url
    state = update(aid, mutate)
    spawn(run_profile, aid, facebook_url)
    return state
