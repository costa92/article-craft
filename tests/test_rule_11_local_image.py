"""Regression tests: Rule 11 local-image residue check must be CWD-independent.

Bug: check_rule_11 resolved a referenced local image with os.path.exists(img_path),
which is relative to the *process CWD* (it also computed a dead `article_dir` from
lines[0], the article's first content line, never used). So whether
`![](images/x.jpg)` was flagged depended on where the script was launched from —
random false positives/negatives.

Fix: Rule 11 is the publish-readiness placeholder-residue gate. A relative local
image path (images/... or placeholder-...) is never publishable regardless of
whether the file exists on disk — flag it unconditionally, deterministically.
"""

import os
import sys
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import review_selfcheck as r  # noqa: E402


ARTICLE_WITH_LOCAL_IMG = (
    "---\ntitle: demo\n---\n\n"
    "## 章节\n\n"
    "![配图](images/x.jpg)\n\n"
    "正文。\n"
)


class Rule11LocalImageTests(unittest.TestCase):
    def test_local_image_flagged_even_when_file_exists_in_cwd(self):
        """The old code passed when images/x.jpg existed relative to CWD."""
        lines = ARTICLE_WITH_LOCAL_IMG.split("\n")
        with TemporaryDirectory() as td:
            (Path(td) / "images").mkdir()
            (Path(td) / "images" / "x.jpg").write_bytes(b"\xff\xd8\xff")
            prev = os.getcwd()
            os.chdir(td)
            try:
                res = r.check_rule_11(ARTICLE_WITH_LOCAL_IMG, lines)
            finally:
                os.chdir(prev)
        self.assertFalse(
            res.passed,
            "A relative local image path is not publishable; it must be flagged "
            "regardless of whether the file happens to exist in the CWD.",
        )

    def test_local_image_flagged_when_file_absent(self):
        lines = ARTICLE_WITH_LOCAL_IMG.split("\n")
        res = r.check_rule_11(ARTICLE_WITH_LOCAL_IMG, lines)
        self.assertFalse(res.passed)

    def test_cdn_url_image_passes(self):
        article = (
            "---\ntitle: demo\n---\n\n"
            "## 章节\n\n"
            "![配图](https://cdn.example.com/x.jpg)\n\n"
            "正文。\n"
        )
        lines = article.split("\n")
        res = r.check_rule_11(article, lines)
        self.assertTrue(res.passed, f"violations={res.violations}")


if __name__ == "__main__":
    unittest.main()
