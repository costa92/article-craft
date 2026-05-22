"""Tests for v1.7.3 Style G + opinionated 加强模板 (P1 修复).

Verifies that:
1. style-guide.md contains the "Style G + opinionated 加强模板" section.
2. The section contains the 4 句式表 (个人经历 / 主观判断 / 强观点 / 具体锚点).
3. The 4 句式表 reference patterns that match scripts/config.py STRONG_OPINION_PATTERNS
   and scripts/review_selfcheck.py PERSONAL_ANCHOR_REGEX (no drift).
4. write/SKILL.md Step 3a.5 references the new section.

Motivation: 4 篇实测发现 Style G + opinionated 文章 100% 失败 Rule 17/22.
Root cause: tone-aware prompt augmentation 太抽象, LLM 写到结尾退化成中立
技术教程. v1.7.3 加针对性填空式模板.
"""

import importlib.util
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
STYLE_GUIDE = REPO_ROOT / "skills" / "write" / "style-guide.md"
WRITE_SKILL = REPO_ROOT / "skills" / "write" / "SKILL.md"
CONFIG_PY = REPO_ROOT / "scripts" / "config.py"


def load_config_module():
    spec = importlib.util.spec_from_file_location("config", CONFIG_PY)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class StyleGuideStructureTests(unittest.TestCase):
    def setUp(self):
        self.content = STYLE_GUIDE.read_text(encoding="utf-8")

    def test_has_p1_enhanced_section(self):
        """Style G + opinionated 加强模板 section must exist."""
        self.assertIn("### Style G + opinionated 加强模板", self.content)

    def test_p1_section_follows_tone_opinionated(self):
        """加强模板 should come AFTER ## Tone: opinionated (it depends on it)."""
        tone_pos = self.content.find("## Tone: opinionated")
        p1_pos = self.content.find("### Style G + opinionated 加强模板")
        self.assertGreater(tone_pos, 0)
        self.assertGreater(p1_pos, tone_pos,
            "Style G 加强模板 must appear after Tone: opinionated section")

    def test_four_句式表_present(self):
        """4 句式表 (个人经历 / 主观判断 / 强观点 / 具体锚点) must be present."""
        for table in [
            "个人经历句式表",
            "主观判断句式表",
            "强观点句式表",
            "具体锚点句式",
        ]:
            self.assertIn(table, self.content,
                f"P1 section missing required 句式表: {table}")

    def test_4_articles_dogfood_table_present(self):
        """The dogfood table comparing 4 articles must remind authors of the
        failure pattern."""
        # 4 articles' rule status table — anchors authors to concrete reality
        self.assertIn("4 篇实测对照表", self.content)
        # the 100% fail story
        self.assertIn("100% 失败", self.content)


class StrongOpinionPatternsNoDriftTests(unittest.TestCase):
    """Make sure 强观点句式表 stays in sync with STRONG_OPINION_PATTERNS in config.py."""

    def setUp(self):
        self.content = STYLE_GUIDE.read_text(encoding="utf-8")
        self.config = load_config_module()

    def test_table_mentions_strong_opinion_patterns_constant(self):
        """Doc must point readers at the canonical pattern source — avoids drift."""
        self.assertIn("STRONG_OPINION_PATTERNS", self.content)

    def test_at_least_3_concrete_examples_match_actual_patterns(self):
        """The doc's example sentences should actually match the regex patterns.
        Otherwise the 'check this table' instruction becomes a lie."""
        # Extract sentences from the 强观点 section (between heading and next subheading)
        # Don't use --- as boundary (collides with table separator lines)
        m = re.search(
            r"#### 强观点句式表.*?(?=\n####|\n## |\Z)",
            self.content,
            re.DOTALL,
        )
        self.assertIsNotNone(m, "强观点句式表 section structure changed unexpectedly")
        section = m.group(0)

        # Extract example sentences (inside straight or Chinese quotes)
        examples = re.findall(r'["「]([^"」]+)["」]', section)
        self.assertGreater(len(examples), 3, "需要 ≥3 个例子")

        # At least 3 must match a STRONG_OPINION_PATTERN
        match_count = 0
        for example in examples:
            for pat in self.config.STRONG_OPINION_PATTERNS:
                if pat.search(example):
                    match_count += 1
                    break

        self.assertGreaterEqual(
            match_count, 3,
            f"At least 3 examples must match STRONG_OPINION_PATTERNS, got {match_count}/{len(examples)} matches",
        )


class WriteSkillReferencesP1Tests(unittest.TestCase):
    def setUp(self):
        self.write_content = WRITE_SKILL.read_text(encoding="utf-8")

    def test_write_skill_references_enhanced_template(self):
        """write SKILL.md Step 3a.5 must point to the new section."""
        # both the term and the version marker should appear
        self.assertIn("Style G + opinionated 加强模板", self.write_content)
        self.assertIn("v1.7.3", self.write_content)

    def test_write_skill_says_opinionated_loads_extra(self):
        """Doc must say opinionated tone loads the extra section."""
        # Find the Step 3a.5 region and check it mentions the conditional load
        m = re.search(
            r"3a\.5.*?(?=#### 3b\b)",
            self.write_content,
            re.DOTALL,
        )
        self.assertIsNotNone(m, "Step 3a.5 structure changed")
        section = m.group(0)
        # Must indicate opinionated tone triggers the extra load
        self.assertRegex(section, r"opinionated.*加强模板|加强模板.*opinionated")


if __name__ == "__main__":
    unittest.main()
