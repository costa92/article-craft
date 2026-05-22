"""Tests for v1.7.4 Rule 4 tags enforcement (P2).

4 篇实测显示 article-craft 默认生成的 frontmatter 只 2 个 tag、
1 个中文 tag——100% 命中 Rule 4 失败。P2 双管齐下：
1. write SKILL.md Step 3a 加 Rule 4 硬约束（≥3 中文 tags）
2. publish SKILL.md Step 3.5.0 自动跑 Rule 4 自检 + 警告

This test verifies both ends of the contract are in place.
"""

import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WRITE_SKILL = REPO_ROOT / "skills" / "write" / "SKILL.md"
PUBLISH_SKILL = REPO_ROOT / "skills" / "publish" / "SKILL.md"
SELFCHECK_PY = REPO_ROOT / "scripts" / "review_selfcheck.py"


def load_selfcheck():
    spec = importlib.util.spec_from_file_location("review_selfcheck", SELFCHECK_PY)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class WriteSkillTagConstraintTests(unittest.TestCase):
    """write SKILL.md Step 3a must contain Rule 4 tags 硬约束."""

    def setUp(self):
        self.content = WRITE_SKILL.read_text(encoding="utf-8")

    def test_step_3a_mentions_rule_4_hard_constraint(self):
        # frontmatter section must call out Rule 4
        self.assertIn("Rule 4 tags 硬约束", self.content)

    def test_step_3a_shows_chinese_tag_example(self):
        # show a recommended pattern with Chinese mix
        # at least one of the recommended patterns must appear
        recommended = [
            "Kubernetes, Docker, 容器运维",
            "LLM, Claude Code, AI写作",
            "Python, uv, 包管理",
        ]
        hits = [p for p in recommended if p in self.content]
        self.assertGreater(
            len(hits), 0,
            "Step 3a must show at least one recommended mixed-Chinese tag example",
        )

    def test_step_3a_warns_against_pure_english_tags(self):
        # explicit negative example
        self.assertIn("MCP, AI, DevOps", self.content,
            "Step 3a should call out '[MCP, AI, DevOps]' as a negative example")


class PublishSkillSelfcheckTests(unittest.TestCase):
    """publish SKILL.md Step 3.5.0 must invoke Rule 4 auto-check."""

    def setUp(self):
        self.content = PUBLISH_SKILL.read_text(encoding="utf-8")

    def test_step_3_5_0_invokes_review_selfcheck_rule_4(self):
        # The bash invocation that runs Rule 4 must be present
        self.assertIn("--rules 4", self.content,
            "publish step 3.5.0 must invoke review_selfcheck.py --rules 4")

    def test_checklist_has_tags_item(self):
        # The new tags checkbox must appear in the checklist block
        self.assertIn("frontmatter tags ≥ 3 个 且 ≥ 3 个中文 tag", self.content)

    def test_dogfooding_reference_present(self):
        # Must cite the 4-article dogfood basis (so future editors don't gut this)
        self.assertIn("4 篇实测", self.content)


class Rule4IntegrationTests(unittest.TestCase):
    """End-to-end: feed a 2-tag article through review_selfcheck, confirm Rule 4 fails;
    feed a 3-Chinese-tag article, confirm Rule 4 passes."""

    def setUp(self):
        self.rs = load_selfcheck()

    def test_two_tags_fails_rule_4(self):
        article = """---
title: 测试
date: 2026-05-22
author: costa
description: 测试描述足够长以通过 description 检查
tags:
  - tag1
  - tag2
category: 测试
status: draft
---

# 测试

正文。
"""
        result = self.rs.check_rule_4(article, article.split("\n"))
        self.assertFalse(result.passed,
            "2-tag article should fail Rule 4 (tags <3)")

    def test_three_chinese_tags_passes_rule_4(self):
        article = """---
title: 测试
date: 2026-05-22
author: costa
description: 测试描述足够长以通过 description 检查
tags:
  - 容器运维
  - AI工具
  - 实战教程
category: 测试
status: draft
---

# 测试

正文。
"""
        result = self.rs.check_rule_4(article, article.split("\n"))
        self.assertTrue(result.passed,
            f"3 Chinese tags should pass Rule 4, got violations: "
            f"{[v.text for v in result.violations]}")

    def test_three_english_tags_fails_rule_4(self):
        article = """---
title: 测试
date: 2026-05-22
author: costa
description: 测试描述足够长以通过 description 检查
tags:
  - MCP
  - AI
  - DevOps
category: 测试
status: draft
---

# 测试

正文。
"""
        result = self.rs.check_rule_4(article, article.split("\n"))
        # 3 tags 数量够，但中文 tag <3 应该失败
        self.assertFalse(result.passed,
            "3 English-only tags should fail Rule 4 (Chinese tags <3)")


if __name__ == "__main__":
    unittest.main()
