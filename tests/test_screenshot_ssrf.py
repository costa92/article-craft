"""SSRF guard for the screenshot/verify/harvest fetch surface.

Policy (per maintainer decision): HARD-BLOCK non-http(s) schemes (file://, data:,
gopher:, …) and link-local / cloud-metadata addresses (169.254.0.0/16 incl.
169.254.169.254, fe80::/10). ALLOW-but-WARN loopback / private (localhost, 127/8,
::1, RFC1918) so local dev-server screenshots keep working.
"""

import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


def load_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "screenshot_tool.py"
    spec = importlib.util.spec_from_file_location("screenshot_tool", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


st = load_module()


class HardBlockTests(unittest.TestCase):
    def test_file_scheme_blocked(self):
        allowed, msg = st._is_fetchable_url("file:///etc/passwd")
        self.assertFalse(allowed)
        self.assertTrue(msg)

    def test_data_scheme_blocked(self):
        allowed, _ = st._is_fetchable_url("data:text/html,<h1>x</h1>")
        self.assertFalse(allowed)

    def test_cloud_metadata_ip_blocked(self):
        allowed, msg = st._is_fetchable_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(allowed)
        self.assertIn("169.254.169.254", msg)

    def test_no_host_blocked(self):
        allowed, _ = st._is_fetchable_url("http://")
        self.assertFalse(allowed)

    def test_ipv4_mapped_metadata_blocked(self):
        # ::ffff:169.254.169.254 is the IPv4-mapped IPv6 spelling of the cloud
        # metadata address. It must be hard-blocked, not allowed-with-warning —
        # on a dual-stack host this is a real reach to the metadata endpoint.
        allowed, msg = st._is_fetchable_url(
            "http://[::ffff:169.254.169.254]/latest/meta-data/"
        )
        self.assertFalse(allowed)
        self.assertIn("169.254.169.254", msg)


class AllowWithWarnTests(unittest.TestCase):
    def test_loopback_allowed_with_warning(self):
        allowed, msg = st._is_fetchable_url("http://127.0.0.1:3000/")
        self.assertTrue(allowed, "loopback dev-server screenshots must stay allowed")
        self.assertTrue(msg, "loopback should still warn")

    def test_rfc1918_allowed_with_warning(self):
        allowed, msg = st._is_fetchable_url("http://192.168.1.10:8080/")
        self.assertTrue(allowed)
        self.assertTrue(msg)


class AllowCleanTests(unittest.TestCase):
    def test_public_https_allowed_no_warning(self):
        # IP literal that is public — avoids real DNS in the test.
        allowed, msg = st._is_fetchable_url("https://1.1.1.1/")
        self.assertTrue(allowed)
        self.assertIsNone(msg)


class WiringTests(unittest.TestCase):
    def test_check_url_status_blocks_file_scheme_without_network(self):
        # Blocked URLs return an invalid status with no status_code and never
        # touch the network (no requests.head call to mock — it returns first).
        status = st.check_url_status("file:///etc/passwd", _from_cache=False)
        self.assertFalse(status["is_valid"])
        self.assertIsNone(status["status_code"])
        self.assertIn("SSRF", status["reason"])

    def test_rehost_image_blocks_metadata_ip(self):
        out = st.rehost_image("http://169.254.169.254/latest/meta-data/", mode="always")
        self.assertFalse(out["ok"])
        self.assertIn("SSRF", out["reason"])

    def test_harvest_images_blocks_file_scheme(self):
        out = st.harvest_images("file:///etc/hosts")
        self.assertIn("SSRF", out["error"])


class RedirectChainTests(unittest.TestCase):
    """初始 URL 干净但 30x 跳转把请求引向 metadata/内网时，必须二次拦截。

    `_is_fetchable_url` 只校验初始 URL；攻击者控制的页面可以用一个公网域名
    301 到 169.254.169.254。fetch 之后必须复检最终落点（及整条 history）。
    """

    _META = "http://169.254.169.254/latest/meta-data/"

    def test_check_url_status_blocks_redirect_to_metadata(self):
        fake_resp = SimpleNamespace(
            status_code=200,
            url=self._META,
            history=[SimpleNamespace(url=self._META)],
        )
        with mock.patch.object(st.requests, "head", return_value=fake_resp):
            status = st.check_url_status("http://evil.example/redir", _from_cache=False)
        self.assertFalse(status["is_valid"])
        self.assertIn("SSRF", status["reason"])

    def test_rehost_image_blocks_redirect_to_metadata(self):
        fake_resp = SimpleNamespace(
            status_code=200,
            url=self._META,
            history=[SimpleNamespace(url=self._META)],
            content=b"x" * 5000,
            headers={"content-type": "image/png"},
        )
        with mock.patch.object(st.requests, "get", return_value=fake_resp):
            out = st.rehost_image("http://evil.example/img.png", mode="always")
        self.assertFalse(out["ok"])
        self.assertIn("SSRF", out["reason"])

    def test_harvest_images_blocks_playwright_redirect_to_metadata(self):
        fake_page = mock.MagicMock()
        fake_page.url = self._META
        fake_page.goto.return_value = SimpleNamespace(status=200)
        fake_p = mock.MagicMock()
        fake_p.chromium.launch.return_value.new_context.return_value.new_page.return_value = fake_page
        cm = mock.MagicMock()
        cm.__enter__.return_value = fake_p
        cm.__exit__.return_value = False
        with mock.patch.object(st, "sync_playwright", return_value=cm):
            out = st.harvest_images("http://evil.example/article", use_fallback=False)
        self.assertIn("SSRF", out["error"])


if __name__ == "__main__":
    unittest.main()
