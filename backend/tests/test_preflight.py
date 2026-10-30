import unittest
from unittest import mock

import httpx

from app import preflight
from app.preflight import LinkError, check_facebook, check_website
from tests.helpers import serve

PUBLIC = "93.184.216.34"
HOSTS = {"brand.com": PUBLIC, "www.brand.com": PUBLIC, "evil.com": PUBLIC, "intranet.corp": "10.0.0.7", "meta.corp": "169.254.169.254"}


def client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def html(status=200, headers=None):
    return lambda request: httpx.Response(status, headers={"content-type": "text/html", **(headers or {})}, text="<html></html>")


class CheckWebsiteTest(unittest.TestCase):
    def setUp(self):
        def resolve(host):
            if host not in HOSTS:
                raise LinkError(f"We couldn't find a website at {host}. Check the spelling of the address.")
            return [HOSTS[host]]
        patcher = mock.patch.object(preflight, "_resolve", side_effect=resolve)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_reachable_site_passes(self):
        result = check_website("https://brand.com/", client(html()))
        self.assertEqual((result.url, result.warning), ("https://brand.com/", None))

    def test_follows_redirects_and_returns_the_final_address(self):
        def handler(request):
            if request.url.host == "brand.com":
                return httpx.Response(301, headers={"location": "https://www.brand.com/th/"})
            return html()(request)
        self.assertEqual(check_website("http://brand.com", client(handler)).url, "https://www.brand.com/th/")

    def test_missing_page_server_error_and_non_html_are_rejected(self):
        for status, expected in ((404, "doesn't exist"), (410, "doesn't exist"), (500, "server error"), (502, "server error")):
            with self.assertRaisesRegex(LinkError, expected):
                check_website("https://brand.com", client(html(status)))
        pdf = lambda request: httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF")
        with self.assertRaisesRegex(LinkError, "isn't a web page"):
            check_website("https://brand.com/brochure.pdf", client(pdf))

    def test_bot_blocking_sites_are_allowed_with_a_warning(self):
        for status in (401, 403, 429, 503):
            result = check_website("https://brand.com", client(html(status)))
            self.assertIn("restricts automated visitors", result.warning)

    def test_unknown_domain_is_explained(self):
        with self.assertRaisesRegex(LinkError, "couldn't find a website at nope.example"):
            check_website("https://nope.example", client(html()))

    def test_private_and_metadata_addresses_are_blocked(self):
        for url in ("https://intranet.corp", "https://meta.corp/latest"):
            with self.assertRaisesRegex(LinkError, "private network"):
                check_website(url, client(html()))

    def test_redirect_into_a_private_network_is_blocked(self):
        redirect = lambda request: httpx.Response(302, headers={"location": "https://intranet.corp/admin"})
        with self.assertRaisesRegex(LinkError, "private network"):
            check_website("https://evil.com", client(redirect))

    def test_redirect_loop_and_network_failures(self):
        loop = lambda request: httpx.Response(302, headers={"location": "https://brand.com/again"})
        with self.assertRaisesRegex(LinkError, "too many times"):
            check_website("https://brand.com", client(loop))

        def timeout(request):
            raise httpx.ReadTimeout("slow")
        with self.assertRaisesRegex(LinkError, "took too long"):
            check_website("https://brand.com", client(timeout))

        def refused(request):
            raise httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED]")
        with self.assertRaisesRegex(LinkError, "secure connection"):
            check_website("https://brand.com", client(refused))


class CheckFacebookTest(unittest.TestCase):
    """Real Chromium against a local stand-in: a real page has og:title, a missing one only titles itself 'Facebook'."""

    ROUTES = {
        "/real": '<html><head><title>After You | Bangkok | Facebook</title><meta property="og:title" content="After You | Bangkok"></head><body>x</body></html>',
        "/missing": "<html><head><title>Facebook</title></head><body>This content isn't available</body></html>",
        "/wall": (302, {"Location": "/login/?next=x"}, ""),
        "/login/": "<html><head><title>Log in to Facebook</title></head><body>login</body></html>",
    }

    def test_real_page_passes(self):
        with serve(self.ROUTES) as base:
            self.assertEqual(check_facebook(base + "/real").warning, None)

    def test_missing_page_is_rejected(self):
        with serve(self.ROUTES) as base:
            with self.assertRaisesRegex(LinkError, "couldn't find a public Facebook page"):
                check_facebook(base + "/missing")

    def test_login_wall_is_inconclusive_so_it_warns_instead_of_blocking(self):
        with serve(self.ROUTES) as base:
            self.assertIn("login", check_facebook(base + "/wall").warning)

    def test_unreachable_facebook_warns_instead_of_blocking(self):
        self.assertIn("Couldn't reach Facebook", check_facebook("http://127.0.0.1:9/page").warning)


if __name__ == "__main__":
    unittest.main()
