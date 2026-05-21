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


class CLIRuleSelectionTests(unittest.TestCase):
    """Tests for the --rules / --write-gate / --gate-only CLI surface.

    These guard the contract that write SKILL.md Step 6 and review SKILL.md
    Phase 1 rely on: shelling out to review_selfcheck.py with a rule subset.
    """

    def setUp(self):
        # Article with known violations across rules 1, 6, 11, 13:
        # - Rule 1: "实际上" (red flag word)
        # - Rule 6: "## 一" only has 0 code blocks (shallow)
        # - Rule 11: "→" arrow in prose (ASCII diagram char)
        # - Rule 13: empty fence ``` opens an untagged block
        self.bad_article = """---
title: demo
description: "demo"
---

# 标题

实际上这是一个测试。

## 一

draft → 检查 → 通过

```
plain text in untagged block
```

## 二

正文。

```python
print("hi")
```

```python
print("ok")
```
"""

    def _write_tmp(self, content: str) -> str:
        import tempfile
        f = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8')
        f.write(content)
        f.close()
        return f.name

    def test_run_selected_rules_skips_unknown_rule_ids(self):
        path = self._write_tmp(self.bad_article)
        results, all_passed = review_selfcheck.run_selected_rules(path, [1, 99, 11])
        self.assertEqual(len(results), 3)
        # Unknown rule 99 is reported as skipped but passed=True (doesn't block).
        unknown = next(r for r in results if r.rule_id == 99)
        self.assertTrue(unknown.skipped)
        self.assertTrue(unknown.passed)
        # Rule 1 fails (red flag "实际上"), so all_passed is False.
        self.assertFalse(all_passed)

    def test_write_gate_rules_constant_matches_doc(self):
        """WRITE_GATE_RULES must stay in sync with the rules.md write column."""
        self.assertEqual(
            review_selfcheck.WRITE_GATE_RULES,
            (1, 2, 6, 11, 13, 16),
            "WRITE_GATE_RULES drift — update self-check-rules.md 'Who enforces what' too",
        )

    def test_parse_rule_list_handles_whitespace_and_commas(self):
        self.assertEqual(review_selfcheck._parse_rule_list("1,2,6"), [1, 2, 6])
        self.assertEqual(review_selfcheck._parse_rule_list(" 1 , 11 "), [1, 11])
        self.assertEqual(review_selfcheck._parse_rule_list("1,,11"), [1, 11])

    def test_parse_rule_list_rejects_non_integer(self):
        with self.assertRaises(SystemExit):
            review_selfcheck._parse_rule_list("1,foo,3")

    def test_cli_write_gate_exit_code_on_failure(self):
        """End-to-end: --write-gate must exit 1 when Rule 1/6/11/13 fails."""
        import subprocess
        path = self._write_tmp(self.bad_article)
        script = (Path(__file__).resolve().parents[1] / "scripts" / "review_selfcheck.py")
        proc = subprocess.run(
            ["python3", str(script), path, "--write-gate"],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 1, f"Expected exit 1, got {proc.returncode}\nstdout: {proc.stdout}\nstderr: {proc.stderr}")
        # Output should mention at least one of the failing rules.
        combined = proc.stdout + proc.stderr
        self.assertTrue(
            any(tag in combined for tag in ("Rule 1", "Rule 6", "Rule 11", "Rule 13")),
            f"Output should name a failing rule. Got: {combined[:500]}",
        )

    def test_cli_write_gate_exit_code_on_pass(self):
        """End-to-end: --write-gate must exit 0 on a clean article that
        satisfies rules 1/2/6/11/13/16. Companion to the failure test."""
        import subprocess
        clean_article = """---
title: 干净测试文章
description: "一篇人为构造的干净文章，给 write-gate 跑过 happy path 用。"
---

# 干净测试文章

这是一个手工准备的测试文章 hook，用具体例子作开头。我跑过一次发现可以稳定通过 --write-gate 的全部六条规则。

## 第一节：核心代码

下面是两个具体的可执行代码块，每一段之间有解释。

```python
def add(a, b):
    return a + b
```

加法函数返回两数之和。下面是减法。

```python
def sub(a, b):
    return a - b
```

减法返回差。

## 第二节：进一步示例

第二节同样保持两个代码块的最低密度。

```python
result = add(2, 3)
assert result == 5
```

中间夹一段对照的运行说明。

```python
result2 = sub(10, 4)
assert result2 == 6
```

这就是全部测试样例。
"""
        path = self._write_tmp(clean_article)
        script = (Path(__file__).resolve().parents[1] / "scripts" / "review_selfcheck.py")
        proc = subprocess.run(
            ["python3", str(script), path, "--write-gate"],
            capture_output=True, text=True,
        )
        self.assertEqual(
            proc.returncode, 0,
            f"--write-gate should exit 0 on clean article. "
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}",
        )

    def test_cli_rules_rejects_empty_list(self):
        """--rules '' or --rules ',,,' must fail loudly, not silently pass."""
        import subprocess
        path = self._write_tmp(self.bad_article)
        script = (Path(__file__).resolve().parents[1] / "scripts" / "review_selfcheck.py")
        for bad in ("", ",,,", "  ,  ,"):
            proc = subprocess.run(
                ["python3", str(script), path, "--rules", bad],
                capture_output=True, text=True,
            )
            self.assertNotEqual(
                proc.returncode, 0,
                f"--rules {bad!r} should fail (argparse error), got exit 0",
            )
            # argparse-style errors go to stderr.
            self.assertIn("--rules", proc.stderr,
                          f"expected --rules error message, got: {proc.stderr!r}")

    def test_cli_rules_flag_overrides_write_gate(self):
        """--rules takes precedence over --write-gate (rules.md says so)."""
        import subprocess
        # Article passes rule 11 but fails rule 1.
        passing_11_failing_1 = """---
title: demo
description: "demo"
---

# 标题

实际上这是测试。

## 一

正文。

```python
print("ok")
```

```python
print("ok2")
```
"""
        path = self._write_tmp(passing_11_failing_1)
        script = (Path(__file__).resolve().parents[1] / "scripts" / "review_selfcheck.py")
        # --rules 11 alone should pass even though Rule 1 would fail.
        proc = subprocess.run(
            ["python3", str(script), path, "--rules", "11", "--write-gate"],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, f"--rules 11 should pass (Rule 1 ignored). stdout: {proc.stdout}")


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

    def test_rule_5_personal_marker_subcheck_skipped_at_casual_tone(self):
        # Body has zero personal markers — Rule 5 would fail at neutral.
        # At casual, it should be silent (Rule 17 takes over).
        from scripts.review_selfcheck import check_rule_5
        article = (
            "---\nwriting_style: B\ntone: casual\n---\n\n# T\n\n"
            + "纯技术描述。" * 100
        )
        result = check_rule_5(article, article.split("\n"))
        markers = [v for v in result.violations if "个人视角" in v.text]
        self.assertEqual(markers, [], "Rule 5 personal-marker check should defer to Rule 17 at casual+")

    def test_rule_5_personal_marker_subcheck_active_at_neutral_tone(self):
        from scripts.review_selfcheck import check_rule_5
        article = (
            "---\nwriting_style: A\ntone: neutral\n---\n\n# T\n\n"
            + "纯技术描述。" * 100
        )
        result = check_rule_5(article, article.split("\n"))
        markers = [v for v in result.violations if "个人视角" in v.text]
        self.assertEqual(len(markers), 1, "Rule 5 personal-marker check should fire at neutral")


if __name__ == "__main__":
    unittest.main()
