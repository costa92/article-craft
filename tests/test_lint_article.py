import importlib.util
import tempfile
import unittest
from pathlib import Path


def load_lint_article_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "lint_article.py"
    spec = importlib.util.spec_from_file_location("lint_article", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


lint_article = load_lint_article_module()


class LintArticleTests(unittest.TestCase):
    def test_auto_fix_removes_mechanical_ai_phrases(self):
        text = """# 标题

本文将从安装、配置、实践三个方面展开。

首先，我们先看安装部分。

可以看到，这个方案比较完整。

从这个角度看，它也比较灵活。
"""
        fixed, stats = lint_article.auto_fix_text(text)

        self.assertNotIn("本文将", fixed)
        self.assertNotIn("首先，", fixed)
        self.assertNotIn("可以看到，", fixed)
        self.assertNotIn("从这个角度看，", fixed)
        self.assertEqual(stats["removed_roadmap_line"], 1)
        self.assertGreaterEqual(stats["removed_empty_judgement"], 2)
        self.assertGreaterEqual(stats["removed_paragraph_starter"], 1)

    def test_auto_fix_does_not_touch_code_blocks_or_placeholders(self):
        text = """# 标题

```text
首先，我们先看这个例子。
可以看到，这里只是示意。
```

<!-- IMAGE: cover - demo (16:9) -->
<!-- PROMPT: test -->

另外，这一段在正文里。
"""
        fixed, _stats = lint_article.auto_fix_text(text)

        self.assertIn("首先，我们先看这个例子。", fixed)
        self.assertIn("可以看到，这里只是示意。", fixed)
        self.assertIn("<!-- IMAGE: cover - demo (16:9) -->", fixed)
        self.assertIn("<!-- PROMPT: test -->", fixed)
        self.assertIn("这一段在正文里。", fixed)

    def test_main_fix_writes_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp) / "article.md"
            article.write_text("首先，这是一段正文。\n", encoding="utf-8")

            rc = lint_article.main(["--article", str(article), "--fix"])

            self.assertEqual(rc, 0)
            self.assertEqual(article.read_text(encoding="utf-8"), "这是一段正文。\n")

    def test_auto_fix_rewrites_red_flags_and_closing(self):
        text = """# 标题

这个工具可以赋能团队，一站式打通请求链路。

综上所述，希望本文对你有帮助。
"""
        fixed, stats = lint_article.auto_fix_text(text)

        self.assertIn("支持团队", fixed)
        self.assertIn("集成的", fixed)
        self.assertIn("调用路径", fixed)
        self.assertNotIn("综上所述", fixed)
        self.assertNotIn("希望本文对你有帮助", fixed)
        self.assertIn("下一步", fixed)
        self.assertGreaterEqual(stats["rewrote_red_flag"], 4)
        self.assertEqual(stats["removed_forbidden_closing"], 1)
        self.assertEqual(stats["added_concrete_closing"], 1)

    def test_auto_fix_removes_trailing_reference_section(self):
        text = """# 标题

正文内容。

## 参考资料
- [官方文档](https://example.com)
- [源码](https://example.com/repo)
"""
        fixed, stats = lint_article.auto_fix_text(text)

        self.assertNotIn("## 参考资料", fixed)
        self.assertNotIn("[官方文档]", fixed)
        self.assertEqual(stats["removed_reference_section"], 1)

    def test_auto_fix_splits_overlong_hook(self):
        text = """# 标题

pip 装包慢、venv 命令长、pyenv 配置烦，这几个问题在旧项目里会一起出现，而且每次换机器都要重新踩一遍，团队成员一多还会冒出新的环境差异。uv 用一个二进制把环境、锁文件和执行入口合到一起，后面我会只看它到底快在哪、坑在哪、值不值得换，以及它在老项目迁移里最容易踩的地方。

## 正文

内容。
"""
        fixed, stats = lint_article.auto_fix_text(text)

        self.assertEqual(stats["split_hook_paragraph"], 1)
        self.assertIn("\n\nuv 用一个二进制", fixed)

    def test_build_report_includes_category_summary(self):
        original = "本文将展开。\n"
        fixed = "\n"
        stats = {
            "removed_roadmap_line": 1,
            "removed_empty_judgement": 0,
            "removed_paragraph_starter": 2,
            "rewrote_red_flag": 1,
            "removed_forbidden_closing": 0,
            "added_concrete_closing": 0,
            "split_hook_paragraph": 0,
            "removed_reference_section": 0,
        }

        report = lint_article.build_report(original, fixed, stats)

        self.assertIn("### Changes by Category", report)
        self.assertIn("Removed roadmap filler lines: 1", report)
        self.assertIn("Removed mechanical paragraph starters: 2", report)
        self.assertIn("Rewrote red-flag words: 1", report)

    def test_analyze_high_risk_sections_reports_section_names(self):
        text = """# 标题

## 总览

核心问题在于，这一段只有判断，没有落实到真实操作面。

更重要的是，下一段依然还是总结，没有把代价写具体。

如果继续这样写，读者只会看到顺滑解释，而看不到真实摩擦。
"""
        findings = lint_article.analyze_high_risk_sections(text)

        self.assertTrue(any("总览: 连续 3 段缺少具体锚点" in item for item in findings))
        self.assertTrue(any("总览: 连续 2 段总结腔且缺少锚点" in item for item in findings))

    def test_build_report_includes_high_risk_sections(self):
        report = lint_article.build_report(
            "old\n",
            "new\n",
            {
                "removed_roadmap_line": 0,
                "removed_empty_judgement": 0,
                "removed_paragraph_starter": 1,
                "rewrote_red_flag": 0,
                "removed_forbidden_closing": 0,
                "added_concrete_closing": 0,
                "split_hook_paragraph": 0,
                "removed_reference_section": 0,
            },
            ["总览: 连续 3 段缺少具体锚点"],
        )

        self.assertIn("### High-Risk Sections", report)
        self.assertIn("总览: 连续 3 段缺少具体锚点", report)

    def test_analyze_high_risk_sections_respects_code_block_breaks(self):
        text = """# 标题

## 实战

这一段先解释背景，但还没有具体锚点。

第二段继续解释取舍，也还没有数字和路径。

```bash
uv sync
```

第三段继续说明，但前面已经有代码块打断。
"""
        findings = lint_article.analyze_high_risk_sections(text)

        self.assertFalse(any("实战: 连续 3 段缺少具体锚点" in item for item in findings))


if __name__ == "__main__":
    unittest.main()
