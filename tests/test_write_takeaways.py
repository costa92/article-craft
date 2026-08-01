"""Tests for deterministic frontmatter takeaways writing."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


def _load_review_selfcheck():
    root = Path(__file__).resolve().parents[1]
    scripts = root / "scripts"
    sys.path.insert(0, str(scripts))
    sys.path.insert(0, str(root))
    path = scripts / "review_selfcheck.py"
    spec = importlib.util.spec_from_file_location("review_selfcheck_takeaways", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


rs = _load_review_selfcheck()


SAMPLE = """---
title: "测试文章"
date: 2026-08-01
tags:
  - llmfit
  - 本地模型
cover: "https://cdn.example.com/cover.jpg"
---

# 测试文章

开头段落。

## 安装

```bash
llmfit system
```

## 选型

用 recommend。
"""


class WriteTakeawaysTests(unittest.TestCase):
    def test_write_takeaways_preserves_body_and_other_keys(self):
        new, status = rs.write_takeaways(SAMPLE, ["会用 llmfit system", "知道 recommend 默认 JSON"])
        self.assertEqual(status, "written")
        # Body after closing --- must be byte-identical in content
        self.assertIn("# 测试文章", new)
        self.assertIn("## 安装", new)
        self.assertIn("```bash\nllmfit system\n```", new)
        body_old = rs.get_body(SAMPLE)
        body_new = rs.get_body(new)
        self.assertEqual(body_new, body_old)

        fm = rs.parse_frontmatter(new)
        self.assertEqual(fm["title"], "测试文章")
        self.assertEqual(fm["cover"], "https://cdn.example.com/cover.jpg")
        self.assertEqual(fm["tags"], ["llmfit", "本地模型"])
        self.assertEqual(fm["takeaways"], ["会用 llmfit system", "知道 recommend 默认 JSON"])

    def test_write_takeaways_overwrites_idempotent(self):
        once, _ = rs.write_takeaways(SAMPLE, ["A", "B"])
        twice, status = rs.write_takeaways(once, ["A", "B"])
        self.assertEqual(status, "written")
        self.assertEqual(rs.parse_frontmatter(once)["takeaways"], ["A", "B"])
        self.assertEqual(rs.parse_frontmatter(twice)["takeaways"], ["A", "B"])
        thrice, _ = rs.write_takeaways(twice, ["C"])
        self.assertEqual(rs.parse_frontmatter(thrice)["takeaways"], ["C"])

    def test_no_frontmatter(self):
        content = "# just a title\n\nbody\n"
        new, status = rs.write_takeaways(content, ["x"])
        self.assertEqual(status, "no_frontmatter")
        self.assertEqual(new, content)

    def test_parse_error(self):
        bad = "---\n: this: is: [invalid\n---\n\nbody\n"
        new, status = rs.write_takeaways(bad, ["x"])
        self.assertEqual(status, "parse_error")
        self.assertEqual(new, bad)

    def test_write_takeaways_file_atomic(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "article.md"
            path.write_text(SAMPLE, encoding="utf-8")
            result = rs.write_takeaways_file(str(path), ["收获一", "收获二"])
            self.assertEqual(result["status"], "written")
            self.assertTrue(result.get("verified"))
            fm = rs.parse_frontmatter(path.read_text(encoding="utf-8"))
            self.assertEqual(fm["takeaways"], ["收获一", "收获二"])
            # body untouched
            self.assertIn("## 选型", path.read_text(encoding="utf-8"))

    def test_extract_section_headings(self):
        headings = rs.extract_section_headings(SAMPLE)
        self.assertEqual(headings, ["安装", "选型"])

    def test_cli_write_takeaways(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.md"
            path.write_text(SAMPLE, encoding="utf-8")
            with self.assertRaises(SystemExit) as cm:
                rs.main([
                    str(path),
                    "--write-takeaways",
                    json.dumps(["t1", "t2"], ensure_ascii=False),
                ])
            self.assertEqual(cm.exception.code, 0)
            fm = rs.parse_frontmatter(path.read_text(encoding="utf-8"))
            self.assertEqual(fm["takeaways"], ["t1", "t2"])

    def test_cli_extract_headings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.md"
            path.write_text(SAMPLE, encoding="utf-8")
            # capture stdout
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf), self.assertRaises(SystemExit) as cm:
                rs.main([str(path), "--extract-headings"])
            self.assertEqual(cm.exception.code, 0)
            data = json.loads(buf.getvalue())
            self.assertEqual(data, ["安装", "选型"])


if __name__ == "__main__":
    unittest.main()
