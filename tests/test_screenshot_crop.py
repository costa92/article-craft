"""Regression tests for screenshot height defaults + crop behavior.

Background: in v1.5.2 and earlier, capture_screenshot's --max-height
defaulted to 0 (no cropping), so element screenshots returned the full
height of the matched element. In practice that meant 1400px+ for
GitHub READMEs / docs sites — too tall for typical viewport reading.
v1.5.3 changed the default to 900 and moved crop application from
batch_capture's outer loop into capture_screenshot itself, so all
callers (CLI direct, batch, programmatic) benefit.
"""

import importlib.util
import inspect
import sys
import tempfile
from pathlib import Path

import pytest
from PIL import Image


def _load_module():
    p = Path(__file__).resolve().parents[1] / "scripts" / "screenshot_tool.py"
    spec = importlib.util.spec_from_file_location("screenshot_tool_crop_test", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["screenshot_tool_crop_test"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


def test_capture_screenshot_default_max_height_is_900(mod):
    """The default must be 900 (≈ one viewport), not 0 or some legacy value.

    If someone changes this without thinking, screenshots will silently
    grow back to 1400px+ and the original bug returns.
    """
    sig = inspect.signature(mod.capture_screenshot)
    assert sig.parameters["max_height"].default == 900


def test_crop_to_max_height_skips_when_image_already_short(mod, tmp_path):
    """No-op when the image is already shorter than max_height."""
    p = tmp_path / "short.png"
    Image.new("RGB", (800, 500), "white").save(p)
    cropped = mod.crop_to_max_height(str(p), 900)
    assert cropped is False
    assert Image.open(p).size == (800, 500)


def test_crop_to_max_height_crops_to_top_when_too_tall(mod, tmp_path):
    """Tall image gets cropped from the top down to max_height pixels."""
    p = tmp_path / "tall.png"
    Image.new("RGB", (800, 1500), "white").save(p)
    cropped = mod.crop_to_max_height(str(p), 900)
    assert cropped is True
    assert Image.open(p).size == (800, 900)


def test_crop_to_max_height_handles_exact_match(mod, tmp_path):
    """Image at exactly max_height is not cropped."""
    p = tmp_path / "exact.png"
    Image.new("RGB", (800, 900), "white").save(p)
    cropped = mod.crop_to_max_height(str(p), 900)
    assert cropped is False
    assert Image.open(p).size == (800, 900)


def test_screenshot_subcommand_max_height_default_in_argparse(mod):
    """The argparse default for the screenshot subcommand must also be 900.

    The signature default + the CLI default need to agree, otherwise
    using --max-height from CLI vs calling capture_screenshot() directly
    behaves inconsistently.
    """
    # We can't easily introspect argparse's defaults without invoking
    # main(), so probe by importing argparse and parsing a minimal
    # fake set of args. Instead, scan the source for the argparse
    # default to fail loud if someone changes it without thinking.
    src = (Path(__file__).resolve().parents[1] / "scripts" / "screenshot_tool.py").read_text()
    # Both `sc` and `ba` subparsers should declare default=900 for --max-height.
    occurrences = src.count('"--max-height", type=int, default=900')
    assert occurrences == 2, (
        f"Expected 2 argparse occurrences of --max-height default=900 "
        f"(screenshot + batch subcommands), found {occurrences}. "
        "Did you change one but forget the other?"
    )


# ─── Per-host main-content selector tests ──────────────────────────────────
# These guard the v1.5.5 multi-platform expansion. Anchor scope and
# suggest_selector both consume HOST_MAIN_SELECTORS via
# main_content_selectors_for_host(); regressions show up here as a
# "selector list shrunk for host X" diff, which is what we want.


@pytest.mark.parametrize("url, must_contain", [
    # X / Twitter — tweet container
    ("https://x.com/user/status/123",          "[data-testid='tweet']"),
    ("https://twitter.com/user/status/456",    "[data-testid='tweet']"),
    # Reddit — modern + legacy
    ("https://www.reddit.com/r/python/comments/xyz/foo/", "shreddit-post"),
    # HN — fatitem
    ("https://news.ycombinator.com/item?id=1234567",      ".fatitem"),
    # Stack Overflow — question container
    ("https://stackoverflow.com/questions/123/foo",       "#question"),
    # Chinese platforms
    ("https://m.weibo.cn/status/1234567890",              ".WB_feed_detail"),
    ("https://weibo.com/u/123",                           ".WB_feed_detail"),
    ("https://www.xiaohongshu.com/explore/abc123",        "#noteContainer"),
    ("https://xhslink.com/abc",                           "#noteContainer"),
    ("https://www.zhihu.com/question/123/answer/456",     ".RichContent-inner"),
    ("https://mp.weixin.qq.com/s/abc123",                 "#js_content"),
    # Video
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ",       "#description-inline-expander"),
    ("https://www.bilibili.com/video/BV1xx411c7XW",       "#viewbox_report"),
    # Long-form
    ("https://medium.com/@author/post-title",             "article"),
    ("https://arxiv.org/abs/2512.12818",                  "#abs"),
])
def test_host_main_selectors_recognize_platform(mod, url, must_contain):
    """Each known host returns a non-empty selector list including the
    canonical content container."""
    sels = mod.main_content_selectors_for_host(url)
    assert sels, f"No selectors returned for {url}"
    assert must_contain in sels, (
        f"Expected '{must_contain}' in selectors for {url}, got {sels}"
    )


def test_host_main_selectors_unknown_host(mod):
    """Unknown hosts return an empty list — caller falls back to GENERIC."""
    assert mod.main_content_selectors_for_host("https://random-blog.example.com/post") == []


def test_host_main_selectors_strips_www(mod):
    """www. prefix doesn't break host matching."""
    sels_www = mod.main_content_selectors_for_host("https://www.x.com/u/status/1")
    sels_bare = mod.main_content_selectors_for_host("https://x.com/u/status/1")
    assert sels_www == sels_bare
    assert sels_www, "www.x.com should match the x.com entry"


def test_user_overrides_win_over_builtin(mod, monkeypatch, tmp_path):
    """env.json `screenshot_main_content_selectors` overrides the built-in
    HOST_MAIN_SELECTORS for matching hosts."""
    # Patch the override-resolver to return a custom dict.
    monkeypatch.setattr(
        mod, "_user_main_content_overrides",
        lambda: {"x.com": [".my-custom-tweet"]},
    )
    sels = mod.main_content_selectors_for_host("https://x.com/u/status/1")
    assert sels == [".my-custom-tweet"], (
        "User override should win over built-in HOST_MAIN_SELECTORS"
    )


def test_user_overrides_for_new_host(mod, monkeypatch):
    """Users can register hosts that aren't in HOST_MAIN_SELECTORS."""
    monkeypatch.setattr(
        mod, "_user_main_content_overrides",
        lambda: {"my-blog.example.com": [".post-body"]},
    )
    sels = mod.main_content_selectors_for_host("https://my-blog.example.com/2026/post")
    assert sels == [".post-body"]


def test_suggest_selector_uses_host_map_for_video(mod):
    """Refactor sanity: suggest_selector() should now produce a non-empty
    selector for YouTube even though there's no path-sensitive special-case
    for it. The host map is the single source of truth."""
    out = mod.suggest_selector("https://www.youtube.com/watch?v=foo")
    assert "#description-inline-expander" in out


def test_suggest_selector_zhihu_answer(mod):
    """Same idea for zhihu — host map drives behavior."""
    out = mod.suggest_selector("https://www.zhihu.com/question/123/answer/456")
    assert ".RichContent-inner" in out


def test_generic_content_selectors_excludes_bare_main_and_article(mod):
    """v1.5.4 lesson: bare `main` and bare `article` are layout containers
    on GitHub etc. — they must not be in GENERIC_CONTENT_SELECTORS or
    anchor will scroll to file trees again."""
    assert "main" not in mod.GENERIC_CONTENT_SELECTORS
    assert "article" not in mod.GENERIC_CONTENT_SELECTORS
