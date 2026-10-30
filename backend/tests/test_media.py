import os
import tempfile
import unittest
from unittest import mock

from app import logos, media

PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 50
VIDEO = {"url": "https://fb.com/reel/1/", "text": "new  menu\n here", "media": [{"__typename": "Video", "thumbnail": "https://cdn.fb/v.jpg", "url": "https://fb.com/reel/1/"}]}
PHOTO = {"url": "https://fb.com/p/2", "text": "cake", "media": [{"__typename": "Photo", "image": {"uri": "https://cdn.fb/p.jpg"}}]}
TEXT_ONLY = {"url": "https://fb.com/p/3", "text": "no picture", "media": [{"url": "https://fb.com/p/3"}]}
PAGES = [{"url": "https://brand.com/", "title": "Home", "og_image": "/share.jpg"}, {"url": "https://brand.com/menu", "title": "Menu", "og_image": "https://cdn.brand.com/menu.jpg"},
         {"url": "https://brand.com/about", "title": "About", "og_image": "/share.jpg"}, {"url": "https://brand.com/x", "title": "X", "og_image": None}]


class PlanTest(unittest.TestCase):
    def test_posts_give_one_picture_each_and_flag_videos(self):
        got = media.from_posts([VIDEO, TEXT_ONLY, PHOTO])
        self.assertEqual([(g["url"], g["video"], g["link"]) for g in got], [("https://cdn.fb/v.jpg", True, "https://fb.com/reel/1/"), ("https://cdn.fb/p.jpg", False, "https://fb.com/p/2")])
        self.assertEqual(got[0]["caption"], "new menu here")

    def test_posts_are_capped(self):
        self.assertEqual(len(media.from_posts([PHOTO] * 20)), media.MAX_POST_IMAGES)

    def test_site_images_are_absolute_and_not_repeated(self):
        self.assertEqual([s["url"] for s in media.from_site(PAGES)], ["https://brand.com/share.jpg", "https://cdn.brand.com/menu.jpg"])

    def test_facebook_cover_is_the_banner_and_everything_else_is_a_sample(self):
        specs = media.plan("https://cdn.fb/cover.jpg", PAGES, [VIDEO])
        self.assertEqual([(s["role"], s["source"]) for s in specs], [("banner", "facebook"), ("sample", "facebook"), ("sample", "website"), ("sample", "website")])

    def test_without_a_cover_the_home_pages_share_image_becomes_the_banner(self):
        specs = media.plan(None, PAGES, [PHOTO])
        self.assertEqual((specs[0]["role"], specs[0]["url"]), ("banner", "https://brand.com/share.jpg"))
        self.assertEqual(sum(s["role"] == "banner" for s in specs), 1)

    def test_nothing_to_show_is_an_empty_plan(self):
        self.assertEqual(media.plan(None, [], []), [])

    def test_the_same_picture_is_not_downloaded_twice(self):
        self.assertEqual(len(media.plan("https://cdn.fb/p.jpg", [], [PHOTO])), 1)


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        env = mock.patch.dict(os.environ, {"SMARTKOL_DATA_DIR": self.tmp.name})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_pictures_that_cannot_be_fetched_are_left_out_and_the_rest_are_saved_under_stable_keys(self):
        specs = media.plan("https://cdn.fb/cover.jpg", [], [PHOTO, VIDEO])
        with mock.patch.object(logos, "fetch", side_effect=lambda http, url, **kw: None if "v.jpg" in url else ("image/png", PNG)):
            described = media.save_all("a1", media.download(None, specs))
        self.assertEqual([d["key"] for d in described], ["banner", "s0"])
        self.assertEqual(media.load("a1", "banner"), ("image/png", PNG))
        self.assertIsNone(media.load("a1", "s1"))
        self.assertNotIn("url", described[0])  # the expiring original address is never exposed

    def test_saving_again_replaces_the_old_set_and_delete_removes_it(self):
        spec = {"role": "banner", "source": "facebook", "url": "u", "link": None, "caption": "", "video": False}
        media.save_all("a1", [(spec, "image/png", PNG), ({**spec, "role": "sample"}, "image/png", PNG)])
        media.save_all("a1", [(spec, "image/png", PNG)])
        self.assertIsNone(media.load("a1", "s0"))
        media.delete("a1")
        self.assertIsNone(media.load("a1", "banner"))

    def test_only_banner_and_sample_keys_are_valid(self):
        self.assertTrue(all(media.KEY.match(k) for k in ("banner", "s0", "s12")))
        self.assertFalse(any(media.KEY.match(k) for k in ("../x", "s", "s123", "banner2", "")))


if __name__ == "__main__":
    unittest.main()
