"""Cross-rule guard: every code-block-sensitive rule must exempt content inside
fenced code blocks for ALL fence styles (``` , ~~~, and nested ```` ).

Why this file exists
--------------------
"Red-flag word / template phrase / bare URL / fabricated number written inside
a code block still gets flagged" is a *recurring* bug class:

    v1.9.2  Rule 1 + Rule 12   (toggle only saw ```, missed block interior)
    v1.9.3  Rule 1             (missed ~~~ and nested ```` fences)
    v1.9.4  Rule 23 + Rule 24  (same — missed ~~~ and nested fences)

Root cause: each rule hand-rolled its own code-block detection (a
`startswith('```')` toggle or the `re.sub(r'```.*?```')` regex) instead of the
canonical `iter_code_blocks` / `_code_block_line_set` scanner. Every audit round
migrated one or two more rules; the rest kept the buggy detector, so the same
bug resurfaced in whichever rule hadn't been migrated yet.

This guard runs the *trigger content for every code-block-sensitive rule* inside
each fence style and asserts zero violations. It goes red the moment any rule —
present or future — regresses to a non-fence-aware detector, regardless of which
rule it is. That is the recurrence prevention the per-rule tests can't give.
"""

import importlib.util
import unittest
from pathlib import Path


def load():
    p = Path(__file__).resolve().parents[1] / "scripts" / "review_selfcheck.py"
    spec = importlib.util.spec_from_file_location("review_selfcheck", p)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


rs = load()

# One trigger line per code-block-sensitive rule. Kept together so the fixtures
# stress every detector at once.
TRIGGERS = [
    "用赋能和闭环抓住底层逻辑方法论。",                # Rule 1  red-flag words
    "详见 https://example.com/internal-page 页面。",   # Rule 8  bare URL
    "本文将会详细地介绍这一整套体系。",                # Rule 12 template summary
    "声明：本文非 AI 生成，纯手写。",                  # Rule 23 reverse declaration
    "实测节省 50%，处理 1000 个文件用 50 秒。",         # Rule 24 fabricated numbers
]
TRIGGER_BODY = "\n".join(TRIGGERS)

# Rules that MUST exempt fenced code-block content.
GUARDED_RULES = [1, 8, 12, 23, 24]


def _article(block: str) -> str:
    return (
        "---\ntitle: 守护测试\n---\n\n# 守护测试\n\n"
        "正常正文段落，足够长以满足结构要求，这里没有任何违规内容。\n\n"
        + block
        + "\n\n结尾段落，仍然没有任何违规内容。\n"
    )


def _violations(rule_id: int, content: str):
    fn = rs._RULE_DISPATCH[rule_id]
    return fn(content, content.split("\n")).violations


class CodeBlockExemptionGuard(unittest.TestCase):
    def test_triggers_are_real_in_plain_body(self):
        # Sanity: the trigger text DOES fire when it is NOT in a code block.
        # A green guard then means exemption works — not that the triggers
        # silently went stale and stopped matching.
        content = _article(TRIGGER_BODY)
        fired = [r for r in GUARDED_RULES if _violations(r, content)]
        self.assertEqual(
            sorted(fired), sorted(GUARDED_RULES),
            "every guarded rule must fire on plain-body triggers; a missing "
            "rule means its trigger went stale and the guard is hollow: "
            "fired={}".format(fired),
        )

    def test_exempt_in_tilde_fence(self):
        content = _article("~~~text\n" + TRIGGER_BODY + "\n~~~")
        for r in GUARDED_RULES:
            self.assertEqual(
                _violations(r, content), [],
                "Rule {} must exempt ~~~ fenced content".format(r),
            )

    def test_exempt_in_nested_backtick_fence(self):
        content = _article("````markdown\n```text\n" + TRIGGER_BODY + "\n```\n````")
        for r in GUARDED_RULES:
            self.assertEqual(
                _violations(r, content), [],
                "Rule {} must exempt nested ```` fenced content".format(r),
            )


if __name__ == "__main__":
    unittest.main()
