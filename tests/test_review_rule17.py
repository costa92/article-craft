"""Tests for Rule 17 (Register Naturalness) sub-checks A-D, per tone."""

import sys
from pathlib import Path
from unittest import TestCase, main

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.review_selfcheck import check_rule_17


def _article(body: str, tone: str = "casual", style: str = "B") -> str:
    """Build a minimal article string with frontmatter for testing."""
    fm = f"---\nwriting_style: {style}\ntone: {tone}\n---\n\n# Title\n\n{body}\n"
    return fm


class Rule17SubCheckATests(TestCase):
    def test_passes_when_first_person_density_meets_neutral_threshold(self):
        # neutral threshold = 2 per 800 chars. We give 2 markers in ~400 chars
        # which is 4 per 800w-equivalent — well above.
        body = "我用过 X。" * 20 + "\n\n踩坑实测过。" * 5
        article = _article(body, tone="neutral", style="A")
        result = check_rule_17(article, article.split("\n"))
        sub_a = [v for v in result.violations if "第一人称密度" in v.text]
        self.assertEqual(sub_a, [])

    def test_fails_when_first_person_density_below_casual_threshold(self):
        # casual threshold = 4 per 800w. We give zero personal markers.
        body = "技术内容描述。" * 100  # 600+ chars, no first-person markers
        article = _article(body, tone="casual", style="B")
        result = check_rule_17(article, article.split("\n"))
        sub_a = [v for v in result.violations if "第一人称密度" in v.text]
        self.assertEqual(len(sub_a), 1)
        self.assertEqual(sub_a[0].severity, "warning")

    def test_skipped_when_body_under_200_chinese_chars(self):
        body = "短文。"  # Way under 200 chars.
        article = _article(body, tone="opinionated", style="G")
        result = check_rule_17(article, article.split("\n"))
        self.assertTrue(result.skipped, msg="Should skip Rule 17 on tiny articles")


if __name__ == "__main__":
    main()
