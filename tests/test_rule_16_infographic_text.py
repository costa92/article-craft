"""Tests for Rule 16 — S2 手绘信息图海报 English-label exemption.

Rule 16 hard-fails on CJK characters in any `<!-- PROMPT: -->` because the
image models can't reliably render Chinese. S2 hand-drawn infographic poster
/ sketchnote / knowledge map is a *labeled* style — text IS the point of an
infographic. Owner decision: S2 prompts may carry SHORT ENGLISH labels, but
CJK is still hard-blocked everywhere (English-only policy — Chinese garbles).

This pins:
  - S2-signature prompts with English labels pass (label warn exempted)
  - S2-signature prompts with CJK still hard-fail (English-only enforced)
  - non-S2 prompts with CJK still hard-fail (exemption is tightly scoped)
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


rs = load_review_selfcheck_module()


def run_rule_16(content: str):
    result = rs.check_rule_16(content, content.split("\n"))
    return result


class Rule16InfographicExemptionTests(unittest.TestCase):
    def test_s2_signature_prompt_with_english_labels_passes(self):
        content = (
            "<!-- IMAGE: flow - workflow framework (3:2) -->\n"
            "<!-- PROMPT: hand-drawn infographic poster, sketchnote style knowledge map, "
            "warm cream paper background, three panels labeled Input / Parser / Output -->\n"
        )
        result = run_rule_16(content)
        self.assertTrue(result.passed, f"S2 infographic with English labels should pass: {result.details}")

    def test_sketchnote_prompt_with_english_label_instruction_passes(self):
        content = (
            "<!-- PROMPT: whiteboard doodle illustration, sketchnote knowledge map, "
            'panels with label "Parser" and label "Cache" connected by arrows -->\n'
        )
        result = run_rule_16(content)
        self.assertTrue(result.passed, f"sketchnote with English labels should pass: {result.details}")

    def test_s2_signature_prompt_with_cjk_still_fails(self):
        # English-only policy: CJK is blocked even for S2 (Chinese garbles).
        content = (
            "<!-- PROMPT: hand-drawn infographic poster, sketchnote knowledge map, "
            "three panels labeled 输入 / 解析 / 输出 -->\n"
        )
        result = run_rule_16(content)
        self.assertFalse(result.passed, "S2 prompt with CJK must still fail (English-only)")

    def test_non_s2_prompt_with_cjk_still_fails(self):
        content = (
            "<!-- PROMPT: Minimalist flat illustration, top banner with big text "
            '"2026 年报告" -->\n'
        )
        result = run_rule_16(content)
        self.assertFalse(result.passed, "non-S2 prompt with CJK must still hard-fail")

    def test_non_s2_prompt_clean_passes(self):
        content = (
            "<!-- PROMPT: Minimalist flat illustration, soft blue palette. "
            "A laptop with floating containers. No readable text anywhere, no letters -->\n"
        )
        result = run_rule_16(content)
        self.assertTrue(result.passed)


if __name__ == "__main__":
    unittest.main()
