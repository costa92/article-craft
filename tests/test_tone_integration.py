"""Golden integration tests verifying Rule 17 against real fixture articles."""

import sys
from pathlib import Path
from unittest import TestCase, main

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.review_selfcheck import check_rule_17

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "tone"


class GoldenToneTests(TestCase):
    def test_neutral_fixture_passes_at_neutral_tone(self):
        article = (FIXTURES / "neutral_uv_intro.md").read_text(encoding="utf-8")
        result = check_rule_17(article, article.split("\n"))
        self.assertTrue(
            result.passed,
            msg=f"neutral fixture should pass at neutral tone but got: {result.violations}",
        )

    def test_casual_fixture_passes_at_casual_tone(self):
        article = (FIXTURES / "casual_kimi_k2_review.md").read_text(encoding="utf-8")
        result = check_rule_17(article, article.split("\n"))
        warning_count = sum(1 for v in result.violations if v.severity == "warning")
        # Casual tier is moderately strict; small body might miss CV threshold.
        # Allow up to 1 warning, but no errors.
        self.assertEqual(
            sum(1 for v in result.violations if v.severity == "error"),
            0,
            msg=f"casual fixture should not produce errors: {result.violations}",
        )
        self.assertLessEqual(warning_count, 1)

    def test_opinionated_fixture_passes_at_opinionated_tone(self):
        article = (FIXTURES / "opinionated_pip_should_die.md").read_text(encoding="utf-8")
        result = check_rule_17(article, article.split("\n"))
        # Opinionated tier requires strong opinion + density. Fixture has both.
        self.assertEqual(
            sum(1 for v in result.violations if v.severity == "error"),
            0,
            msg=f"opinionated fixture should pass: {result.violations}",
        )

    def test_neutral_fixture_warns_under_opinionated_tone(self):
        # Cross-tier check: neutral text under opinionated tone should
        # at minimum miss the strong-opinion-required check (error level).
        article_text = (FIXTURES / "neutral_uv_intro.md").read_text(encoding="utf-8")
        # Patch frontmatter to claim opinionated tone
        article_text = article_text.replace("tone: neutral", "tone: opinionated")
        result = check_rule_17(article_text, article_text.split("\n"))
        self.assertFalse(result.passed, "neutral text should fail opinionated bar")
        self.assertTrue(
            any(v.severity == "error" for v in result.violations),
            msg="opinionated tone should error on missing strong opinion",
        )


if __name__ == "__main__":
    main()
