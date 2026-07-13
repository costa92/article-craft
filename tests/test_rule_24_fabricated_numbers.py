"""Tests for Rule 24 — fabricated-number detection (v1.7.2+, warning).

Detects "数字 + 单位" claims in body text that lack source attribution.
Warning-level (passed=True), not blocking — designed to surface
unverified numbers for author review, not to mechanically gate publish.

Motivation: LLM-authored articles tend to confidently invent specific
numbers to make claims sound credible. Rule 22 counts subjective-judgment
density, Rule 23 catches AIGC reverse declarations, but neither
verifies number truthfulness. Rule 24 fills this blind spot — see
references/self-check-rules.md Rule 24 for full design rationale.

Exemptions:
  1. backtick-enclosed `..` (treated as code/literal)
  2. line contains markdown link [..](http..)
  3. number in frontmatter verified_numbers whitelist
  4. hedge prefix in same sentence (约/大概/我估计/可能...)
  5. hedge postfix immediately after (左右/上下/前后...)
  6. year format (19xx/20xx 年)
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


def run_rule_24(content: str):
    result = rs.check_rule_24(content, content.split("\n"))
    return result, result.violations


class BareClaimDetectionTests(unittest.TestCase):
    """Numbers without any exemption should fire."""

    def test_percentage_with_unit(self):
        content = """---
title: t
---

# T

我的项目过期率 30%, 节省 100 美元/天。
"""
        _, v = run_rule_24(content)
        self.assertGreaterEqual(len(v), 2)

    def test_time_units(self):
        content = """---
title: t
---

# T

LAT.md 处理 1000 个文件用 50 秒。
"""
        _, v = run_rule_24(content)
        self.assertGreaterEqual(len(v), 2)

    def test_passed_is_always_true_warning_level(self):
        """Rule 24 is warning-only, never blocks publish."""
        content = """---
title: t
---

# T

5 个事故，10 起异常，60 秒平均处理时间。
"""
        result, v = run_rule_24(content)
        self.assertTrue(result.passed, "Rule 24 must be warning-level")
        self.assertGreater(len(v), 0, "must still record warnings")


class ExemptionTests(unittest.TestCase):
    """Each exemption mechanism should suppress the warning."""

    def test_backtick_exempts(self):
        content = """---
title: t
---

# T

我的项目过期率 `30%`, 节省成本可观。
"""
        _, v = run_rule_24(content)
        # backtick-wrapped 30% should not fire
        triggers = [x for x in v if "30%" in x.text]
        self.assertEqual(len(triggers), 0)

    def test_number_between_two_code_spans_still_fires(self):
        # The number sits in the GAP between two separate code spans, not inside
        # either. The old nearest-backtick-pair heuristic wrongly exempted it;
        # backtick parity before the match (even = outside any span) catches it.
        content = """---
title: t
---

# T

`verify()` 命中 50% 的 `cases`，需要核对。
"""
        _, v = run_rule_24(content)
        triggers = [x for x in v if "50%" in x.text]
        self.assertEqual(
            len(triggers), 1,
            "number between two code spans must fire: {}".format(
                [x.text for x in v]),
        )

    def test_markdown_link_in_same_line_exempts(self):
        content = """---
title: t
---

# T

按 [pricing](https://anthropic.com/pricing) Claude 4 输入 15 美元/M tokens。
"""
        _, v = run_rule_24(content)
        self.assertEqual(len(v), 0)

    def test_hedge_prefix_约_exempts(self):
        content = """---
title: t
---

# T

我估计大概 30% 的项目会用 LAT.md。约 6 周可以见效。
"""
        _, v = run_rule_24(content)
        self.assertEqual(len(v), 0)

    def test_hedge_postfix_左右_exempts(self):
        content = """---
title: t
---

# T

每次 review 大约 20 分钟左右就够。
"""
        _, v = run_rule_24(content)
        triggers = [x for x in v if "20" in x.text]
        self.assertEqual(len(triggers), 0)

    def test_verified_numbers_frontmatter_exempts(self):
        content = """---
title: t
verified_numbers:
  - 22条
  - 14个
---

# T

article-craft 有 22 条规则, 14 个 SKILL.md。
"""
        _, v = run_rule_24(content)
        triggers = [x for x in v if "22" in x.text or "14" in x.text]
        self.assertEqual(len(triggers), 0)

    def test_year_excluded(self):
        content = """---
title: t
---

# T

LAT.md 发布于 2026 年 5 月，那时我在写 v1.7 系列。
"""
        _, v = run_rule_24(content)
        # 2026 年 should be excluded (year pattern)
        triggers = [x for x in v if "2026" in x.text]
        self.assertEqual(len(triggers), 0)

    def test_code_block_exempts(self):
        content = """---
title: t
---

# T

```bash
# article-craft 项目 12 个月内命中 7 个事故
echo "100 美元"
```

正文里的 50% 命中率算事实声明。
"""
        _, v = run_rule_24(content)
        # only the 50% in body should fire
        self.assertEqual(len(v), 1)
        self.assertIn("50%", v[0].text)

    def test_tilde_fence_exempts(self):
        # ~~~ fences are invisible to the hand-rolled startswith('```') toggle,
        # so numbers inside leak into the scan. The canonical scanner fixes it.
        content = """---
title: t
---

# T

~~~bash
echo "命中率 99%, 节省 500 美元/天"
~~~

正文无具体数字。
"""
        _, v = run_rule_24(content)
        self.assertEqual(
            len(v), 0,
            "~~~ fenced numbers must be exempt: {}".format([x.text for x in v]),
        )


class FuzzyHedgeTests(unittest.TestCase):
    """Hedge detection allows some flexibility in spacing."""

    def test_hedge_with_intervening_words(self):
        content = """---
title: t
---

# T

需要语义关联的查询每周可能就 2-3 次。
"""
        _, v = run_rule_24(content)
        # "可能就 2-3 次" — 可能 is 5 chars before digit, allowed
        self.assertEqual(len(v), 0)

    def test_chinese_modal_quantifier_exempts(self):
        content = """---
title: t
---

# T

几起事故 / 数个文件 / 若干次失败。
"""
        _, v = run_rule_24(content)
        self.assertEqual(len(v), 0)


class SeparationOfSentencesTests(unittest.TestCase):
    """Hedge in one sub-clause should not exempt other sub-clauses."""

    def test_comma_splits_hedge_scope(self):
        content = """---
title: t
---

# T

我的项目过期率约 30%, 节省 100 美元/天。
"""
        # "约 30%" is exempt, "100 美元/天" is not
        _, v = run_rule_24(content)
        self.assertEqual(len(v), 1)
        self.assertIn("100", v[0].text)


class FrontmatterBoundaryTests(unittest.TestCase):
    """The frontmatter skip must track the real closing '---', not a
    'first 20 lines that look like yaml' heuristic. Chinese chars are \\w under
    Unicode, so a body line like '实测结果: 提升 50%' matches ^\\s*\\w+:\\s and
    was wrongly skipped when it sat in the first 20 lines.
    """

    def test_body_yaml_shaped_line_still_scanned(self):
        content = """---
title: t
---

# T

实测结果: 提升 50%，节省 100 美元。
"""
        _, v = run_rule_24(content)
        # Both numbers are real body claims and must fire (not skipped as fm).
        self.assertGreaterEqual(
            len(v), 2,
            "yaml-shaped body line must still be scanned: {}".format(
                [x.text for x in v]),
        )

    def test_real_frontmatter_field_still_exempt(self):
        # A genuine frontmatter field with a number must NOT fire.
        content = """---
title: t
reading_time: 5 分钟
---

# T

正文无数字。
"""
        _, v = run_rule_24(content)
        self.assertEqual(len(v), 0)


class HighDensityWarningTests(unittest.TestCase):
    def test_high_density_marker(self):
        """When >5 unverified NOVEL claims appear, details should say 高密度.

        Since the noise-bucket refinement, structural counts (个/文件/…)
        no longer count toward the threshold — fixture uses 6 novel claims.
        """
        content = """---
title: t
---

# T

数字 1: 30%。数字 2: 50%。数字 3: 100 美元。数字 4: 200 tokens。数字 5: 500 行。数字 6: 16GB。
"""
        result, v = run_rule_24(content)
        self.assertGreater(len(v), 5)
        self.assertIn("高密度", result.details)


if __name__ == "__main__":
    unittest.main()
