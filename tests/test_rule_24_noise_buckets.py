"""Tests for Rule 24 — noise-bucket refinements (design-debt follow-up).

Field data (2026-07-13, 39 window articles, 480 warnings) showed the two
dominant noise classes are NOT the version numbers the debt item described
(those are already blocked by the `(?<![`\\w\\.])` lookbehind in
NUMERIC_CLAIM_PATTERN — pinned here), but:

1. Calendar months ("6 月", "6 月 21 日") — structural temporal references,
   same class as the already-exempt year patterns in EXCLUDED_PATTERNS.
2. Structural counts ("3 个", "5 篇") — enumerations of things in the
   article's own scope, not fabricatable measurements.

Refinement contract:
- Calendar months 1-12 are exempt entirely (like years). Non-calendar
  numbers with 月 ("18 月") still warn.
- Structural-count units (个/篇/条/次/轮/组/文件/人/起) still warn but do
  NOT count toward the >5 high-density flag; only novel claims
  (measurements: %, 倍, time, bytes, money, tokens, throughput, 行) do.
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

FM = """---
title: 测试
---

# Title

"""


def run_rule_24(content: str):
    result = rs.check_rule_24(content, content.split("\n"))
    return result, result.violations


class CalendarMonthExemptionTests(unittest.TestCase):
    def test_year_month_date_exempt(self):
        """"2026 年 6 月" — the month part must not warn (year already exempt)."""
        content = FM + "项目在 2026 年 6 月发布了新版本。\n"
        _, violations = run_rule_24(content)
        self.assertEqual([v.text for v in violations], [])

    def test_bare_month_day_exempt(self):
        """"6 月 21 日更新" — calendar month must not warn."""
        content = FM + "文档在 6 月 21 日更新过一次。\n"
        _, violations = run_rule_24(content)
        self.assertEqual([v.text for v in violations], [])

    def test_all_calendar_months_exempt(self):
        """Months 1-12 are all exempt."""
        content = FM + "\n".join(f"第{i}件事发生在 {i} 月。" for i in range(1, 13)) + "\n"
        _, violations = run_rule_24(content)
        self.assertEqual([v.text for v in violations], [])

    def test_non_calendar_month_number_still_warns(self):
        """"18 月" is not a calendar month — still a (weird) duration claim."""
        content = FM + "这个项目坚持了 18 月之久。\n"
        _, violations = run_rule_24(content)
        self.assertEqual(len(violations), 1)

    def test_duration_ge_month_still_warns(self):
        """"6 个月" (duration) matches the 个 unit and still warns."""
        content = FM + "迁移一共花了 6 个月。\n"
        _, violations = run_rule_24(content)
        self.assertEqual(len(violations), 1)

    def test_month_range_exempt(self):
        """"6-8 月" — calendar month range is the same temporal-reference
        class as a single month and must not warn."""
        content = FM + "活动持续到 6-8 月。\n"
        _, violations = run_rule_24(content)
        self.assertEqual([v.text for v in violations], [])

    def test_month_range_with_invalid_endpoint_still_warns(self):
        """"6-18 月" — endpoint outside 1-12 is not a calendar range."""
        content = FM + "上线要 6-18 月才能完成。\n"
        _, violations = run_rule_24(content)
        self.assertEqual(len(violations), 1)


class DurationCueOverrideTests(unittest.TestCase):
    """"N 月" preceded by a duration verb (历时/耗时/花了/持续/坚持/长达…)
    or followed by 之久 is a time-measurement claim, not a calendar
    reference — the exemption must not silence it."""

    def test_duration_cue_before_month_warns(self):
        content = FM + "这个迁移历时 6 月才完成。\n"
        result, violations = run_rule_24(content)
        self.assertEqual(len(violations), 1)
        self.assertIn("新颖 1", result.details)

    def test_duration_zhijiu_after_month_warns(self):
        content = FM + "上线一共拖了 9 月之久。\n"
        _, violations = run_rule_24(content)
        self.assertEqual(len(violations), 1)

    def test_chixudao_is_not_a_duration_cue(self):
        """"持续到 6 月" — 持续+到 points at a calendar date, stays exempt."""
        content = FM + "灰度持续到 6 月。\n"
        _, violations = run_rule_24(content)
        self.assertEqual([v.text for v in violations], [])


class GeTimeUnitNovelBucketTests(unittest.TestCase):
    """"N 个月/个小时/个星期" is a time measurement — the 个-classifier
    capture must not demote it to the structural bucket (docs declare
    时间 a novel-claim class)."""

    def test_ge_month_counts_novel(self):
        content = FM + "迁移一共花了 6 个月。\n"
        result, violations = run_rule_24(content)
        self.assertEqual(len(violations), 1)
        self.assertIn("新颖 1 / 结构计数 0", result.details)

    def test_six_ge_durations_trigger_high_density(self):
        content = FM + (
            "迁移花了 3 个月。\n"
            "调优用了 6 个月。\n"
            "压测跑了 3 个小时。\n"
            "排队等了 2 个星期。\n"
            "冷备恢复要 5 个小时。\n"
            "灰度放量走了 4 个月。\n"
        )
        result, violations = run_rule_24(content)
        self.assertEqual(len(violations), 6)
        self.assertIn("高密度", result.details)

    def test_plain_ge_count_stays_structural(self):
        content = FM + "这 3 个技巧最有用。\n"
        result, violations = run_rule_24(content)
        self.assertEqual(len(violations), 1)
        self.assertIn("新颖 0 / 结构计数 1", result.details)


class VersionNumberPinTests(unittest.TestCase):
    """Pins: the debt item proposed exempting v\\d+.\\d+.\\d+ — already
    covered by the lookbehind. These tests keep it that way."""

    def test_v_prefixed_version_not_flagged(self):
        content = FM + "升级到 v1.7.4 之后一切正常。\n"
        _, violations = run_rule_24(content)
        self.assertEqual([v.text for v in violations], [])

    def test_bare_semver_not_flagged(self):
        content = FM + "从 1.7.3 迁移到 1.7.4 没有踩坑。\n"
        _, violations = run_rule_24(content)
        self.assertEqual([v.text for v in violations], [])


class HighDensityBucketTests(unittest.TestCase):
    def test_structural_counts_do_not_trigger_high_density(self):
        """6 structural counts still warn individually but are not 高密度."""
        content = FM + (
            "这 3 个技巧最有用。\n"
            "我整理了 5 篇文章。\n"
            "一共踩了 4 条红线。\n"
            "重试了 7 次才成功。\n"
            "分成 2 组做对照。\n"
            "涉及 9 个文件。\n"
        )
        result, violations = run_rule_24(content)
        self.assertEqual(len(violations), 6)
        self.assertNotIn("高密度", result.details)

    def test_novel_claims_still_trigger_high_density(self):
        """6 novel measurement claims keep the 高密度 flag."""
        content = FM + (
            "成功率提升到 68% 了。\n"
            "冷启动只要 5 分钟。\n"
            "显存占用 16GB 起步。\n"
            "吞吐是原来的 3 倍。\n"
            "上下文吃掉 4096 tokens 不止。\n"
            "一个月账单 42 美元。\n"
        )
        result, violations = run_rule_24(content)
        self.assertEqual(len(violations), 6)
        self.assertIn("高密度", result.details)

    def test_mixed_buckets_count_only_novel(self):
        """3 structural + 3 novel = 6 warnings but only 3 novel → no 高密度."""
        content = FM + (
            "这 3 个技巧最有用。\n"
            "我整理了 5 篇文章。\n"
            "一共踩了 4 条红线。\n"
            "成功率提升到 68% 了。\n"
            "冷启动只要 5 分钟。\n"
            "显存占用 16GB 起步。\n"
        )
        result, violations = run_rule_24(content)
        self.assertEqual(len(violations), 6)
        self.assertNotIn("高密度", result.details)


if __name__ == "__main__":
    unittest.main()
