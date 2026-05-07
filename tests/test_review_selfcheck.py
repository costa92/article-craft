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


class ReviewSelfcheckTests(unittest.TestCase):
    def test_rule_5_flags_template_cadence_and_missing_anchors(self):
        article = """---
title: demo
description: "demo"
---

# 标题

本文将从安装、配置、实践三个方面展开。

首先，我们先看安装部分。

其次，我们再看配置部分。

可以看到，这个方案比较完整。

从这个角度看，它也比较灵活。
"""
        result = review_selfcheck.check_rule_5(article, article.splitlines())

        self.assertFalse(result.passed)
        suggestions = [v.suggestion for v in result.violations]
        self.assertTrue(any("路线图" in s or "本文将" in s for s in suggestions))
        self.assertTrue(any("具体锚点" in s for s in suggestions))
        self.assertTrue(any("第一人称" in s for s in suggestions))

    def test_rule_5_passes_with_personal_voice_tradeoffs_and_evidence(self):
        article = """---
title: demo
description: "demo"
---

# 标题

我在把旧项目从 pip 迁到 uv 时，第一次卡在 `uv sync` 读不到私有源，终端直接报了 401。

我最后的处理办法很土：先把凭证写进 `~/.config/uv/credentials.toml`，再跑一次，2.3 秒就过了。

这个方案的优点是快，缺点也很明显：团队里如果有人还在用 Python 3.9，锁文件会多出一层兼容成本。
"""
        result = review_selfcheck.check_rule_5(article, article.splitlines())

        self.assertTrue(result.passed, result.details)

    def test_rule_12_flags_template_summary(self):
        article = """---
title: demo
description: "demo"
---

# 标题

本文将详细介绍 uv 的核心能力。
"""
        result = review_selfcheck.check_rule_12(article, article.splitlines())

        self.assertFalse(result.passed)
        self.assertEqual(result.rule_id, 12)

    def test_rule_5_flags_three_paragraphs_without_anchor_density(self):
        article = """---
title: demo
description: "demo"
---

# 标题

## 总览

我在团队里试过几次这种工作流，第一感觉是它写得很顺，但也容易把问题说得太圆。

这种写法的问题不在于观点错，而在于每段都像总结，没有把读者真正会遇到的摩擦感写出来。

如果后面几段继续这样平铺，整篇文章就会越来越像整理稿，而不像一个人真的做过这件事。

到了这里，正文已经连续三段都在解释，却没有命令、报错、路径或数字把判断钉住。
"""
        result = review_selfcheck.check_rule_5(article, article.splitlines())

        self.assertFalse(result.passed)
        self.assertTrue(any("章节「总览」连续 3 段" in v.text for v in result.violations))

    def test_rule_5_flags_consecutive_summary_tone_without_anchor(self):
        article = """---
title: demo
description: "demo"
---

# 标题

## 判断

我在团队里试过这种写法两次，第一次就感觉它太像整理稿。

核心问题在于，这一段虽然在解释方向，但没有把真实代价和操作面写出来。

更重要的是，后面如果继续这样铺开，读者只会看到顺滑总结，而看不到具体摩擦。
"""
        result = review_selfcheck.check_rule_5(article, article.splitlines())

        self.assertFalse(result.passed)
        self.assertTrue(any("章节「判断」连续 2 段总结腔" in v.text for v in result.violations))

    def test_rule_5_does_not_flag_when_code_block_breaks_density_run(self):
        article = """---
title: demo
description: "demo"
---

# 标题

## 实战

这一段先交代背景，但还没有落到具体证据。

第二段继续解释问题，仍然没有命令或数字。

```bash
uv sync
```

第三段虽然还是说明文，但中间已经有代码块打断。
"""
        result = review_selfcheck.check_rule_5(article, article.splitlines())

        self.assertTrue(not any("章节「实战」连续 3 段缺少具体锚点" in v.text for v in result.violations))

    def test_rule_6_skips_writing_conclusion_sections(self):
        article = """---
title: demo
description: "demo"
---

# 标题

## 写在最后

这是一段结尾总结，不应该因为没有两个代码块被判浅层。
"""
        result = review_selfcheck.check_rule_6(article, article.splitlines())

        self.assertTrue(result.passed, result.details)


class TextStripHelperTests(unittest.TestCase):
    def test_strip_callout_blocks_removes_obsidian_callouts(self):
        from scripts.review_selfcheck import _strip_callout_blocks
        text = "正常一段。\n\n> [!info] 标题\n> 提示内容\n> 第二行\n\n下一段。"
        result = _strip_callout_blocks(text)
        self.assertIn("正常一段", result)
        self.assertIn("下一段", result)
        self.assertNotIn("提示内容", result)

    def test_strip_callout_blocks_preserves_normal_blockquotes(self):
        from scripts.review_selfcheck import _strip_callout_blocks
        # > without [!type] is a normal blockquote — keep it.
        text = "> 引用一句话\n> 第二行"
        result = _strip_callout_blocks(text)
        self.assertIn("引用一句话", result)

    def test_strip_image_lines_removes_markdown_image_syntax(self):
        from scripts.review_selfcheck import _strip_image_lines
        text = "段一。\n![alt text](https://x.com/y.png)\n段二。"
        result = _strip_image_lines(text)
        self.assertIn("段一", result)
        self.assertIn("段二", result)
        self.assertNotIn("![", result)

    def test_strip_image_lines_does_not_touch_inline_image(self):
        from scripts.review_selfcheck import _strip_image_lines
        # An image embedded in a sentence (not its own line) should remain.
        text = "正常段落 ![tiny](inline.png) 句尾继续。"
        result = _strip_image_lines(text)
        self.assertIn("![tiny]", result)


if __name__ == "__main__":
    unittest.main()
