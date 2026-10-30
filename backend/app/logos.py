"""Brand logos: pick the best candidate image, fetch it on the server, keep our own copy.

The browser never loads anything from the brand's domain or Facebook: the copy is served from our own API,
so no viewer is tracked by a third party and expiring Facebook picture URLs don't matter.
"""
import re
from urllib.parse import urljoin, urlparse

import httpx

from .db import connect
from .preflight import HEADERS, LinkError, assert_public_host

MAX_BYTES = 1_000_000
MAX_REDIRECTS = 3
ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp", "image/avif", "image/gif", "image/svg+xml", "image/x-icon", "image/vnd.microsoft.icon"}
GOOD_ENOUGH_PX = 120  # smaller icons are blurry when shown at logo size


def _px(icon: dict) -> int:
    sizes = (icon.get("sizes") or "").lower()
    found = [int(n) for n in re.findall(r"(\d+)x\d+", sizes)]
    if found:
        return max(found)
    if "any" in sizes or str(icon.get("href", "")).lower().endswith(".svg"):
        return 512  # scalable
    return 180 if "apple-touch-icon" in (icon.get("rel") or "") else 0


def candidates(icons: list[dict], og_image: str | None, facebook_picture: str | None, site_url: str | None) -> list[str]:
    """Best-first: crisp site icons, then the Facebook profile picture, then small icons, then the share image."""
    sized = [(_px(icon), urljoin(site_url or "", icon["href"])) for icon in icons if icon.get("href")]
    crisp = [url for px, url in sorted(sized, reverse=True) if px >= GOOD_ENOUGH_PX]
    small = [url for px, url in sorted(sized, reverse=True) if px < GOOD_ENOUGH_PX]
    tail = [urljoin(site_url, og_image)] if site_url and og_image else []
    fallback = [urljoin(site_url, "/favicon.ico")] if site_url else []
    ordered = crisp + ([facebook_picture] if facebook_picture else []) + small + tail + fallback
    return list(dict.fromkeys(url for url in ordered if url and urlparse(url).scheme in ("http", "https")))


def fetch(http: httpx.Client, url: str, max_bytes: int = MAX_BYTES) -> tuple[str, bytes] | None:
    """One image, or None. Same SSRF rules as the website check; small, image-typed responses only."""
    for _ in range(MAX_REDIRECTS + 1):
        try:
            assert_public_host(urlparse(url).hostname or "")
            with http.stream("GET", url, headers={**HEADERS, "Accept": "image/*,*/*;q=0.5"}) as resp:
                if 300 <= resp.status_code < 400 and resp.headers.get("location"):
                    url = urljoin(url, resp.headers["location"])
                    continue
                content_type = resp.headers.get("content-type", "").split(";")[0].strip().lower()
                if resp.status_code != 200 or content_type not in ALLOWED_TYPES:
                    return None
                data = b""
                for chunk in resp.iter_bytes():
                    data += chunk
                    if len(data) > max_bytes:
                        return None
                return (content_type, data) if data else None
        except (LinkError, httpx.HTTPError):
            return None
    return None


def find(http: httpx.Client, urls: list[str]) -> tuple[str, bytes] | None:
    for url in urls:
        found = fetch(http, url)
        if found:
            return found
    return None


def save(analysis_id: str, content_type: str, data: bytes) -> None:
    with connect() as conn:
        conn.execute("INSERT OR REPLACE INTO analysis_logos (analysis_id, content_type, data) VALUES (?, ?, ?)",
                     (analysis_id, content_type, data))


def load(analysis_id: str) -> tuple[str, bytes] | None:
    with connect() as conn:
        row = conn.execute("SELECT content_type, data FROM analysis_logos WHERE analysis_id = ?", (analysis_id,)).fetchone()
    return (row[0], bytes(row[1])) if row else None


def delete(analysis_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM analysis_logos WHERE analysis_id = ?", (analysis_id,))
