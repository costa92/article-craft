"""Regression tests for screenshot placeholder parsing in
generate_and_upload_images.py.

Same defect family as the IMAGE placeholder fix: the SCREENSHOT regexes (v2 and
legacy) ran over raw file content with no code-fence exclusion, so a
<!-- SCREENSHOT: ... --> shown as a documentation example inside a fenced code
block was treated as a real placeholder. The v2 filename hash was also
md5(file_path + url) only, so two shots of the same URL with different options
(selector/width) collided to one filename.
"""

import importlib.util
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


def _load():
    p = Path(__file__).resolve().parents[1] / "scripts" / "generate_and_upload_images.py"
    spec = importlib.util.spec_from_file_location("images_ss_test", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["images_ss_test"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load()


def _parse(mod, content):
    with TemporaryDirectory() as td:
        path = Path(td) / "article.md"
        path.write_text(content, encoding="utf-8")
        return mod.parse_markdown_screenshots(str(path))


def test_screenshot_in_code_block_is_ignored(mod):
    content = (
        "# 教程：截图占位符语法\n\n"
        "在正文这样写：\n\n"
        "```markdown\n"
        "<!-- SCREENSHOT: https://example.com/docs -->\n"
        "```\n\n"
        "下面是真实占位符：\n\n"
        "<!-- SCREENSHOT: https://real.example.com/page -->\n"
    )
    matches = _parse(mod, content)
    urls = [c.url for c, _ in matches]
    assert "https://example.com/docs" not in urls, (
        f"a documented screenshot inside a code block was parsed as real: {urls}"
    )
    assert urls == ["https://real.example.com/page"]


def test_same_url_different_options_get_distinct_filenames(mod):
    content = (
        "# 文章\n\n"
        "<!-- SCREENSHOT: https://example.com/p #header WIDTH:800 -->\n\n"
        "正文。\n\n"
        "<!-- SCREENSHOT: https://example.com/p #footer WIDTH:1200 -->\n"
    )
    matches = _parse(mod, content)
    assert len(matches) == 2
    f1, f2 = matches[0][0].filename, matches[1][0].filename
    assert f1 != f2, f"two distinct screenshots collided to one filename: {f1}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
