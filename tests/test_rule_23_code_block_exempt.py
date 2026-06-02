"""Tests for Rule 23 — AIGC reverse-declaration detection must exempt
content inside fenced code blocks (` ``` `).

Bug history: v1.7.1 initial implementation computed `body = strip_code_blocks(...)`
but then iterated over `lines` (full content) in the violation loop — the
strip-result was never consumed. Articles that documented Rule 23 itself by
putting reverse declarations as examples inside a ```text block were
incorrectly flagged as violating Rule 23.

Fix: track which line numbers fall inside fenced code blocks, and skip them
in the violation loop. The line-by-line scan is intentional (we need original
line numbers for error reporting) — we can't just iterate over body lines.
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


def run_rule_23(content: str):
    """Convenience: run check_rule_23 on raw content, return errors."""
    result = rs.check_rule_23(content, content.split("\n"))
    errors = [v for v in result.violations if v.severity == "error"]
    warnings = [v for v in result.violations if v.severity == "warning"]
    return result, errors, warnings


class CodeBlockExemptionTests(unittest.TestCase):
    def test_reverse_declaration_in_code_block_exempt(self):
        """Reverse declarations inside ```text fenced block must NOT trigger."""
        content = """---
title: 测试
---

# Title

正文段落，无反向声明。

```text
Rule 23 反例报告:
  L3 反向声明: 非 AI 生成
  L3 反向声明: 纯手写
  L12 反向声明: 完全人工撰写
```

正文继续，仍无反向声明。
"""
        _, errors, _ = run_rule_23(content)
        self.assertEqual(
            len(errors), 0,
            "Code-block exemption failed: {}".format([e.text for e in errors]),
        )

    def test_reverse_declaration_in_python_block_exempt(self):
        """Reverse declarations inside ```python block also exempt."""
        content = """---
title: 测试
---

# Title

```python
PATTERNS = [
    r'非\\s*AI\\s*生成',
    r'纯\\s*手写',
]
```
"""
        _, errors, _ = run_rule_23(content)
        self.assertEqual(len(errors), 0)

    def test_reverse_declaration_in_body_text_still_caught(self):
        """Normal body text reverse declarations must still trigger."""
        content = """---
title: 测试
---

# Title

声明：本文非 AI 生成，纯手写。
"""
        _, errors, _ = run_rule_23(content)
        self.assertGreaterEqual(
            len(errors), 2,
            "Body 内反向声明应触发 >=2 错误 (non-AI + pure-handwrite),"
            " actual {}".format(len(errors)),
        )

    def test_mixed_body_and_code_block(self):
        """Body declaration triggers, code-block example exempt — only body counted."""
        content = """---
title: 测试
---

# Title

本文非 AI 生成。

```text
反例说明: 不要写"非 AI 生成"
```
"""
        _, errors, _ = run_rule_23(content)
        # 仅 line 7 的正文反向声明应触发，代码块第 11 行豁免
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].line, 7)

    def test_clean_article_passes(self):
        """Clean article with AIGC label and no reverse decls passes cleanly."""
        content = """---
title: 我用半年踩出的 4 条筛选规则
---

# 我用半年踩出的 4 条筛选规则

正常内容。

> 本文 AI 辅助起稿 + 人工核实改写。
"""
        result, errors, warnings = run_rule_23(content)
        self.assertTrue(result.passed)
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(warnings), 0)

    def test_marketing_headline_still_warns(self):
        """Marketing headline in title still emits WARNING (not affected by fix)."""
        content = """---
title: 震惊！我发现了一个秘密
---

# 震惊！我发现了一个秘密

正常内容。
"""
        _, errors, warnings = run_rule_23(content)
        self.assertEqual(len(errors), 0)
        self.assertGreaterEqual(len(warnings), 1)


class CodeBlockBoundaryTests(unittest.TestCase):
    """Edge cases for the code-block line tracking."""

    def test_unclosed_code_block(self):
        """Unclosed ``` should still exempt subsequent lines (defensive)."""
        content = """---
title: 测试
---

```text
非 AI 生成
"""
        # Even without closing ```, our line tracker considers everything after
        # opening fence as in-code (in_code flips on, never flips off).
        _, errors, _ = run_rule_23(content)
        self.assertEqual(len(errors), 0)

    def test_indented_fence_does_not_close_block(self):
        """A 4-space-indented ``` is NOT a closing fence (CommonMark).

        The canonical iter_code_blocks scanner anchors fences at column 0
        (`^`{3,}`), so an indented ``` is content, not a close. The opening
        ```text block therefore stays open to EOF and "纯手写" is exempt.
        (The old hand-rolled toggle .strip()-ed first and wrongly closed here.)
        """
        content = """---
title: 测试
---

```text
非 AI 生成
    ```
仍在代码块内: 纯手写
"""
        _, errors, _ = run_rule_23(content)
        self.assertEqual(len(errors), 0)


class CanonicalFenceTests(unittest.TestCase):
    """The hand-rolled startswith('```') toggle misses ~~~ fences and treats a
    bare ``` inside a ```` block as a close. Both let a reverse declaration
    documented as a code example leak into the violation scan. The canonical
    iter_code_blocks scanner handles both.
    """

    def test_reverse_declaration_in_tilde_fence_exempt(self):
        content = """---
title: 测试
---

# Title

~~~text
反例: 非 AI 生成
反例: 纯手写
~~~

正文，无反向声明。
"""
        _, errors, _ = run_rule_23(content)
        self.assertEqual(
            len(errors), 0,
            "~~~ fenced reverse declarations must be exempt: {}".format(
                [e.text for e in errors]),
        )

    def test_reverse_declaration_in_nested_backtick_fence_exempt(self):
        # A ```` block whose body shows a ```text example. The inner ``` must
        # NOT close the outer ```` block (CommonMark: close needs >= open length).
        content = """---
title: 测试
---

# Title

````markdown
示例代码块：
```text
非 AI 生成
```
````

正文，无反向声明。
"""
        _, errors, _ = run_rule_23(content)
        self.assertEqual(
            len(errors), 0,
            "nested ``` inside ```` must stay in-code: {}".format(
                [e.text for e in errors]),
        )


if __name__ == "__main__":
    unittest.main()
