"""Tests for the canonical PicGo output parser (B2).

The parser used to live duplicated in screenshot_tool.upload_to_cdn and
generate_and_upload_images.upload_to_picgo. v1.5.2 fixed one half (the
multi-line [PicGo INFO] log case that silently broke screenshot
uploads); v1.6.8 unifies both call sites onto scripts/uploaders.py.

These tests pin the parser behavior so future changes can't regress
either historical bug.
"""

import importlib.util
import sys
from pathlib import Path


def _load():
    p = Path(__file__).resolve().parents[1] / "scripts" / "uploaders.py"
    if str(p.parent) not in sys.path:
        sys.path.insert(0, str(p.parent))
    spec = importlib.util.spec_from_file_location("uploaders_test_mod", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["uploaders_test_mod"] = mod
    spec.loader.exec_module(mod)
    return mod


mod = _load()


# --- the historical bug case: multi-line log + final URL ---


def test_picgo_real_world_multiline_log():
    """The exact shape that broke screenshot upload in v1.5.2."""
    stdout = (
        "[PicGo INFO]: Before transform\n"
        "[PicGo INFO]: Transforming... Current transformer is [path]\n"
        "[PicGo INFO]: Before upload\n"
        "[PicGo INFO]: Uploading to GitHub\n"
        "[PicGo SUCCESS]:\n"
        "https://cdn.jsdelivr.net/gh/foo/bar/img.png\n"
    )
    assert mod.parse_picgo_output(stdout) == "https://cdn.jsdelivr.net/gh/foo/bar/img.png"


def test_picgo_url_anywhere_in_lines():
    """URL doesn't have to be the last line — first match wins."""
    stdout = (
        "https://cdn.example.com/first.png\n"
        "[PicGo INFO]: trailing log\n"
    )
    assert mod.parse_picgo_output(stdout) == "https://cdn.example.com/first.png"


def test_picgo_bare_url_single_line():
    """Minimal happy path — just a URL."""
    assert mod.parse_picgo_output("https://example.com/img.png") == \
        "https://example.com/img.png"


def test_picgo_http_url_accepted():
    """http:// (not just https://) is also recognized."""
    assert mod.parse_picgo_output("http://example.com/img.png") == \
        "http://example.com/img.png"


# --- JSON fallback strategies ---


def test_picgo_json_dict_format():
    assert mod.parse_picgo_output('{"url": "https://cdn.example.com/x.png"}') == \
        "https://cdn.example.com/x.png"


def test_picgo_json_list_format():
    assert mod.parse_picgo_output('[{"url": "https://cdn.example.com/y.png"}]') == \
        "https://cdn.example.com/y.png"


def test_picgo_line_url_beats_json_when_both_present():
    stdout = (
        "[PicGo INFO]: log\n"
        "https://cdn.example.com/line.png\n"
        '{"url": "https://cdn.example.com/json.png"}\n'
    )
    # Line scan finds http first → JSON never parsed
    assert mod.parse_picgo_output(stdout) == "https://cdn.example.com/line.png"


# --- failure modes (return None) ---


def test_picgo_empty_string_returns_none():
    assert mod.parse_picgo_output("") is None


def test_picgo_no_url_no_json_returns_none():
    assert mod.parse_picgo_output("[PicGo ERROR]: upload failed\n") is None


def test_picgo_invalid_json_returns_none():
    """Looks JSON-ish but doesn't parse → None, not crash."""
    assert mod.parse_picgo_output("{not valid json,}") is None


def test_picgo_json_dict_without_url_key_returns_none():
    assert mod.parse_picgo_output('{"status": "ok"}') is None


def test_picgo_json_empty_list_returns_none():
    assert mod.parse_picgo_output('[]') is None


def test_picgo_json_list_first_element_not_dict_returns_none():
    assert mod.parse_picgo_output('["just a string"]') is None


def test_picgo_json_with_non_string_url_returns_none():
    """Defensive: URL must actually be a string."""
    assert mod.parse_picgo_output('{"url": 12345}') is None


# --- Uploader protocol exists for future backends ---


def test_uploader_protocol_is_runtime_checkable():
    """The Uploader protocol can be used with isinstance() — required
    for the future factory pattern to dispatch on configured backend."""
    class FakeUploader:
        def upload(self, local_path: str) -> str:
            return "https://x.com/" + local_path
    assert isinstance(FakeUploader(), mod.Uploader)


def test_uploader_protocol_rejects_wrong_shape():
    class NotAnUploader:
        def something_else(self):
            pass
    assert not isinstance(NotAnUploader(), mod.Uploader)
