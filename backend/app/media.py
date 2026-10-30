"""Brand imagery for an analysis: a banner and a few sample pictures, kept as our own copies.

Facebook picture links are signed and expire within days, and loading them in the browser would contact Facebook
for every viewer. So the server downloads each image once (same SSRF rules and size cap as logos) and serves it
from the API. Everything shown here is read from the sources, nothing is generated.
"""
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

import httpx

from . import logos
from .db import connect

MAX_POST_IMAGES = 6
MAX_SITE_IMAGES = 3
MAX_BYTES = 4_000_000  # Facebook covers are routinely 2 MB PNGs; logos stay at 1 MB
KEY = re.compile(r"^(banner|s\d{1,2})$")


def _post_image(item: dict) -> str | None:
    for value in (item.get("thumbnail"), (item.get("image") or {}).get("uri"), (item.get("thumbnailImage") or {}).get("uri")):
        if isinstance(value, str) and urlparse(value).scheme in ("http", "https"):
            return value
    return None


def from_posts(posts: list[dict], limit: int = MAX_POST_IMAGES) -> list[dict]:
    """One picture per post, newest first. A video contributes its thumbnail and is flagged as a video."""
    out = []
    for post in posts:
        for item in post.get("media") or []:
            url = _post_image(item)
            if url:
                out.append({"source": "facebook", "url": url, "link": post.get("url") or post.get("topLevelUrl"),
                            "caption": " ".join(str(post.get("text") or "").split())[:120], "video": item.get("__typename") == "Video"})
                break
        if len(out) >= limit:
            break
    return out


def from_site(pages: list[dict], limit: int = MAX_SITE_IMAGES) -> list[dict]:
    """The share image (og:image) of each page we read: the picture the brand chose to represent that page."""
    out, seen = [], set()
    for page in pages:
        image = page.get("og_image")
        url = urljoin(page["url"], image) if image else None
        if url and urlparse(url).scheme in ("http", "https") and url not in seen:
            seen.add(url)
            out.append({"source": "website", "url": url, "link": page["url"], "caption": (page.get("title") or "")[:120], "video": False})
        if len(out) >= limit:
            break
    return out


def plan(cover: str | None, site_pages: list[dict], posts: list[dict]) -> list[dict]:
    """What to download: the Facebook cover as the banner (else the home page's share image), then the samples."""
    site = from_site(site_pages)
    banner = {"source": "facebook", "url": cover, "link": None, "caption": "", "video": False} if cover else (site.pop(0) if site else None)
    ordered, seen = [], set()
    for role, spec in [("banner", banner)] + [("sample", s) for s in from_posts(posts) + site]:
        if spec and spec["url"] not in seen:
            seen.add(spec["url"])
            ordered.append({**spec, "role": role})
    return ordered


def download(http: httpx.Client, specs: list[dict]) -> list[tuple[dict, str, bytes]]:
    """Fetch all of them side by side; anything that can't be fetched is simply left out."""
    with ThreadPoolExecutor(max_workers=6) as pool:
        fetched = list(pool.map(lambda spec: logos.fetch(http, spec["url"], max_bytes=MAX_BYTES), specs))
    return [(spec, *found) for spec, found in zip(specs, fetched) if found]


def save_all(analysis_id: str, items: list[tuple[dict, str, bytes]]) -> list[dict]:
    """Store the copies; returns the public description of each (never the original, expiring URL)."""
    described, n = [], 0
    with connect() as conn:
        conn.execute("DELETE FROM analysis_media WHERE analysis_id = ? AND key NOT LIKE 'c-%'", (analysis_id,))  # creator pictures stay
        for spec, content_type, data in items:
            key = "banner" if spec["role"] == "banner" else f"s{n}"
            n += spec["role"] != "banner"
            conn.execute("INSERT INTO analysis_media (analysis_id, key, content_type, data) VALUES (?, ?, ?, ?)", (analysis_id, key, content_type, data))
            described.append({"key": key, "role": spec["role"], "source": spec["source"], "link": spec["link"], "caption": spec["caption"], "video": spec["video"]})
    return described


def save_one(analysis_id: str, key: str, content_type: str, data: bytes) -> None:
    with connect() as conn:
        conn.execute("INSERT OR REPLACE INTO analysis_media (analysis_id, key, content_type, data) VALUES (?, ?, ?, ?)", (analysis_id, key, content_type, data))


def load(analysis_id: str, key: str) -> tuple[str, bytes] | None:
    with connect() as conn:
        row = conn.execute("SELECT content_type, data FROM analysis_media WHERE analysis_id = ? AND key = ?", (analysis_id, key)).fetchone()
    return (row[0], bytes(row[1])) if row else None


def delete(analysis_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM analysis_media WHERE analysis_id = ?", (analysis_id,))
