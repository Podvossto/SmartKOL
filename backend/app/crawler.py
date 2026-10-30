"""Read a brand website with Playwright: a few relevant pages as clean text + social links. No third-party service."""
import re
from dataclasses import dataclass, field
from urllib.parse import unquote, urljoin, urlparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

from .clients import UpstreamError
from .social import extract_socials

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
PAGE_CHARS = 20000
_WANTED = re.compile(
    r"about|story|brand|product|shop|menu|collection|service|catalog|our-|who-we|"
    r"เกี่ยวกับ|สินค้า|บริการ|เมนู|เรื่องราว|ผลิตภัณฑ์", re.I)
_SKIPPED = re.compile(
    r"privacy|terms|policy|cookie|login|register|cart|checkout|career|investor|board|management|organization|"
    r"sitemap|\.(pdf|jpe?g|png|gif|svg|webp|zip)(\?|$)|นโยบาย|สมัครงาน", re.I)

# Runs in the page: text of visible leaf blocks in reading order (headings marked with #), minus nav/footer/chrome.
_EXTRACT = """() => {
  const SKIP = 'script,style,noscript,svg,iframe,template,nav,footer,aside,form,select,[role=navigation],[aria-hidden=true]';
  const BLOCK = 'h1,h2,h3,h4,h5,h6,p,li,div,section,article,td,th,blockquote,figcaption,dt,dd,summary,pre,ul,ol,table,main,header';
  const meta = (sel) => document.querySelector(sel)?.getAttribute('content') || null;
  const lines = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT, {
    acceptNode: (el) => el.matches(SKIP) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT });
  for (let el = walker.nextNode(); el; el = walker.nextNode()) {
    if (!el.matches(BLOCK) || el.querySelector(BLOCK) || !el.checkVisibility()) continue;
    const text = (el.innerText || '').replace(/\\s+/g, ' ').trim();
    if (text.length < 2 || text === lines[lines.length - 1]) continue;
    const level = /^H([1-6])$/.exec(el.tagName);
    lines.push(level ? '#'.repeat(+level[1]) + ' ' + text : text);
  }
  const ld = [...document.querySelectorAll('script[type="application/ld+json"]')].map((s) => s.textContent.trim()).join(' ').slice(0, 1500);
  return {
    title: document.title || null,
    description: meta('meta[name=description]') || meta('meta[property="og:description"]'),
    site_name: meta('meta[property="og:site_name"]'),
    text: lines.join('\\n\\n'),
    structured_data: ld || null,
    og_image: meta('meta[property="og:image"]'),
    icons: [...document.querySelectorAll('link[rel~="icon"],link[rel="apple-touch-icon"],link[rel="apple-touch-icon-precomposed"]')]
      .map((l) => ({ href: l.href, rel: l.rel, sizes: l.getAttribute('sizes') || '' })),
    links: [...document.querySelectorAll('a[href]')].map((a) => a.href),
  };
}"""


@dataclass
class Page:
    url: str
    title: str | None
    description: str | None
    markdown: str
    icons: list[dict] = field(default_factory=list)
    og_image: str | None = None


@dataclass
class SiteData:
    start_url: str
    pages: list[Page]
    socials: dict[str, list[str]] = field(default_factory=dict)


def pick_links(start_url: str, internal_hrefs: list[str], limit: int) -> list[str]:
    """Best internal pages to read: product/about/menu first, shallow paths first, noise removed."""
    host = urlparse(start_url).netloc
    start = start_url.rstrip("/")
    scored: dict[str, tuple[int, int, int]] = {}
    for href in internal_hrefs:
        url = urljoin(start_url, href).split("#")[0].split("?")[0].rstrip("/")
        parsed = urlparse(url)
        if parsed.netloc != host or url == start or not parsed.path or _SKIPPED.search(unquote(url)):
            continue
        depth = len([s for s in parsed.path.split("/") if s])
        scored[url] = (0 if _WANTED.search(unquote(parsed.path)) else 1, depth, len(url))
    return sorted(scored, key=scored.__getitem__)[:limit]


def _light(route) -> None:
    """Skip images, video and fonts: we only read text, and it makes pages load several times faster."""
    if route.request.resource_type in ("image", "media", "font"):
        route.abort()
    else:
        route.continue_()


def _read(context, url: str) -> tuple[Page, str, list[str]]:
    page = context.new_page()
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
        try:
            page.wait_for_load_state("networkidle", timeout=6000)  # JS-rendered sites settle here; best effort
        except PlaywrightTimeout:
            pass
        if response is not None and response.status >= 400 and response.status not in (401, 403, 429, 503):
            raise UpstreamError(f"The website returned HTTP {response.status} for {url}")
        data = page.evaluate(_EXTRACT)
        text = data["text"]
        if data["structured_data"]:
            text += "\n\nStructured data: " + data["structured_data"]
        page_data = Page(url, data["title"], data["description"], text[:PAGE_CHARS], data["icons"], data["og_image"])
        return page_data, page.content(), data["links"]
    except PlaywrightTimeout:
        raise UpstreamError("The website took too long to load.") from None
    except PlaywrightError as exc:
        raise UpstreamError(f"Could not open the website: {str(exc).splitlines()[0][:160]}") from None
    finally:
        page.close()


def crawl_site(start_url: str, max_pages: int = 5) -> SiteData:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            context = browser.new_context(user_agent=USER_AGENT, locale="th-TH", viewport={"width": 1366, "height": 900})
            context.route("**/*", _light)
            home, home_html, hrefs = _read(context, start_url)
            pages, html_blobs = [home], [home_html]
            for url in pick_links(start_url, hrefs, max_pages - 1):
                try:
                    page, html, _ = _read(context, url)
                except UpstreamError:
                    continue  # one broken subpage should not sink the analysis
                pages.append(page)
                html_blobs.append(html)
            return SiteData(start_url, pages, extract_socials(html_blobs))
        finally:
            browser.close()
