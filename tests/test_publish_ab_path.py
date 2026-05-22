"""Tests for v1.7.5 — publish step 3.5 A/B 路径 (原创 vs 创作来源-AI 生成).

Background: developing v1.7.4 dogfood article surfaced a real-world conflict:
the original v1.7.x checklist told authors to *always* tick both
- 「点亮原创」 (≥300 字 门槛 — 推荐池命中)
- 「创作来源 → 内容由 AI 生成」 (GB 45438-2025 合规)

But user community on developers.weixin.qq.com hits this as a contradiction:
"未经原创著作人独家授权的再创作内容不能声明原创" — so AI-generated content
*实际上* cannot claim original. Official 运营专员 declines to give a clear
ruling — this is a gray zone.

v1.7.5 splits the checklist into two explicit paths (A: AI 辅助, B: AI 生成)
so authors can make an informed choice instead of facing a hidden conflict.

This test verifies the publish SKILL.md captures both paths with the
necessary distinctions.
"""

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLISH_SKILL = REPO_ROOT / "skills" / "publish" / "SKILL.md"


class ABPathStructureTests(unittest.TestCase):
    def setUp(self):
        self.content = PUBLISH_SKILL.read_text(encoding="utf-8")

    def test_path_a_section_exists(self):
        """Path A (AI 辅助 / claim original) must be documented."""
        self.assertIn("路径 A", self.content)
        self.assertIn("AI 辅助路径", self.content)

    def test_path_b_section_exists(self):
        """Path B (AI 生成 / don't claim original) must be documented."""
        self.assertIn("路径 B", self.content)
        self.assertIn("AI 完全生成路径", self.content)

    def test_path_a_says_dont_tick_ai_creation_source(self):
        """Path A must explicitly say "creation source 不勾 AI 生成"."""
        # Find Path A region (between "路径 A" and "路径 B")
        start = self.content.find("路径 A —")
        end = self.content.find("路径 B —")
        self.assertGreater(end, start, "Path A/B section structure incorrect")
        path_a = self.content[start:end]
        # Must say 不勾 or 不要勾 for 创作来源
        self.assertRegex(path_a, r"不勾.*创作来源|创作来源.*不勾",
            "Path A must say 'don't tick 创作来源 - AI'")

    def test_path_a_says_claim_original(self):
        """Path A must tell author to claim 原创."""
        start = self.content.find("路径 A —")
        end = self.content.find("路径 B —")
        path_a = self.content[start:end]
        self.assertIn("点亮「原创」声明", path_a)

    def test_path_b_says_dont_claim_original(self):
        """Path B must tell author NOT to claim 原创."""
        start = self.content.find("路径 B —")
        end = self.content.find("路径 A vs B")
        if end == -1:
            end = self.content.find("【合规项-通用】")
        self.assertGreater(end, start)
        path_b = self.content[start:end]
        self.assertIn("不点", path_b)
        self.assertIn("「原创」", path_b)

    def test_path_b_says_tick_ai_creation_source(self):
        """Path B must tick 「创作来源 - 内容由 AI 生成」."""
        start = self.content.find("路径 B —")
        end = self.content.find("路径 A vs B")
        if end == -1:
            end = self.content.find("【合规项-通用】")
        path_b = self.content[start:end]
        self.assertIn("内容由 AI 生成", path_b)


class GrayZoneDocumentationTests(unittest.TestCase):
    """The checklist must explicitly document this is a gray zone, not a hard rule."""

    def setUp(self):
        self.content = PUBLISH_SKILL.read_text(encoding="utf-8")

    def test_acknowledges_gray_zone(self):
        """Must say 'gray zone' or '官方未明确' to set expectations."""
        # 任一关键词命中即可 (gray zone / 官方未明确 / 灰色)
        gray_zone_signals = ["gray zone", "官方未明确", "灰色", "无官方"]
        hit = any(s in self.content for s in gray_zone_signals)
        self.assertTrue(hit,
            "Must explicitly acknowledge this is a gray zone, not a hard rule")

    def test_decision_belongs_to_author(self):
        """Must say the A/B choice belongs to the author, not the tool."""
        self.assertRegex(self.content,
            r"决策权.*作者|作者.*决策|article-craft 不替",
            "Must clarify article-craft doesn't decide A/B for the author")

    def test_path_a_has_self_check_questions(self):
        """Path A must include self-check questions to help author confirm fit."""
        start = self.content.find("路径 A —")
        end = self.content.find("路径 B —")
        path_a = self.content[start:end]
        # 自检 3 问 should exist
        self.assertIn("自检", path_a)
        # At least one question mark indicating a question is present
        self.assertRegex(path_a, r"[?？]",
            "Path A should have self-check questions to help author decide")


class CommonComplianceStillEnforcedTests(unittest.TestCase):
    """Both paths must enforce: no reverse declarations, AIGC label present."""

    def setUp(self):
        self.content = PUBLISH_SKILL.read_text(encoding="utf-8")

    def test_no_reverse_declarations_for_both_paths(self):
        """Rule 23 check applies regardless of A/B."""
        # 合规项-通用 section after both paths
        self.assertIn("合规项-通用", self.content)
        # Must reference Rule 23 reverse declaration check
        self.assertRegex(self.content, r"Rule 23|反向声明|非 AI 生成")

    def test_recommendation_pool_rules_still_enforced(self):
        """Path B (no 原创) must still pass other recommendation-pool rules."""
        self.assertIn("允许平台推荐", self.content)
        self.assertIn("单发未分组", self.content)


if __name__ == "__main__":
    unittest.main()
