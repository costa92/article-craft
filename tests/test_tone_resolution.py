"""Tests for tone resolution: levels enum, style defaults, resolve_tone() precedence."""

import sys
from pathlib import Path
from unittest import TestCase, main

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import config


class ToneLevelsTests(TestCase):
    def test_levels_enum_is_three_strings_in_order(self):
        self.assertEqual(
            config.TONE_REGISTER_LEVELS,
            ("neutral", "casual", "opinionated"),
        )

    def test_style_to_tone_default_covers_all_eight_styles(self):
        for style in "ABCDEFGH":
            self.assertIn(style, config.STYLE_TO_TONE_DEFAULT)
            self.assertIn(
                config.STYLE_TO_TONE_DEFAULT[style],
                config.TONE_REGISTER_LEVELS,
            )

    def test_style_default_mapping_matches_spec(self):
        expected = {
            "A": "neutral",       # 技术教程
            "B": "casual",        # 经验分享 / 口语化
            "C": "neutral",       # 深度长文
            "D": "casual",        # 评测对比
            "E": "neutral",       # 资讯快报
            "F": "casual",        # 项目复盘 / Case Study
            "G": "opinionated",   # 观点输出 / 思考
            "H": "opinionated",   # AI 资讯爆料 / 自媒体爆款
        }
        self.assertEqual(config.STYLE_TO_TONE_DEFAULT, expected)


class ResolveToneTests(TestCase):
    def test_cli_wins_over_frontmatter_and_style(self):
        result = config.resolve_tone(
            cli_tone="opinionated",
            frontmatter_tone="neutral",
            writing_style="A",
        )
        self.assertEqual(result, "opinionated")

    def test_frontmatter_wins_over_style_default(self):
        result = config.resolve_tone(
            cli_tone=None,
            frontmatter_tone="casual",
            writing_style="A",  # default would be neutral
        )
        self.assertEqual(result, "casual")

    def test_style_default_when_cli_and_frontmatter_missing(self):
        result = config.resolve_tone(
            cli_tone=None,
            frontmatter_tone=None,
            writing_style="H",
        )
        self.assertEqual(result, "opinionated")

    def test_unknown_style_falls_back_to_neutral(self):
        result = config.resolve_tone(
            cli_tone=None,
            frontmatter_tone=None,
            writing_style="Z",  # not in mapping
        )
        self.assertEqual(result, "neutral")

    def test_invalid_frontmatter_value_falls_back_to_style_default(self):
        # frontmatter author manually typed something invalid; we degrade silently
        # (warning is logged elsewhere; resolver only returns valid values)
        result = config.resolve_tone(
            cli_tone=None,
            frontmatter_tone="aggressive",  # invalid
            writing_style="B",
        )
        self.assertEqual(result, "casual")


class ToneThresholdsTests(TestCase):
    def test_thresholds_dict_has_all_three_tones(self):
        for tone in config.TONE_REGISTER_LEVELS:
            self.assertIn(tone, config.TONE_THRESHOLDS)

    def test_each_tone_has_four_metrics(self):
        expected_keys = {
            "first_person_per_800w",
            "strong_opinion_min",
            "max_summary_phrases",
            "sentence_len_variance_min",
        }
        for tone, metrics in config.TONE_THRESHOLDS.items():
            self.assertEqual(set(metrics.keys()), expected_keys, f"tone={tone}")

    def test_first_person_density_increases_with_tone_severity(self):
        # neutral 2 < casual 4 < opinionated 6
        self.assertLess(
            config.TONE_THRESHOLDS["neutral"]["first_person_per_800w"],
            config.TONE_THRESHOLDS["casual"]["first_person_per_800w"],
        )
        self.assertLess(
            config.TONE_THRESHOLDS["casual"]["first_person_per_800w"],
            config.TONE_THRESHOLDS["opinionated"]["first_person_per_800w"],
        )

    def test_strong_opinion_patterns_is_non_empty_list_of_compiled_regex(self):
        import re
        self.assertGreater(len(config.STRONG_OPINION_PATTERNS), 5)
        for p in config.STRONG_OPINION_PATTERNS:
            self.assertIsInstance(p, re.Pattern)


if __name__ == "__main__":
    main()
