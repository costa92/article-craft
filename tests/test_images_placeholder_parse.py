"""Regression tests for parse_markdown_images in generate_and_upload_images.py.

Two bugs:
  A) Filename hash = md5(file_path + slug) only. Two IMAGE placeholders that
     resolve to the same slug (trivial: any pure-CJK name strips to "_") get an
     identical filename — the second generation overwrites the first on disk and
     filename_to_url (keyed by filename) maps both placeholders to one URL, so a
     distinct image is silently lost.
  B) The placeholder regex runs over raw file content with no code-fence
     exclusion, so an IMAGE/PROMPT pair shown as a documentation *example* inside
     a fenced code block is treated as a real placeholder — an image is generated
     and the example is rewritten, corrupting the doc.
"""

import importlib.util
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


def _load():
    p = Path(__file__).resolve().parents[1] / "scripts" / "generate_and_upload_images.py"
    spec = importlib.util.spec_from_file_location("images_parse_test", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["images_parse_test"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load()


def _parse(mod, content):
    with TemporaryDirectory() as td:
        path = Path(td) / "article.md"
        path.write_text(content, encoding="utf-8")
        return mod.parse_markdown_images(str(path))


def test_same_slug_placeholders_get_distinct_filenames(mod):
    content = (
        "# 文章\n\n"
        "<!-- IMAGE: 配图 - 第一张描述 (16:9) -->\n"
        "<!-- PROMPT: a red apple -->\n\n"
        "中间正文。\n\n"
        "<!-- IMAGE: 配图 - 第二张描述 (16:9) -->\n"
        "<!-- PROMPT: a blue ocean -->\n"
    )
    matches = _parse(mod, content)
    assert len(matches) == 2
    f1, f2 = matches[0][0].filename, matches[1][0].filename
    assert f1 != f2, f"two distinct placeholders collided to one filename: {f1}"


def test_placeholder_inside_code_block_is_ignored(mod):
    content = (
        "# 教程：如何写图片占位符\n\n"
        "在正文里这样写：\n\n"
        "```markdown\n"
        "<!-- IMAGE: 示例 - 演示 (16:9) -->\n"
        "<!-- PROMPT: this is only documentation -->\n"
        "```\n\n"
        "下面是一个真实占位符：\n\n"
        "<!-- IMAGE: 真图 - 真实配图 (16:9) -->\n"
        "<!-- PROMPT: a real image -->\n"
    )
    matches = _parse(mod, content)
    prompts = [c.prompt for c, _ in matches]
    assert "this is only documentation" not in prompts, (
        f"a documented placeholder inside a code block was parsed as real: {prompts}"
    )
    assert len(matches) == 1
    assert matches[0][0].prompt == "a real image"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
