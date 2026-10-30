import unittest
from unittest import mock

import httpx

from app import logos
from app.preflight import LinkError

SITE = "https://brand.com/th/"
FB = "https://scontent.fbcdn.net/profile.jpg"
PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 100


class CandidatesTest(unittest.TestCase):
    def test_orders_crisp_icons_then_facebook_then_small_icons_then_share_image_then_favicon(self):
        icons = [
            {"href": "/favicon-32.png", "rel": "icon", "sizes": "32x32"},
            {"href": "/apple.png", "rel": "apple-touch-icon", "sizes": ""},  # no sizes: touch icons are ~180
            {"href": "https://cdn.brand.com/logo.svg", "rel": "icon", "sizes": "any"},
            {"href": "/icon-192.png", "rel": "icon", "sizes": "192x192"},
        ]
        self.assertEqual(logos.candidates(icons, "/share.jpg", FB, SITE), [
            "https://cdn.brand.com/logo.svg",        # scalable, crispest
            "https://brand.com/icon-192.png",
            "https://brand.com/apple.png",
            FB,
            "https://brand.com/favicon-32.png",
            "https://brand.com/share.jpg",
            "https://brand.com/favicon.ico",
        ])

    def test_facebook_picture_only_when_there_is_no_website(self):
        self.assertEqual(logos.candidates([], None, FB, None), [FB])
        self.assertEqual(logos.candidates([], None, None, None), [])

    def test_drops_non_http_and_duplicates(self):
        icons = [{"href": "data:image/png;base64,AAAA", "rel": "icon", "sizes": "180x180"},
                 {"href": "/a.png", "rel": "icon", "sizes": "180x180"}, {"href": "/a.png", "rel": "icon", "sizes": "180x180"}]
        self.assertEqual(logos.candidates(icons, None, None, SITE)[0], "https://brand.com/a.png")
        self.assertEqual(logos.candidates(icons, None, None, SITE).count("https://brand.com/a.png"), 1)


def client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def image(status=200, ctype="image/png", body=PNG, headers=None):
    return lambda request: httpx.Response(status, headers={"content-type": ctype, **(headers or {})}, content=body)


class FetchTest(unittest.TestCase):
    def setUp(self):
        guard = mock.patch.object(logos, "assert_public_host")
        self.guard = guard.start()
        self.addCleanup(guard.stop)

    def test_facebook_serves_profile_pictures_as_avif(self):
        self.assertEqual(logos.fetch(client(image(ctype="image/avif", body=b"avif-bytes")), "https://scontent.fbcdn.net/p.jpg"), ("image/avif", b"avif-bytes"))

    def test_returns_a_small_image(self):
        self.assertEqual(logos.fetch(client(image()), "https://brand.com/a.png"), ("image/png", PNG))
        self.assertEqual(logos.fetch(client(image(ctype="image/svg+xml; charset=utf-8", body=b"<svg/>")), "https://x.com/l.svg"), ("image/svg+xml", b"<svg/>"))

    def test_rejects_wrong_type_missing_empty_and_oversized_files(self):
        for handler in (image(ctype="text/html", body=b"<html>"), image(status=404), image(body=b""),
                        image(body=b"x" * (logos.MAX_BYTES + 1))):
            self.assertIsNone(logos.fetch(client(handler), "https://brand.com/a.png"))

    def test_follows_a_redirect_to_the_image(self):
        def handler(request):
            if request.url.path == "/old.png":
                return httpx.Response(301, headers={"location": "https://cdn.brand.com/new.png"})
            return image()(request)
        self.assertEqual(logos.fetch(client(handler), "https://brand.com/old.png")[0], "image/png")

    def test_never_follows_a_redirect_into_a_private_network(self):
        self.guard.side_effect = lambda host: (_ for _ in ()).throw(LinkError("private")) if host == "intranet.corp" else None
        redirect = lambda request: httpx.Response(302, headers={"location": "http://intranet.corp/secret.png"})
        self.assertIsNone(logos.fetch(client(redirect), "https://brand.com/a.png"))

    def test_network_errors_are_a_miss_not_a_crash(self):
        def boom(request):
            raise httpx.ConnectError("down")
        self.assertIsNone(logos.fetch(client(boom), "https://brand.com/a.png"))

    def test_find_uses_the_first_url_that_works(self):
        def handler(request):
            return image()(request) if request.url.path == "/good.png" else httpx.Response(404)
        found = logos.find(client(handler), ["https://a.com/bad.png", "https://a.com/good.png", "https://a.com/other.png"])
        self.assertEqual(found, ("image/png", PNG))
        self.assertIsNone(logos.find(client(handler), ["https://a.com/bad.png"]))


if __name__ == "__main__":
    unittest.main()
