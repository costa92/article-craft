"""Regression tests: variable-length code fences (```` vs ```) and ~~~ fences.

Bug: Rule 13 / Rule 14 / ascii_gate tracked fences with a naive
`line.startswith('```')` toggle that ignored fence length. An article that
*documents* a Markdown code block — wrapping a bare ``` inside a 4-backtick
```` fence — desynced the toggle: the inner ``` was read as a "close", the
real ```` close as a new "open" with no language, and Rule 13 (a write-gate
rule) falsely BLOCKED save.

CommonMark: a fence opened by N backticks is closed only by a line of >= N
backticks of the same char with no info string. The inner ``` is content.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import review_selfcheck as r  # noqa: E402
import ascii_gate  # noqa: E402


# An article that teaches Markdown fence syntax: outer 4-backtick fence wraps a
# bare 3-backtick block as documentation content.
NESTED_FENCE_ARTICLE = (
    "---\ntitle: demo\n---\n\n"
    "## 如何写代码块\n\n"
    "用四个反引号包住三个反引号即可展示：\n\n"
    "````markdown\n"
    "```\n"
    "some code here\n"
    "```\n"
    "````\n\n"
    "正文继续。\n"
)


class Rule13NestedFenceTests(unittest.TestCase):
    def test_rule_13_passes_on_documented_fence(self):
        lines = NESTED_FENCE_ARTICLE.split("\n")
        res = r.check_rule_13(NESTED_FENCE_ARTICLE, lines)
        self.assertTrue(
            res.passed,
            f"Rule 13 should not flag the inner bare ``` as missing a language; "
            f"violations={res.violations}",
        )

    def test_rule_13_still_flags_real_missing_language(self):
        article = (
            "---\ntitle: demo\n---\n\n"
            "## 章节\n\n"
            "```\n"
            "echo hi\n"
            "```\n"
        )
        lines = article.split("\n")
        res = r.check_rule_13(article, lines)
        self.assertFalse(res.passed)
        self.assertEqual(res.violations[0].line, 7)


class Rule14NestedFenceTests(unittest.TestCase):
    def test_rule_14_treats_nested_block_as_one_block(self):
        # The documented inner block is plain content of a markdown-tagged outer
        # block; markdown is in _EXECUTABLE_LANGS so no ASCII-diagram violation.
        lines = NESTED_FENCE_ARTICLE.split("\n")
        res = r.check_rule_14(NESTED_FENCE_ARTICLE, lines)
        self.assertTrue(res.passed, f"violations={res.violations}")


class AsciiGateNestedFenceTests(unittest.TestCase):
    def test_ascii_gate_does_not_desync_on_nested_fence(self):
        violations = ascii_gate.find_violations(NESTED_FENCE_ARTICLE)
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
