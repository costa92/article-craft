"""Tests for tone-aware lint behavior: severity filtering, inline disable, max-pass."""

import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.lint_article import auto_fix


def _temp_article(body: str, frontmatter: str = "writing_style: A") -> Path:
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    )
    f.write(f"---\n{frontmatter}\n---\n\n# Title\n\n{body}\n")
    f.close()
    return Path(f.name)


class SeverityFilteringTests(TestCase):
    def test_default_min_severity_is_warning_skips_info_fixes(self):
        # 链路 is severity=info — should NOT be replaced at default min-severity.
        article = _temp_article("链路清晰。")
        auto_fix(article)
        self.assertIn("链路", article.read_text(encoding="utf-8"))

    def test_apply_info_replaces_info_severity(self):
        article = _temp_article("链路清晰。")
        auto_fix(article, apply_info=True)
        self.assertNotIn("链路", article.read_text(encoding="utf-8"))

    def test_error_severity_always_applied(self):
        # 综上所述 is error severity at opinionated tier.
        article = _temp_article(
            "综上所述。",
            frontmatter="writing_style: G\ntone: opinionated",
        )
        auto_fix(article)
        self.assertNotIn("综上所述", article.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
