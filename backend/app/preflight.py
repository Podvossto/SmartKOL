"""Check that a link the user typed really leads somewhere, BEFORE any paid Apify run or model call."""
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from .crawler import USER_AGENT

HEADERS = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8", "Accept-Language": "th,en;q=0.8"}
MAX_REDIRECTS = 5


class LinkError(Exception):
    """A user-facing reason the link can't be used."""


@dataclass
class Check:
    url: str  # final address (after redirects) — use this one
    warning: str | None = None


def _resolve(host: str) -> list[str]:
    try:
        return sorted({info[4][0] for info in socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)})
    except socket.gaierror:
        raise LinkError(f"We couldn't find a website at {host}. Check the spelling of the address.") from None


def assert_public_host(host: str) -> None:
    """Every address the name resolves to must be on the public internet (no localhost / LAN / cloud metadata)."""
    for address in _resolve(host):
        ip = ipaddress.ip_address(address.split("%")[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise LinkError("That address points to a private network, which isn't allowed.")


def check_website(url: str, http: httpx.Client) -> Check:
    for _ in range(MAX_REDIRECTS + 1):
        host = urlparse(url).hostname or ""
        assert_public_host(host)
        try:
            with http.stream("GET", url, headers=HEADERS) as resp:
                status, ctype, location = resp.status_code, resp.headers.get("content-type", ""), resp.headers.get("location")
        except httpx.TimeoutException:
            raise LinkError(f"{host} took too long to respond.") from None
        except httpx.ConnectError as exc:
            reason = "Couldn't make a secure connection to" if "ssl" in str(exc).lower() or "certificate" in str(exc).lower() else "Couldn't connect to"
            raise LinkError(f"{reason} {host}.") from None
        except httpx.HTTPError:
            raise LinkError(f"Couldn't reach {host}.") from None

        if 300 <= status < 400 and location:
            url = urljoin(url, location)
            if urlparse(url).scheme not in ("http", "https"):
                raise LinkError("The website redirects somewhere that isn't a web page.")
            continue
        if status in (404, 410):
            raise LinkError(f"That page doesn't exist (HTTP {status}). Check the address.")
        if status >= 500 and status != 503:
            raise LinkError(f"{host} is returning a server error (HTTP {status}). Try again later.")
        if ctype and not any(t in ctype.lower() for t in ("html", "xml", "text/plain")):
            raise LinkError(f"That link isn't a web page (it's {ctype.split(';')[0]}).")
        blocked = status in (401, 403, 429, 503)
        return Check(url, "This website restricts automated visitors, so what we can read may be limited." if blocked else None)
    raise LinkError("The website redirects too many times.")


def check_facebook(url: str) -> Check:
    """Facebook answers non-browsers with HTTP 400 for everything, so ask it like a browser: a real page has an
    og:title, a missing one only titles itself "Facebook". Free (no Apify)."""
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                page = browser.new_context(user_agent=USER_AGENT, locale="th-TH").new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(1500)
                og_title = page.locator('meta[property="og:title"]')
                if og_title.count() and (og_title.first.get_attribute("content") or "").strip():
                    return Check(url)
                if "/login" in page.url or "checkpoint" in page.url:
                    return Check(url, "Facebook asked for a login, so we couldn't confirm this page exists.")
            finally:
                browser.close()
    except PlaywrightError:
        return Check(url, "Couldn't reach Facebook to confirm this page exists.")
    raise LinkError("We couldn't find a public Facebook page at this address. Check the link, or make sure the page is public.")
