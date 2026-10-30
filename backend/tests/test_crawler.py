import unittest

from app.clients import UpstreamError
from app.crawler import crawl_site
from tests.helpers import serve

HOME = """<!doctype html><html lang="th"><head><title>Brand Home</title>
<meta name="description" content="Handmade cakes in Bangkok">
<meta property="og:site_name" content="Brand"><meta property="og:image" content="/share.jpg">
<link rel="icon" href="/favicon-32.png" sizes="32x32"><link rel="apple-touch-icon" href="/apple.png" sizes="180x180"></head><body>
<nav><a href="/menu">Menu</a> <a href="/privacy">Privacy Policy</a> <span>NAVIGATION-NOISE</span></nav>
<div id="app"></div>
<script>document.getElementById('app').innerHTML =
  '<h1>Handmade Cakes</h1><p>We bake daily in Bangkok. เค้กโฮมเมดทุกวัน</p><ul><li>Lava cake</li><li>Tiramisu</li></ul>';</script>
<script type="application/ld+json">{"@type":"Bakery","name":"Brand Bakery","priceRange":"$$"}</script>
<a href="/products/cake">Our cake</a>
<footer><a href="https://www.facebook.com/brandbakery/">Facebook</a>
<a href="https://www.instagram.com/brandbakery">IG</a> <span>FOOTER-NOISE cookie policy</span></footer>
</body></html>"""

ROUTES = {
    "/": HOME,
    "/menu": "<html><head><title>Menu</title></head><body><h2>Menu</h2><p>Lava cake 120 baht</p></body></html>",
    "/products/cake": "<html><head><title>Cake</title></head><body><h1>Chocolate cake</h1><div>Rich and dark</div></body></html>",
    "/privacy": "<html><body><p>We collect cookies</p></body></html>",
}


class CrawlSiteTest(unittest.TestCase):
    """Runs against a real headless Chromium and a local server."""

    def test_reads_javascript_rendered_pages_as_clean_text(self):
        with serve(ROUTES) as base:
            site = crawl_site(base + "/", max_pages=4)
        home = site.pages[0]
        self.assertEqual((home.title, home.description), ("Brand Home", "Handmade cakes in Bangkok"))
        self.assertIn("# Handmade Cakes", home.markdown)  # rendered by JS, heading kept as a heading
        self.assertIn("We bake daily in Bangkok. เค้กโฮมเมดทุกวัน", home.markdown)
        self.assertIn("Lava cake", home.markdown)
        self.assertIn("Brand Bakery", home.markdown)  # structured data survives
        self.assertNotIn("NAVIGATION-NOISE", home.markdown)
        self.assertNotIn("FOOTER-NOISE", home.markdown)

    def test_collects_icons_and_share_image_for_the_logo(self):
        with serve(ROUTES) as base:
            home = crawl_site(base + "/", max_pages=1).pages[0]
        self.assertEqual({(i["href"].removeprefix(base), i["sizes"]) for i in home.icons}, {("/favicon-32.png", "32x32"), ("/apple.png", "180x180")})
        self.assertEqual(home.og_image, "/share.jpg")

    def test_follows_useful_links_and_skips_policy_pages(self):
        with serve(ROUTES) as base:
            site = crawl_site(base + "/", max_pages=4)
        paths = {p.url.removeprefix(base) for p in site.pages}
        self.assertEqual(paths, {"/", "/menu", "/products/cake"})
        self.assertIn("Lava cake 120 baht", next(p for p in site.pages if p.url.endswith("/menu")).markdown)

    def test_collects_social_links(self):
        with serve(ROUTES) as base:
            site = crawl_site(base + "/", max_pages=1)
        self.assertEqual(site.socials["facebook"], ["https://www.facebook.com/brandbakery"])
        self.assertEqual(site.socials["instagram"], ["https://www.instagram.com/brandbakery"])
        self.assertEqual(len(site.pages), 1)

    def test_a_broken_subpage_does_not_fail_the_crawl(self):
        routes = {**ROUTES, "/menu": (500, {}, "boom")}
        with serve(routes) as base:
            site = crawl_site(base + "/", max_pages=4)
        self.assertNotIn("/menu", {p.url.removeprefix(base) for p in site.pages})
        self.assertGreaterEqual(len(site.pages), 2)

    def test_unreachable_or_missing_home_page_is_a_readable_error(self):
        with serve({}) as base:  # everything is 404
            with self.assertRaisesRegex(UpstreamError, "HTTP 404"):
                crawl_site(base + "/")
        with self.assertRaises(UpstreamError):
            crawl_site("http://127.0.0.1:9/")  # nothing listens here


if __name__ == "__main__":
    unittest.main()
