"""Tests for screenshot host matching — host keys must match by domain
boundary, not bare substring.

Bug: HOST_MAIN_SELECTORS / suggest_selector matched the key "x.com" with a
bare substring test (`"x.com" in host` / `"x.com" in url_lower`), so hosts
ending in x.com — vox.com, netflix.com, max.com, xbox.com — were treated as
Twitter/X and got the tweet CSS selector, producing a wrong/empty screenshot
region. The substring form was only ever safe for longer keys like
weibo.com → m.weibo.com (a real subdomain).

Fix: match on host suffix boundary — host == key OR host endswith "." + key.
"""

import importlib.util
import unittest
from pathlib import Path


def load_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "screenshot_tool.py"
    spec = importlib.util.spec_from_file_location("screenshot_tool", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


st = load_module()


class HostOvermatchTests(unittest.TestCase):
    def test_vox_com_not_treated_as_twitter(self):
        self.assertEqual(st.main_content_selectors_for_host("https://www.vox.com/article"), [])

    def test_max_com_not_treated_as_twitter(self):
        self.assertEqual(st.main_content_selectors_for_host("https://www.max.com/movies"), [])

    def test_netflix_com_not_treated_as_twitter(self):
        self.assertEqual(st.main_content_selectors_for_host("https://www.netflix.com/title/123"), [])

    def test_suggest_selector_vox_status_path_not_tweet(self):
        # "status" appears in the path but the host is vox.com, not x.com.
        self.assertEqual(st.suggest_selector("https://www.vox.com/2024/status-update"), "")


class HostMatchStillWorksTests(unittest.TestCase):
    def test_x_com_status_still_gets_tweet_selector(self):
        self.assertEqual(
            st.suggest_selector("https://x.com/user/status/123"), '[data-testid="tweet"]'
        )

    def test_x_com_host_selectors(self):
        sels = st.main_content_selectors_for_host("https://x.com/user/status/123")
        self.assertIn("[data-testid='tweet']", sels)

    def test_weibo_subdomain_still_matches(self):
        # The substring form existed to let m.weibo.com match weibo.com — the
        # suffix form must preserve that.
        sels = st.main_content_selectors_for_host("https://m.weibo.com/detail/456")
        self.assertIn(".WB_feed_detail", sels)


class Is404HostParityTests(unittest.TestCase):
    def test_vox_not_matched_by_twitter_404_patterns(self):
        # vox.com must not be host-matched as x.com for 404 detection.
        page = "This account doesn't exist anymore"
        self.assertFalse(st.is_404_content(page, "https://www.vox.com/some-article"))

    def test_x_com_still_matched_for_404(self):
        page = "This account doesn't exist anymore"
        self.assertTrue(st.is_404_content(page, "https://x.com/u/status/1"))


if __name__ == "__main__":
    unittest.main()
