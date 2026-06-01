"""Generated image/screenshot filenames carry a timestamp segment so the same
placeholder produced in different runs (or the same slug across articles) never
collides on disk / CDN — even when file_path + slug + prompt are identical.
"""

import importlib.util
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


def _load():
    p = Path(__file__).resolve().parents[1] / "scripts" / "generate_and_upload_images.py"
    spec = importlib.util.spec_from_file_location("images_ts_test", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["images_ts_test"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load()


def _parse_images(mod, content):
    with TemporaryDirectory() as td:
        path = Path(td) / "article.md"
        path.write_text(content, encoding="utf-8")
        return mod.parse_markdown_images(str(path))


def _parse_screenshots(mod, content):
    with TemporaryDirectory() as td:
        path = Path(td) / "article.md"
        path.write_text(content, encoding="utf-8")
        return mod.parse_markdown_screenshots(str(path))


IMAGE = (
    "# 文章\n\n"
    "<!-- IMAGE: 配图 - 描述 (16:9) -->\n"
    "<!-- PROMPT: a red apple -->\n"
)
SHOT = "# 文章\n\n<!-- SCREENSHOT: https://example.com/p -->\n"


def test_image_filename_contains_timestamp(mod, monkeypatch):
    monkeypatch.setattr(mod, "_image_timestamp", lambda: "20260601-153012")
    matches = _parse_images(mod, IMAGE)
    assert "20260601-153012" in matches[0][0].filename


def test_same_placeholder_distinct_across_runs(mod, monkeypatch):
    monkeypatch.setattr(mod, "_image_timestamp", lambda: "20260601-100000")
    f_run1 = _parse_images(mod, IMAGE)[0][0].filename
    monkeypatch.setattr(mod, "_image_timestamp", lambda: "20260601-110000")
    f_run2 = _parse_images(mod, IMAGE)[0][0].filename
    assert f_run1 != f_run2, "identical placeholder collided across runs"


def test_screenshot_filename_contains_timestamp(mod, monkeypatch):
    monkeypatch.setattr(mod, "_image_timestamp", lambda: "20260601-153012")
    matches = _parse_screenshots(mod, SHOT)
    assert "20260601-153012" in matches[0][0].filename


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
