import unittest

from app.crawler import pick_links
from app.social import extract_socials, normalize_facebook, validate_public_url


class NormalizeFacebookTest(unittest.TestCase):
    def test_reduces_urls_to_the_page_root(self):
        for raw in (
            "https://www.facebook.com/afteryoucafe/",
            "http://m.facebook.com/afteryoucafe/posts/123?ref=x",
            "https://web.facebook.com/afteryoucafe/about",
        ):
            self.assertEqual(normalize_facebook(raw), "https://www.facebook.com/afteryoucafe")

    def test_numeric_profile_and_legacy_pages(self):
        self.assertEqual(normalize_facebook("https://facebook.com/profile.php?id=100066416713262&sk=about"),
                         "https://www.facebook.com/profile.php?id=100066416713262")
        self.assertEqual(normalize_facebook("https://www.facebook.com/pages/Cafe-Name/12345/"),
                         "https://www.facebook.com/pages/Cafe-Name/12345")

    def test_rejects_share_links_and_non_facebook(self):
        for raw in (
            "https://www.facebook.com/sharer/sharer.php?u=https://x.com",
            "https://www.facebook.com/plugins/like.php",
            "https://www.facebook.com/",
            "https://www.facebook.com/profile.php?id=abc",
            "https://example.com/afteryoucafe",
            "not a url",
        ):
            self.assertIsNone(normalize_facebook(raw), raw)

    def test_thai_page_name_survives(self):
        self.assertEqual(normalize_facebook("https://www.facebook.com/ร้านขนม"), "https://www.facebook.com/%E0%B8%A3%E0%B9%89%E0%B8%B2%E0%B8%99%E0%B8%82%E0%B8%99%E0%B8%A1")


class ExtractSocialsTest(unittest.TestCase):
    HTML = """
      <a href="https://www.facebook.com/afteryoucafe?ref=nav">fb</a>
      <a href="https://www.facebook.com/afteryoucafe/">fb again</a>
      <a href="https://www.facebook.com/sharer/sharer.php?u=x&amp;t=y">share</a>
      <a href="https://www.facebook.com/afteryoudessertcafe">other</a>
      <a href="https://www.tiktok.com/@afteryou_th/video/7000">tt</a>
      <a href="https://vt.tiktok.com/ZSJjkakdG/">short</a>
      <a href="https://www.instagram.com/afteryoudessertcafe/">ig</a>
      <a href="https://www.instagram.com/p/AbC123/">post</a>
      <a href="https://line.me/R/ti/p/%40nlr9729q">line</a>
      <a href="https://www.youtube.com/@AfterYou">yt</a>
      <a href="https://www.youtube.com/watch?v=abc">video</a>
    """

    def test_finds_deduplicated_profiles_in_order(self):
        s = extract_socials([self.HTML, "https://www.facebook.com/afteryoucafe"])
        self.assertEqual(s["facebook"], ["https://www.facebook.com/afteryoucafe", "https://www.facebook.com/afteryoudessertcafe"])
        self.assertEqual(s["tiktok"], ["https://www.tiktok.com/@afteryou_th", "https://vt.tiktok.com/ZSJjkakdG"])
        self.assertEqual(s["instagram"], ["https://www.instagram.com/afteryoudessertcafe"])
        self.assertEqual(s["line"], ["https://line.me/R/ti/p/%40nlr9729q"])
        self.assertEqual(s["youtube"], ["https://www.youtube.com/@AfterYou"])

    def test_no_links_gives_empty_lists(self):
        self.assertEqual(extract_socials(["<p>hello</p>"]), {k: [] for k in ("facebook", "tiktok", "instagram", "youtube", "line")})


class ValidatePublicUrlTest(unittest.TestCase):
    def test_accepts_and_normalises(self):
        self.assertEqual(validate_public_url("  example.com/menu "), "https://example.com/menu")
        self.assertEqual(validate_public_url("http://shop.example.co.th"), "http://shop.example.co.th")

    def test_rejects_unsafe_or_invalid(self):
        for raw in ("", "ftp://example.com", "localhost", "http://127.0.0.1:8000", "http://192.168.1.10",
                    "http://10.0.0.5/admin", "http://printer.local", "intranet", "http://169.254.169.254/latest"):
            with self.assertRaises(ValueError, msg=raw):
                validate_public_url(raw)


class PickLinksTest(unittest.TestCase):
    def test_prefers_product_pages_and_drops_noise(self):
        hrefs = ["/privacy-policy", "/menu", "/about/board-of-directors", "/about", "/blog/post-1", "/careers",
                 "https://other.com/menu", "/logo.png", "/", "#top", "/products/cake"]
        picked = pick_links("https://brand.com/", hrefs, 4)
        self.assertEqual(picked[:3], ["https://brand.com/menu", "https://brand.com/about", "https://brand.com/products/cake"])
        self.assertNotIn("https://brand.com/privacy-policy", picked)
        self.assertNotIn("https://brand.com/about/board-of-directors", picked)
        self.assertTrue(all(u.startswith("https://brand.com/") for u in picked))

    def test_respects_limit(self):
        self.assertEqual(len(pick_links("https://b.com", [f"/page{i}" for i in range(20)], 3)), 3)


if __name__ == "__main__":
    unittest.main()
