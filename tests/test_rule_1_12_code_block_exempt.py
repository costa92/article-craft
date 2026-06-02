"""Tests for Rule 1 (红旗词汇) and Rule 12 (模板化摘要) — both must exempt
content inside fenced code blocks (` ``` `).

Bug history (same regression class as Rule 23):

- check_rule_1 only skipped the fence *lines* (`startswith('```') → continue`),
  not the content between fences, so red-flag words (赋能/闭环/抓手/底层逻辑)
  appearing inside a demo log or a quoted example tripped the rule. Rule 1 is a
  WRITE GATE (WRITE_GATE_RULES), so this false positive could block the save.

- check_rule_12 computed `text = strip_code_blocks(body)` but then iterated the
  full `lines` (the strip-result was dead), so a template-summary phrase inside a
  ```text example was flagged. Rule 12 is diagnostic-only, so it degraded review
  signal rather than blocking save.

Fix (both): track which line numbers fall inside fenced code blocks and skip them
in the violation loop — the same `code_lines` set idiom already used by Rule 23.
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


class Rule1CodeBlockExemptionTests(unittest.TestCase):
    def test_red_flag_word_in_code_block_exempt(self):
        """Red-flag words inside a ```text fenced block must NOT trip the GATE."""
        content = """---
title: 测试
---

# Title

正文段落，自然表达，无红旗词。

```text
这里是赋能闭环抓手底层逻辑的示例输出
```

正文继续。
"""
        result = rs.check_rule_1(content, content.split("\n"))
        self.assertTrue(
            result.passed,
            "Code-block exemption failed: {}".format([v.text for v in result.violations]),
        )

    def test_red_flag_word_in_body_still_caught(self):
        """Red-flag words in body prose must still be flagged (regression guard)."""
        content = """---
title: 测试
---

# Title

我们要为团队赋能，打造业务闭环。
"""
        result = rs.check_rule_1(content, content.split("\n"))
        self.assertFalse(result.passed)
        self.assertGreaterEqual(len(result.violations), 2)


class Rule12CodeBlockExemptionTests(unittest.TestCase):
    def test_template_summary_in_code_block_exempt(self):
        """A template-summary phrase inside a code block must NOT be flagged."""
        content = """---
title: 测试
---

# Title

真实的开头，从一个具体问题讲起。

```text
本文将详细介绍如何配置
```

正文继续。
"""
        result = rs.check_rule_12(content, content.split("\n"))
        self.assertTrue(
            result.passed,
            "Code-block exemption failed: {}".format([v.text for v in result.violations]),
        )

    def test_template_summary_in_body_still_caught(self):
        """Template-summary phrase in body prose must still be flagged."""
        content = """---
title: 测试
---

# Title

本文将详细介绍如何配置 Nginx 反向代理。
"""
        result = rs.check_rule_12(content, content.split("\n"))
        self.assertFalse(result.passed)
        self.assertGreaterEqual(len(result.violations), 1)


if __name__ == "__main__":
    unittest.main()
