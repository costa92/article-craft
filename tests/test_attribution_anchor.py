"""Attribution-as-anchor: source-derived articles (YouTube/research/docs) should
not be penalized by Rule 5 / Rule 22 for lacking fabricated first-person voice.

Motivated by a dogfood run: a faithful, fully-attributed video summary got
flagged "个人视角/经历 too low" while a from-scratch article passed by inventing
personal anecdotes. Recognizing attribution closes that perverse incentive.
"""

import importlib.util
import unittest
from pathlib import Path


def _load():
    p = Path(__file__).resolve().parents[1] / "scripts" / "review_selfcheck.py"
    spec = importlib.util.spec_from_file_location("review_selfcheck_attr", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


rs = _load()


class AttributionAnchorTests(unittest.TestCase):
    def test_attribution_counts_as_concrete_anchor(self):
        for para in [
            "据官方文档显示，这个功能在 2024 年就上线了。",
            "Karpathy 演示了模型如何调用浏览器去搜索。",
            "视频里提到，训练成本大约要几百万美元。",
            "根据论文报告，性能随规模平滑提升。",
        ]:
            self.assertTrue(rs._has_concrete_anchor(para), f"should anchor: {para}")

    def test_plain_opinion_without_source_is_not_anchored(self):
        # No source, no number/command → still not an anchor (rule still bites
        # genuinely vague prose).
        self.assertFalse(rs._has_concrete_anchor("这个东西总体来说还是挺不错的，值得一试。"))

    def test_rule5_no_anchor_warning_for_attributed_section(self):
        # casual tone (skips the personal-marker check); a section of 3 attributed
        # paragraphs must NOT trip "连续 3 段缺少具体锚点".
        article = """---
title: demo
description: "demo"
writing_style: B
tone: casual
---

# 标题

## 视频讲了什么

据官方说明，这个模型本质上就是两个文件。

Karpathy 演示了它怎么一步步预测下一个词。

视频里提到，整个训练靠的是海量文本压缩。
"""
        r = rs.check_rule_5(article, article.splitlines())
        offenders = [v.text for v in r.violations if "连续 3 段缺少具体锚点" in v.text]
        self.assertEqual(offenders, [], f"attributed paras should be anchored: {offenders}")

    def test_rule22_passes_on_attribution_without_personal_experience(self):
        # 0 personal experience but ≥2 source attributions → 经历/来源归属 sub-check
        # must NOT fire.
        body = """---
title: demo
description: "demo"
---

# 标题

据官方数据，部署耗时降到 47ms。我推荐这个方案。

Karpathy 在视频里说，规模定律让性能可预测。

根据报告显示，准确率提升了 30%。
"""
        r = rs.check_rule_22(body, body.splitlines())
        offenders = [v.text for v in r.violations if "经历" in v.text or "来源归属" in v.text]
        self.assertEqual(offenders, [], f"attribution should satisfy the voice check: {offenders}; details={r.details}")

    def test_rule5_skips_conclusion_section_for_anchor_check(self):
        # "写在最后" is reflective by nature; its paragraphs shouldn't be required
        # to carry command/number anchors (Rule 6 already skips such sections).
        article = """---
title: demo
description: "demo"
writing_style: B
tone: casual
---

# 标题

## 写在最后

工具卷成这样，对我们其实是好事，心态放平就行。

如果你也在纠结，先想清楚自己最高频的场景是哪类。

觉得有用就点个收藏，转给需要的朋友。
"""
        r = rs.check_rule_5(article, article.splitlines())
        offenders = [v.text for v in r.violations if "连续 3 段缺少具体锚点" in v.text]
        self.assertEqual(offenders, [], f"conclusion section should be skipped: {offenders}")

    def test_rule22_still_flags_when_neither_experience_nor_attribution(self):
        body = """---
title: demo
description: "demo"
---

# 标题

这个方案总体不错。它在很多场景下表现良好，整体值得考虑使用。
"""
        r = rs.check_rule_22(body, body.splitlines())
        offenders = [v.text for v in r.violations if "经历" in v.text or "来源归属" in v.text]
        self.assertTrue(offenders, "no experience and no attribution should still warn")


if __name__ == "__main__":
    unittest.main()
