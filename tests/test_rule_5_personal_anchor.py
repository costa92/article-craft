"""Tests for B15 — check_rule_5 personal-anchor regex now covers natural
Chinese tech-blog phrasings (我接 / 我自己 / 我跑 / 本机实测 / …) while
avoiding false positives like `我是开发者`.
"""

import importlib.util
import re
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


# The regex inlined in check_rule_5. We rebuild it here to test markers in
# isolation; the integration test below also exercises the real function.
PERSONAL_ANCHOR_PATTERN = re.compile(
    r'我(?:在|曾|的|会|用|选|踩|测|最后|发现|看|做|跑|试|觉得|以为|之前|后来|当时|'
    r'读|查|翻|改|写|删|跑通|没跑通|发觉|意识到|意外|没料到|接|搞|想|担心|赌|碰|自己)'
    r'|踩坑|踩过|实测|本机实测|实测下来|我的(?:经验|理解|做法)|生产环境中.*我'
    r'|从.{0,6}经验看|我们最后|这次我'
)


SHOULD_MATCH = [
    "我看了官方文档",
    "我做了一个 demo",
    "我跑了一遍发现不对",
    "我自己试过同样的配置",
    "我自己的工作流是这样",
    "本机实测，冷启动 2 秒",
    "实测下来稳定不掉链子",
    "我接了这个 agent 项目",
    "我接过类似的需求",
    "踩过坑的人都知道",
    "我在迁移旧项目时发现",
    "我会优先用 uv",
    "我最后的处理办法是",
    "我读了源码",
    "我查了 changelog",
    "我改了配置后重跑",
    "我之前用过 poetry",
    "我后来换了方案",
    "我当时没想到这个坑",
    "我们最后决定用 Pulumi",
    "这次我换了实现",
    "我的经验是先验证再迁移",
    "从过去三年的经验看",
]

SHOULD_NOT_MATCH = [
    "我是开发者",        # bare 我是, not actionable
    "我们一起来看",       # 我们 without 最后
    "他在做实验",         # third-person
    "这个工具不错",       # no first-person
    "运行结果是 OK",      # no first-person
    "我国的开发者",       # 我国 isn't a verb anchor (国 not in list)
    "我市的政策",         # same
]


class PersonalAnchorRegexUnit(unittest.TestCase):
    def test_natural_phrasings_match(self):
        for sample in SHOULD_MATCH:
            with self.subTest(sample=sample):
                self.assertTrue(
                    PERSONAL_ANCHOR_PATTERN.search(sample),
                    f"expected to match: {sample!r}",
                )

    def test_false_positive_phrasings_do_not_match(self):
        for sample in SHOULD_NOT_MATCH:
            with self.subTest(sample=sample):
                self.assertIsNone(
                    PERSONAL_ANCHOR_PATTERN.search(sample),
                    f"unexpectedly matched: {sample!r}",
                )


def _article_with_body(body: str) -> str:
    return (
        "---\n"
        "title: demo\n"
        'description: "demo"\n'
        "writing_style: B\n"
        "---\n"
        "\n"
        "# 标题\n\n" + body + "\n"
    )


class Rule5IntegrationTests(unittest.TestCase):
    """Drive the full check_rule_5 to verify personal_markers detection."""

    def test_natural_phrasings_satisfy_personal_anchor_requirement(self):
        """Article with `我接` + `我自己` + `本机实测` should not trip the
        'personal markers < 2' violation under neutral tone.
        """
        body = (
            "我接了一个 agent 项目，把网关切到 Envoy 时报了 `503`，端口冲突。\n\n"
            "我自己试过把端口改回 8080，跑了一遍，瓶颈在握手阶段，本机实测 1.2 秒。\n\n"
            "选 uv 而不是 poetry 的原因：v0.4.0 之后冷启动 200ms，比 poetry 1.7 快 5×。\n"
        )
        article = _article_with_body(body)
        result = review_selfcheck.check_rule_5(article, article.splitlines())
        # Should NOT have a personal-marker violation.
        joined = " ".join(v.suggestion for v in result.violations)
        self.assertNotIn(
            "第一人称",
            joined,
            f"unexpected personal-marker violation; details={result.details}, joined={joined}",
        )

    def test_three_natural_verbs_keep_rule5_marker_count_at_least_two(self):
        body = (
            "我跑了一遍冒烟测试，结果是 200。\n\n"
            "我读了源码，发现是 retry 的 backoff 写错了。\n\n"
            "我自己改完后 PR 在 v1.4.3 合并，本机实测，p99 从 800ms 掉到 90ms。\n"
        )
        article = _article_with_body(body)
        result = review_selfcheck.check_rule_5(article, article.splitlines())
        joined = " ".join(v.suggestion for v in result.violations)
        self.assertNotIn("第一人称", joined, joined)

    def test_legacy_passes_still_pass(self):
        """The existing test article in test_review_selfcheck.py should
        still be considered personal-rich. Run a representative paragraph.
        """
        body = (
            "我在把旧项目从 pip 迁到 uv 时，第一次卡在 `uv sync` 读不到私有源，终端直接报了 401。\n\n"
            "我最后的处理办法很土：先把凭证写进 `~/.config/uv/credentials.toml`，再跑一次，2.3 秒就过了。\n\n"
            "这个方案的优点是快，缺点也很明显：团队里如果有人还在用 Python 3.9，锁文件会多出一层兼容成本。\n"
        )
        article = _article_with_body(body)
        result = review_selfcheck.check_rule_5(article, article.splitlines())
        self.assertTrue(
            result.passed,
            f"legacy-style article should still pass; details={result.details} "
            f"violations={[v.text for v in result.violations]}",
        )


if __name__ == "__main__":
    unittest.main()
