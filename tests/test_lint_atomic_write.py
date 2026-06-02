"""lint_article.auto_fix must write the article atomically and must not
truncate-rewrite a clean article that has nothing to fix.

Bug: the three in-place writers used Path.write_text (truncate-then-write) with
no temp-and-rename and no backup — an ill-timed kill mid-write leaves the
author's article half-written and unrecoverable. And the converged/clean branch
wrote the (unchanged) text back even when no pass mutated anything, exposing a
no-op lint to corruption for zero benefit.
"""

import os
import tempfile
import unittest
from pathlib import Path

from scripts import lint_article
from scripts.lint_article import auto_fix


class LintNoOpWriteTests(unittest.TestCase):
    def _article(self, text: str) -> Path:
        d = tempfile.mkdtemp()
        p = Path(d) / "article.md"
        p.write_text(text, encoding="utf-8")
        return p

    def test_clean_article_is_not_rewritten(self):
        """A clean article (nothing to fix) must not be written at all."""
        p = self._article("---\nwriting_style: A\n---\n\n这是一段干净的正文。\n")
        calls = {"n": 0}
        orig = lint_article._atomic_write

        def spy(path, data):
            calls["n"] += 1
            return orig(path, data)

        lint_article._atomic_write = spy
        try:
            report = auto_fix(p)
        finally:
            lint_article._atomic_write = orig
        self.assertEqual(report.status, "clean")
        self.assertEqual(calls["n"], 0, "clean no-op lint must not rewrite the article")

    def test_fix_writes_atomically_and_leaves_no_temp(self):
        """A real fix is applied and no stray temp files remain in the dir."""
        p = self._article("本产品赋能开发者。\n")
        auto_fix(p)
        result = p.read_text(encoding="utf-8")
        self.assertNotIn("赋能", result)  # fix applied
        leftovers = [f for f in os.listdir(p.parent) if f != "article.md"]
        self.assertEqual(leftovers, [], "atomic write must not leave temp files behind")


if __name__ == "__main__":
    unittest.main()
