"""Tests for B1 — cookie injection in screenshot_tool.

The three helpers (_resolve_cookies_path, _load_cookies, _apply_cookies)
are pure functions exercised here directly. The end-to-end Playwright
flow itself isn't exercised — `capture_screenshot` launches a real
browser, which is covered separately by the existing screenshot e2e
plumbing.
"""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest


def _load_module():
    repo_root = Path(__file__).resolve().parents[1]
    scripts_dir = repo_root / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    spec = importlib.util.spec_from_file_location(
        "screenshot_tool_cookies_test", scripts_dir / "screenshot_tool.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["screenshot_tool_cookies_test"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


# --- _resolve_cookies_path ------------------------------------------------


def test_resolve_disabled_returns_none(mod, tmp_path):
    """--no-cookies forces None even if explicit path provided."""
    f = tmp_path / "c.json"
    f.write_text("[]")
    assert mod._resolve_cookies_path(str(f), disabled=True) is None


def test_resolve_explicit_path_wins(mod, tmp_path):
    f = tmp_path / "c.json"
    f.write_text("[]")
    with mock.patch.object(mod, "config", create=True) as cfg_mock:
        cfg_mock.browser_cookies_path.return_value = str(tmp_path / "from_env.json")
        result = mod._resolve_cookies_path(str(f), disabled=False)
    assert result == str(f)


def test_resolve_from_config_when_no_explicit(mod, tmp_path, monkeypatch):
    f = tmp_path / "from_env.json"
    f.write_text("[]")
    # Make sure the default fallback file does NOT exist in HOME
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    import config as real_config
    monkeypatch.setattr(real_config, "browser_cookies_path", lambda: str(f))
    assert mod._resolve_cookies_path("", disabled=False) == str(f)


def test_resolve_default_fallback_only_if_file_exists(mod, monkeypatch, tmp_path):
    """When no env.json setting and ~/.cache/article-craft/cookies.json
    does NOT exist, resolver returns None (no spurious "default" path)."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    import config as real_config
    monkeypatch.setattr(real_config, "browser_cookies_path", lambda: "")
    assert mod._resolve_cookies_path("", disabled=False) is None


def test_resolve_default_fallback_when_file_exists(mod, monkeypatch, tmp_path):
    fake_home = tmp_path / "home"
    (fake_home / ".cache" / "article-craft").mkdir(parents=True)
    (fake_home / ".cache" / "article-craft" / "cookies.json").write_text("[]")
    monkeypatch.setenv("HOME", str(fake_home))
    import config as real_config
    monkeypatch.setattr(real_config, "browser_cookies_path", lambda: "")
    resolved = mod._resolve_cookies_path("", disabled=False)
    assert resolved is not None
    assert resolved.endswith("cookies.json")


# --- _load_cookies --------------------------------------------------------


def test_load_cookies_missing_file_returns_error(mod, tmp_path):
    cookies, err = mod._load_cookies(str(tmp_path / "nope.json"))
    assert cookies == []
    assert err is not None
    assert "not found" in err


def test_load_cookies_invalid_json_returns_error_with_position(mod, tmp_path):
    f = tmp_path / "bad.json"
    f.write_text("{not valid,}")
    cookies, err = mod._load_cookies(str(f))
    assert cookies == []
    assert err is not None
    assert "invalid JSON" in err
    # Includes line:col coordinates
    assert ":" in err


def test_load_cookies_top_level_list(mod, tmp_path):
    f = tmp_path / "c.json"
    f.write_text(json.dumps([
        {"name": "session", "value": "abc", "domain": ".example.com", "path": "/"},
    ]))
    cookies, err = mod._load_cookies(str(f))
    assert err is None
    assert len(cookies) == 1
    assert cookies[0]["name"] == "session"


def test_load_cookies_wrapped_dict(mod, tmp_path):
    f = tmp_path / "c.json"
    f.write_text(json.dumps({"cookies": [
        {"name": "session", "value": "abc", "domain": ".example.com"},
    ]}))
    cookies, err = mod._load_cookies(str(f))
    assert err is None
    assert len(cookies) == 1


def test_load_cookies_rejects_non_list_non_dict(mod, tmp_path):
    f = tmp_path / "c.json"
    f.write_text('"just a string"')
    cookies, err = mod._load_cookies(str(f))
    assert cookies == []
    assert err is not None


def test_load_cookies_skips_invalid_entries(mod, tmp_path):
    """A single bad cookie shouldn't drop the rest — defensive parse."""
    f = tmp_path / "c.json"
    f.write_text(json.dumps([
        {"name": "ok", "value": "x", "domain": ".example.com"},
        {"name": "missing_value", "domain": ".example.com"},  # no value → skip
        {"value": "no_name", "domain": ".example.com"},       # no name → skip
        {"name": "no_domain_or_url", "value": "x"},            # neither → skip
        "not a dict",                                          # wrong shape → skip
        {"name": "ok2", "value": "y", "url": "https://x.com/"},  # url variant → keep
    ]))
    cookies, err = mod._load_cookies(str(f))
    assert err is None
    names = [c["name"] for c in cookies]
    assert names == ["ok", "ok2"]


# --- _apply_cookies -------------------------------------------------------


def test_apply_cookies_empty_is_noop(mod):
    ctx = mock.MagicMock()
    n = mod._apply_cookies(ctx, [])
    assert n == 0
    ctx.add_cookies.assert_not_called()


def test_apply_cookies_calls_playwright_and_returns_count(mod):
    ctx = mock.MagicMock()
    cookies = [
        {"name": "a", "value": "1", "domain": ".x.com"},
        {"name": "b", "value": "2", "domain": ".y.com"},
    ]
    n = mod._apply_cookies(ctx, cookies)
    assert n == 2
    ctx.add_cookies.assert_called_once_with(cookies)


def test_apply_cookies_swallows_playwright_error(mod, capsys):
    """If Playwright raises (bad cookie format etc.), we log + return 0,
    not raise — a bad cookie file shouldn't take down the whole screenshot."""
    ctx = mock.MagicMock()
    ctx.add_cookies.side_effect = ValueError("bad cookie format")
    n = mod._apply_cookies(ctx, [{"name": "a", "value": "1", "domain": ".x.com"}])
    assert n == 0
    captured = capsys.readouterr()
    assert "failed to apply cookies" in captured.out
