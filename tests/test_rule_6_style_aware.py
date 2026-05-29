"""Tests for B14 — check_rule_6 reads writing_style and applies a per-style
threshold to "code blocks per section".

Style table (skills/write/SKILL.md "风格特定的章节结构"):
    A 教程 → 3 code blocks/section
    B 分享 → 1
    C 深度 → 5
    D 评测 → 2
    E 资讯 → 1
    F 复盘 → 2
    G 观点 → 1
    H 爆料 → defaults to 2

Missing / unknown style → default 2 (the legacy hardcoded threshold).
"""

import importlib.util
import unittest
from pathlib import Path


def load_review_selfcheck_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "review_selfcheck.py"
    spec = importlib.util.spec_from_file_location("review_selfcheck", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


review_selfcheck = load_review_selfcheck_module()


def _make_section(heading: str, n_code_blocks: int) -> str:
    """Build a section that exceeds 200 chars and has exactly N code blocks."""
    filler = "这是一段说明文字，用来把章节填到 200 字以上以触发 Rule 6 的判定逻辑。" * 6
    blocks = ""
    for i in range(n_code_blocks):
        blocks += f"\n\n```bash\necho hello-{i}\n```\n"
    return f"## {heading}\n\n{filler}\n{blocks}\n"


def _article(style_token: str, sections: list[tuple[str, int]], body_form: str = "") -> str:
    """Assemble a fake article: frontmatter (with writing_style) + sections."""
    fm_line = f"writing_style: {style_token}\n" if style_token else ""
    bf_line = f"body_form: {body_form}\n" if body_form else ""
    fm = "---\n" + "title: demo\ndescription: \"demo\"\n" + fm_line + bf_line + "---\n\n# 标题\n\n"
    body = "\n".join(_make_section(h, n) for h, n in sections)
    return fm + body


class Rule6StyleAwareTests(unittest.TestCase):
    def test_style_e_passes_with_one_code_block_per_section(self):
        """Style E (资讯) → threshold 1, so 1 block per section is enough."""
        article = _article("E 资讯快报", [("更新概览", 1), ("升级步骤", 1)])
        result = review_selfcheck.check_rule_6(article, article.splitlines())
        self.assertTrue(
            result.passed,
            f"Style E with 1 code block per section should pass; got: {result.details} "
            f"violations={[v.text for v in result.violations]}",
        )

    def test_style_b_passes_with_one_code_block_per_section(self):
        """Style B (分享) → threshold 1."""
        article = _article("B", [("第一段经验", 1), ("第二段经验", 1)])
        result = review_selfcheck.check_rule_6(article, article.splitlines())
        self.assertTrue(result.passed, result.details)

    def test_style_g_passes_with_one_code_block_per_section(self):
        """Style G (观点) → threshold 1."""
        article = _article("G", [("观点一", 1), ("观点二", 1)])
        result = review_selfcheck.check_rule_6(article, article.splitlines())
        self.assertTrue(result.passed, result.details)

    def test_style_a_fails_with_one_code_block_per_section(self):
        """Style A (教程) → threshold 3, so 1 block per section should FAIL."""
        article = _article("A", [("步骤一", 1), ("步骤二", 1)], body_form="long-form")
        result = review_selfcheck.check_rule_6(article, article.splitlines())
        self.assertFalse(
            result.passed,
            f"Style A with 1 code block per section should fail; got: {result.details}",
        )
        # Both sections (non-intro keywords) flagged
        self.assertGreaterEqual(len(result.violations), 2)
        # Suggestion text should mention threshold 3
        joined = " ".join(v.suggestion for v in result.violations)
        self.assertIn("3", joined)

    def test_style_a_passes_with_three_code_blocks_per_section(self):
        # long-form pins the full Style-A threshold (3); 3 blocks/section passes.
        article = _article("A", [("步骤一", 3), ("步骤二", 3)], body_form="long-form")
        result = review_selfcheck.check_rule_6(article, article.splitlines())
        self.assertTrue(result.passed, result.details)

    def test_style_c_requires_five_code_blocks(self):
        """Style C (深度) → threshold 5, so 2 blocks should fail."""
        article = _article("C", [("深度一", 2)], body_form="long-form")
        result = review_selfcheck.check_rule_6(article, article.splitlines())
        self.assertFalse(result.passed, result.details)
        joined = " ".join(v.suggestion for v in result.violations)
        self.assertIn("5", joined)

    def test_no_writing_style_defaults_to_two(self):
        """Missing writing_style + long-form → falls back to threshold 2."""
        article = _article("", [("章节一", 1)], body_form="long-form")
        result = review_selfcheck.check_rule_6(article, article.splitlines())
        self.assertFalse(
            result.passed,
            f"No writing_style + 1 code block should fail (default threshold 2); got: {result.details}",
        )
        # Two blocks → pass under default
        article_ok = _article("", [("章节一", 2)], body_form="long-form")
        result_ok = review_selfcheck.check_rule_6(article_ok, article_ok.splitlines())
        self.assertTrue(result_ok.passed, result_ok.details)

    def test_unknown_writing_style_defaults_to_two(self):
        """Unknown style letter (Z) + long-form → falls back to threshold 2."""
        article = _article("Z 未知", [("章节一", 1)], body_form="long-form")
        result = review_selfcheck.check_rule_6(article, article.splitlines())
        self.assertFalse(result.passed, result.details)

    def test_lowercase_style_token_is_normalized(self):
        """`writing_style: a 教程` should be treated as Style A (threshold 3)."""
        article = _article("a 教程", [("步骤一", 1)])
        result = review_selfcheck.check_rule_6(article, article.splitlines())
        self.assertFalse(result.passed, result.details)

    def test_intro_chapter_gets_one_less_than_base_threshold(self):
        """Intro/motivation chapter keywords (`为什么` / `背景` / `挑战`)
        allow N-1 (min 1) code blocks even at higher base thresholds.
        Style A base = 3 → intro chapter threshold = 2.
        """
        article = _article("A", [("为什么需要 Foo", 2)])
        result = review_selfcheck.check_rule_6(article, article.splitlines())
        self.assertTrue(
            result.passed,
            f"Intro chapter under Style A should pass with 2 code blocks; got: {result.details}",
        )

    def test_summary_sections_still_skipped(self):
        """## 写在最后 / ## 总结 / ## 结语 are still skipped regardless of style."""
        article = _article("A", [("写在最后", 0)])
        # The function expects exact prefix match — ensure heading is normalized.
        # Replace the section heading manually so it starts with '## 写在最后':
        article_fix = article.replace("## 写在最后", "## 写在最后")
        result = review_selfcheck.check_rule_6(article_fix, article_fix.splitlines())
        # No violations from the summary chapter
        self.assertTrue(result.passed, result.details)


if __name__ == "__main__":
    unittest.main()
