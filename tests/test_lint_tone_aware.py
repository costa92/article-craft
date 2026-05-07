"""Tests for tone-aware lint behavior: severity filtering, inline disable, max-pass."""

import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import re as _re
import unittest

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


class InlineDisableTests(TestCase):
    def test_disable_block_skips_fixes_inside(self):
        body = (
            "正常: 赋能开发者。\n\n"
            "<!-- lint:disable rule1 -->\n"
            "保留: 原文有赋能 一站式 这两个词。\n"
            "<!-- lint:enable rule1 -->\n\n"
            "正常: 一站式服务。"
        )
        article = _temp_article(body)
        auto_fix(article)
        text = article.read_text(encoding="utf-8")
        # Outside disable: 赋能 / 一站式 replaced
        self.assertNotIn("正常: 赋能", text)
        self.assertNotIn("正常: 一站式", text)
        # Inside disable: preserved
        self.assertIn("保留: 原文有赋能 一站式 这两个词", text)

    def test_disable_all_skips_everything(self):
        body = (
            "<!-- lint:disable all -->\n"
            "赋能 一站式 链路 综上所述。\n"
            "<!-- lint:enable all -->"
        )
        article = _temp_article(body)
        auto_fix(article)
        text = article.read_text(encoding="utf-8")
        self.assertIn("赋能 一站式 链路 综上所述", text)

    def test_unmatched_disable_warns_but_does_not_abort(self):
        # Unmatched <!-- lint:disable --> at end of file
        body = "正常段落。\n<!-- lint:disable rule1 -->\n赋能段落。"
        article = _temp_article(body)
        report = auto_fix(article)
        # No exception; report should reflect the issue
        self.assertTrue(any("unmatched" in str(w).lower() for w in report.warnings))

    def test_disable_specific_rule_does_not_block_other_rules(self):
        body = (
            "<!-- lint:disable rule1 -->\n"
            "赋能 综上所述。\n"
            "<!-- lint:enable rule1 -->"
        )
        article = _temp_article(
            body,
            frontmatter="writing_style: G\ntone: opinionated",
        )
        auto_fix(article)
        text = article.read_text(encoding="utf-8")
        self.assertIn("赋能", text)              # rule1 disabled inside block
        # 综上所述 isn't tagged with rule1 so it should still be replaced


class MaxPassTests(TestCase):
    def test_clean_after_one_pass(self):
        # Plain prose with no violations — should converge immediately.
        article = _temp_article("纯净段落。我用过这个工具。")
        report = auto_fix(article, max_passes=3)
        self.assertEqual(report.status, "clean")
        self.assertLessEqual(report.passes, 1)

    def test_converges_within_max_passes_for_chained_replacements(self):
        # Words that are matched by the rewrite table — all should be replaced
        # within max_passes and the result stabilise to "clean".
        article = _temp_article("赋能 一站式 链路。" * 10)
        report = auto_fix(article, max_passes=3, apply_info=True)
        self.assertEqual(report.status, "clean")
        self.assertLessEqual(report.passes, 3)

    def test_oscillation_detected_when_rewrites_cycle(self):
        # Inject a stateful hook that alternates its rewrite each call:
        # odd calls replace "testword" with "altword", even calls replace
        # "altword" back to "testword".  This causes pass 1: A→B, pass 2:
        # B→A, pass 3: A→B — the (A, B) signature repeats → "oscillating".
        try:
            from scripts.lint_article import _set_test_rewrites_hook
        except ImportError:
            self.skipTest("Test hook not exposed")

        call_count = [0]

        def _alternating_rewrites(tone):
            call_count[0] += 1
            if call_count[0] % 2 == 1:
                # Odd pass: replace "testword" → "altword"
                return [(_re.compile(r"testword"), "altword", "warning", "rule_test")]
            else:
                # Even pass: replace "altword" → "testword"
                return [(_re.compile(r"altword"), "testword", "warning", "rule_test")]

        _set_test_rewrites_hook(_alternating_rewrites)
        try:
            article = _temp_article("testword bar")
            report = auto_fix(article, max_passes=5)
            self.assertEqual(report.status, "oscillating")
        finally:
            _set_test_rewrites_hook(None)


if __name__ == "__main__":
    main()
