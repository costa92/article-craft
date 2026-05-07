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


if __name__ == "__main__":
    main()
