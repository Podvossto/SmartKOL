"""Pure helpers: validate brand URLs and pull social-profile links out of crawled pages."""
import html
import ipaddress
import re
from urllib.parse import parse_qs, quote, unquote, urlparse

_URL = re.compile(r"""https?://[^\s"'<>\\)\]]+""", re.I)
_FB_HOSTS = {"facebook.com", "www.facebook.com", "m.facebook.com", "web.facebook.com", "mbasic.facebook.com", "fb.com", "www.fb.com"}
_FB_NOT_PAGES = {
    "sharer", "sharer.php", "share", "share.php", "plugins", "tr", "dialog", "login", "login.php", "policies", "help",
    "legal", "privacy", "terms", "groups", "events", "watch", "marketplace", "hashtag", "photo", "photo.php",
    "permalink.php", "story.php", "l.php", "ads", "business", "reel", "reels", "stories", "gaming", "public",
    "people", "search", "settings", "recover", "r.php", "about", "video.php", "videos", "posts", "pg", "home.php",
    "notes", "places", "fundraisers",
}
_IG_NOT_PROFILES = {"p", "reel", "reels", "explore", "accounts", "stories", "tv", "direct"}
PLATFORMS = ("facebook", "tiktok", "instagram", "youtube", "line")


def validate_public_url(raw: str) -> str:
    """Normalise a brand website URL; reject anything that is not a public http(s) address."""
    url = raw.strip()
    if not url:
        raise ValueError("Website URL is empty")
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or not host or "." not in host and host != "localhost":
        raise ValueError("Enter a valid website address, e.g. https://example.com")
    if host == "localhost" or host.endswith((".local", ".internal", ".localhost")):
        raise ValueError("Local addresses are not allowed")
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("Private network addresses are not allowed")
    except ValueError as exc:
        if "not allowed" in str(exc):
            raise
    return url


def normalize_facebook(url: str) -> str | None:
    """Reduce any facebook.com URL to its page root, or None if it is not a page (share links, posts, …)."""
    p = urlparse(url.strip())
    if p.scheme not in ("http", "https") or p.netloc.lower() not in _FB_HOSTS:
        return None
    parts = [unquote(s) for s in p.path.split("/") if s]
    if not parts:
        return None
    first = parts[0].lower()
    if first == "profile.php":
        page_id = parse_qs(p.query).get("id", [""])[0]
        return f"https://www.facebook.com/profile.php?id={page_id}" if page_id.isdigit() else None
    if first == "pages" and len(parts) >= 3:
        return f"https://www.facebook.com/pages/{quote(parts[1])}/{quote(parts[2])}"
    if first in _FB_NOT_PAGES:
        return None
    return "https://www.facebook.com/" + quote(parts[0], safe=".-_")


def _tiktok(p) -> str | None:
    host = (p.hostname or "").lower()
    if host in ("vt.tiktok.com", "vm.tiktok.com"):
        return p.geturl().split("?")[0].rstrip("/") if p.path.strip("/") else None
    if host.endswith("tiktok.com"):
        seg = next((s for s in p.path.split("/") if s), "")
        if seg.startswith("@") and len(seg) > 1:
            return f"https://www.tiktok.com/{seg}"
    return None


def _instagram(p) -> str | None:
    if not (p.hostname or "").lower().endswith("instagram.com"):
        return None
    seg = next((s for s in p.path.split("/") if s), "")
    return f"https://www.instagram.com/{seg}" if seg and seg.lower() not in _IG_NOT_PROFILES else None


def _youtube(p) -> str | None:
    host = (p.hostname or "").lower()
    if not host.endswith("youtube.com"):
        return None
    parts = [s for s in p.path.split("/") if s]
    if parts and (parts[0].startswith("@") or (parts[0] in ("channel", "c", "user") and len(parts) > 1)):
        return "https://www.youtube.com/" + "/".join(parts[:2] if not parts[0].startswith("@") else parts[:1])
    return None


def _line(p) -> str | None:
    host, path = (p.hostname or "").lower(), p.path
    if host == "lin.ee" and path.strip("/"):
        return f"https://lin.ee{path.rstrip('/')}"
    if host in ("line.me", "page.line.me") and path.strip("/"):
        return p.geturl().split("?")[0]
    return None


def extract_socials(texts: list[str]) -> dict[str, list[str]]:
    """Social profile links found in HTML/markdown, deduplicated, in order of first appearance."""
    found: dict[str, list[str]] = {name: [] for name in PLATFORMS}
    seen: set[tuple[str, str]] = set()
    for text in texts:
        for match in _URL.finditer(html.unescape(text)):
            raw = match.group(0).rstrip(".,;:!?")
            p = urlparse(raw)
            candidates = {
                "facebook": normalize_facebook(raw),
                "tiktok": _tiktok(p),
                "instagram": _instagram(p),
                "youtube": _youtube(p),
                "line": _line(p),
            }
            for platform, url in candidates.items():
                if url and (platform, url.lower()) not in seen:
                    seen.add((platform, url.lower()))
                    found[platform].append(url)
    return found
