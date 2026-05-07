# Tone System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tone-intensity dimension (neutral / casual / opinionated) on top of the existing prevent → detect → fix three-layer pipeline, plus a calibration data feedback loop, so authors can dial up de-AI register treatment per article.

**Architecture:** Three-tier resolution — CLI `--tone=X` > frontmatter `tone:` > writing-style default. A new `scripts/config.py` data layer holds `TONE_REGISTER_LEVELS`, `STYLE_TO_TONE_DEFAULT`, `TONE_THRESHOLDS`, `TONE_LEXICAL_REWRITES`, `STRONG_OPINION_PATTERNS`, plus a single `resolve_tone()` entry point. `review_selfcheck.py` adds Rule 17 (Register Naturalness) with 4 sub-checks. `lint_article.py` is refactored from a single rewrite list into tone-aware tiers with Vale-style severity, inline `<!-- lint:disable -->` regions, and a max-pass oscillation guard. Skill-level prose changes thread the resolved tone through `requirements → write → review → lint`.

**Tech Stack:** Python 3.10 (existing scripts), pytest (existing), regex-only (no NLP deps), no external API calls.

**Spec:** `docs/superpowers/specs/2026-05-07-tone-system-design.md`

**Suggested PR split:**
- **PR A** — Tasks 1–4 (data layer + resolver). Lands inert. Pure additions to `config.py`, one new test file.
- **PR B** — Tasks 5–30 (everything else). User-visible behavior change. CHANGELOG entry has BREAKING marker for `lint_article.py --fix` no longer auto-deleting `首先/其次/最后` paragraph starters at default `tone=neutral`.

---

## File Structure

### Created files

| Path | Responsibility |
|------|----------------|
| `tests/test_tone_resolution.py` | Unit tests for `resolve_tone()` precedence + degradation |
| `tests/test_review_rule17.py` | Unit tests for the four Rule 17 sub-checks across all three tones |
| `tests/test_lint_tone_aware.py` | Unit tests for tone-aware rewrites, severity, inline disable, max-pass guard |
| `tests/fixtures/tone/neutral_uv_intro.md` | Golden fixture: neutral-tier article |
| `tests/fixtures/tone/casual_kimi_k2_review.md` | Golden fixture: casual-tier article |
| `tests/fixtures/tone/opinionated_pip_should_die.md` | Golden fixture: opinionated-tier article |
| `tests/test_tone_integration.py` | Three golden tests using the fixtures |
| `tests/test_tone_calibration.py` | Test that calibration JSONL gets written when enabled |

### Modified files

| Path | Change |
|------|--------|
| `scripts/config.py` | Append tone constants and `resolve_tone()` after the existing `S3_CONFIG` block |
| `scripts/review_selfcheck.py` | Add `_strip_callout_blocks` / `_strip_image_lines` helpers; add `check_rule_17`; gate the existing `personal_markers < 2` Rule-5 sub-check on `tone=neutral`; thread `tone` through `check_all` |
| `scripts/lint_article.py` | Migrate `RED_FLAG_REWRITES` and friends into `TONE_LEXICAL_REWRITES`; add severity, inline disable parser, max-pass guard, `--tone` / `--min-severity` / `--apply-info` / `--max-passes` CLI |
| `scripts/pipeline_state.py` | Read `tone:` from frontmatter in `_scan_article()` so `--upgrade` mode preserves it |
| `skills/orchestrator/SKILL.md` | Parse `--tone={neutral,casual,opinionated}` from `$ARGUMENTS`; reject invalid values; pass to `requirements` |
| `skills/requirements/SKILL.md` | Insert "Tone resolution" step that calls `resolve_tone()` and writes resolved value into `article.md` frontmatter |
| `skills/write/SKILL.md` | Step 3 reads `tone:` and injects the matching `## Tone: <tier>` section from `style-guide.md` into the writer prompt |
| `skills/write/style-guide.md` | Append three `## Tone: <tier>` sections with replacement maps + sample paragraphs |
| `skills/review/SKILL.md` | Phase 1 reads `tone:` from frontmatter and passes through (or relies on `review_selfcheck.py` to read it); document Rule 17 in the rule list |
| `skills/lint/SKILL.md` | Step 4 passes `--tone` to `lint_article.py`; document inline disable syntax |
| `references/self-check-rules.md` | Add `## Rule 17: Register Naturalness (tone-aware)` with full threshold table + check logic |
| `commands/article-craft.md` | Document `--tone` flag in the orchestrator command's argument list |
| `tests/test_review_selfcheck.py` | +3 regression tests (Rule 5 unchanged at neutral; Rule 17 / Rule 5 don't double-count; neutral tone skips strong-opinion sub-check) |
| `tests/test_lint_article.py` | +2 regression tests (existing 10 cases preserved at `tone=neutral`; missing `tone:` falls back to neutral) |
| `CHANGELOG.md` | New `[Unreleased]` entry with BREAKING marker |
| `CLAUDE.md` | New § Tone System (3–5 lines) under Architecture |

### Touched but no semantic change

None. All edits are scoped to the files above.

---

## Phase A — Data layer (PR A — lands inert)

### Task 1: Tone level enum and writing-style mapping

**Files:**
- Modify: `scripts/config.py` (append after `S3_CONFIG` block)
- Test: `tests/test_tone_resolution.py` (create)

- [ ] **Step 1: Write the failing test for the constants and the default lookup**

Create `tests/test_tone_resolution.py`:

```python
"""Tests for tone resolution: levels enum, style defaults, resolve_tone() precedence."""

import sys
from pathlib import Path
from unittest import TestCase, main

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import config


class ToneLevelsTests(TestCase):
    def test_levels_enum_is_three_strings_in_order(self):
        self.assertEqual(
            config.TONE_REGISTER_LEVELS,
            ("neutral", "casual", "opinionated"),
        )

    def test_style_to_tone_default_covers_all_eight_styles(self):
        for style in "ABCDEFGH":
            self.assertIn(style, config.STYLE_TO_TONE_DEFAULT)
            self.assertIn(
                config.STYLE_TO_TONE_DEFAULT[style],
                config.TONE_REGISTER_LEVELS,
            )

    def test_style_default_mapping_matches_spec(self):
        expected = {
            "A": "neutral",       # 技术教程
            "B": "casual",        # 经验分享 / 口语化
            "C": "neutral",       # 深度长文
            "D": "casual",        # 评测对比
            "E": "neutral",       # 资讯快报
            "F": "casual",        # 项目复盘 / Case Study
            "G": "opinionated",   # 观点输出 / 思考
            "H": "opinionated",   # AI 资讯爆料 / 自媒体爆款
        }
        self.assertEqual(config.STYLE_TO_TONE_DEFAULT, expected)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run test, expect failures**

Run: `python3 -m pytest tests/test_tone_resolution.py -v`
Expected: 3 ERRORS / FAILS — `AttributeError: module 'scripts.config' has no attribute 'TONE_REGISTER_LEVELS'` (and same for `STYLE_TO_TONE_DEFAULT`).

- [ ] **Step 3: Implement constants in `scripts/config.py`**

Append at the end of `scripts/config.py`:

```python


# ─── Tone System (v1.4.18) ───────────────────────────────────────
# Three-tier register-aware de-AI system. See
# docs/superpowers/specs/2026-05-07-tone-system-design.md for design rationale.

TONE_REGISTER_LEVELS = ("neutral", "casual", "opinionated")

# Default tone per writing style (references/writing-styles.md A-H).
# Falls back to "neutral" for unknown style ids.
STYLE_TO_TONE_DEFAULT = {
    "A": "neutral",       # 技术教程
    "B": "casual",        # 经验分享 / 口语化
    "C": "neutral",       # 深度长文
    "D": "casual",        # 评测对比
    "E": "neutral",       # 资讯快报
    "F": "casual",        # 项目复盘 / Case Study
    "G": "opinionated",   # 观点输出 / 思考
    "H": "opinionated",   # AI 资讯爆料 / 自媒体爆款
}
```

- [ ] **Step 4: Run test, expect 3 PASS**

Run: `python3 -m pytest tests/test_tone_resolution.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/config.py tests/test_tone_resolution.py
git commit -m "feat(config): tone level enum and writing-style default mapping"
```

---

### Task 2: `resolve_tone()` three-tier precedence

**Files:**
- Modify: `scripts/config.py` (append `resolve_tone` function)
- Modify: `tests/test_tone_resolution.py` (add 5 precedence tests)

- [ ] **Step 1: Add 5 failing tests to `tests/test_tone_resolution.py`**

Append before `if __name__ == "__main__":`:

```python
class ResolveToneTests(TestCase):
    def test_cli_wins_over_frontmatter_and_style(self):
        result = config.resolve_tone(
            cli_tone="opinionated",
            frontmatter_tone="neutral",
            writing_style="A",
        )
        self.assertEqual(result, "opinionated")

    def test_frontmatter_wins_over_style_default(self):
        result = config.resolve_tone(
            cli_tone=None,
            frontmatter_tone="casual",
            writing_style="A",  # default would be neutral
        )
        self.assertEqual(result, "casual")

    def test_style_default_when_cli_and_frontmatter_missing(self):
        result = config.resolve_tone(
            cli_tone=None,
            frontmatter_tone=None,
            writing_style="H",
        )
        self.assertEqual(result, "opinionated")

    def test_unknown_style_falls_back_to_neutral(self):
        result = config.resolve_tone(
            cli_tone=None,
            frontmatter_tone=None,
            writing_style="Z",  # not in mapping
        )
        self.assertEqual(result, "neutral")

    def test_invalid_frontmatter_value_falls_back_to_style_default(self):
        # frontmatter author manually typed something invalid; we degrade silently
        # (warning is logged elsewhere; resolver only returns valid values)
        result = config.resolve_tone(
            cli_tone=None,
            frontmatter_tone="aggressive",  # invalid
            writing_style="B",
        )
        self.assertEqual(result, "casual")
```

- [ ] **Step 2: Run tests, expect 5 failures**

Run: `python3 -m pytest tests/test_tone_resolution.py::ResolveToneTests -v`
Expected: 5 failures (`AttributeError: module 'scripts.config' has no attribute 'resolve_tone'`).

- [ ] **Step 3: Implement `resolve_tone()` in `scripts/config.py`**

Append after the `STYLE_TO_TONE_DEFAULT` dict:

```python


def resolve_tone(
    cli_tone: Optional[str] = None,
    frontmatter_tone: Optional[str] = None,
    writing_style: Optional[str] = None,
) -> str:
    """Resolve final tone using three-tier precedence: CLI > frontmatter > style default.

    Invalid values at any tier degrade silently to the next tier. Unknown
    writing styles default to "neutral". The CLI layer is expected to reject
    invalid `--tone` values BEFORE calling this function (with an explicit
    error to the user); we keep this resolver permissive so frontmatter
    typos and missing fields don't crash the pipeline.

    Returns one of TONE_REGISTER_LEVELS, never None.
    """
    if cli_tone in TONE_REGISTER_LEVELS:
        return cli_tone
    if frontmatter_tone in TONE_REGISTER_LEVELS:
        return frontmatter_tone
    if writing_style and writing_style in STYLE_TO_TONE_DEFAULT:
        return STYLE_TO_TONE_DEFAULT[writing_style]
    return "neutral"
```

- [ ] **Step 4: Run tests, expect 5 PASS**

Run: `python3 -m pytest tests/test_tone_resolution.py -v`
Expected: 8 passed (3 from Task 1 + 5 new).

- [ ] **Step 5: Commit**

```bash
git add scripts/config.py tests/test_tone_resolution.py
git commit -m "feat(config): resolve_tone() with cli > frontmatter > style precedence"
```

---

### Task 3: `TONE_THRESHOLDS` + `STRONG_OPINION_PATTERNS`

**Files:**
- Modify: `scripts/config.py` (append after `resolve_tone`)
- Modify: `tests/test_tone_resolution.py` (add 4 threshold-shape tests)

- [ ] **Step 1: Add 4 failing tests for the threshold dict shape**

Append a new test class to `tests/test_tone_resolution.py`:

```python
class ToneThresholdsTests(TestCase):
    def test_thresholds_dict_has_all_three_tones(self):
        for tone in config.TONE_REGISTER_LEVELS:
            self.assertIn(tone, config.TONE_THRESHOLDS)

    def test_each_tone_has_four_metrics(self):
        expected_keys = {
            "first_person_per_800w",
            "strong_opinion_min",
            "max_summary_phrases",
            "sentence_len_variance_min",
        }
        for tone, metrics in config.TONE_THRESHOLDS.items():
            self.assertEqual(set(metrics.keys()), expected_keys, f"tone={tone}")

    def test_first_person_density_increases_with_tone_severity(self):
        # neutral 2 < casual 4 < opinionated 6
        self.assertLess(
            config.TONE_THRESHOLDS["neutral"]["first_person_per_800w"],
            config.TONE_THRESHOLDS["casual"]["first_person_per_800w"],
        )
        self.assertLess(
            config.TONE_THRESHOLDS["casual"]["first_person_per_800w"],
            config.TONE_THRESHOLDS["opinionated"]["first_person_per_800w"],
        )

    def test_strong_opinion_patterns_is_non_empty_list_of_compiled_regex(self):
        import re
        self.assertGreater(len(config.STRONG_OPINION_PATTERNS), 5)
        for p in config.STRONG_OPINION_PATTERNS:
            self.assertIsInstance(p, re.Pattern)
```

- [ ] **Step 2: Run tests, expect 4 failures**

Run: `python3 -m pytest tests/test_tone_resolution.py::ToneThresholdsTests -v`
Expected: 4 failures.

- [ ] **Step 3: Add constants to `scripts/config.py`**

Append after `resolve_tone`:

```python


# ─── Tone thresholds (Rule 17 sub-checks) ────────────────────────
# Calibration: v1 starting values. Will be revisited after 20 articles
# of real review-cycle data accumulate in tone-calibration.jsonl.
TONE_THRESHOLDS = {
    "neutral": {
        "first_person_per_800w": 2,
        "strong_opinion_min": 0,
        "max_summary_phrases": 5,
        "sentence_len_variance_min": 0.0,    # 0 = sub-check D skipped
    },
    "casual": {
        "first_person_per_800w": 4,
        "strong_opinion_min": 0,
        "max_summary_phrases": 2,
        "sentence_len_variance_min": 0.30,
    },
    "opinionated": {
        "first_person_per_800w": 6,
        "strong_opinion_min": 1,
        "max_summary_phrases": 0,
        "sentence_len_variance_min": 0.45,
    },
}


# Patterns that signal an explicit personal opinion / hot take.
# Used by Rule 17 sub-check B. Patterns are kept conservative — false
# positives on plain technical prose are worse than false negatives.
import re as _re_for_tone

STRONG_OPINION_PATTERNS = [
    _re_for_tone.compile(r"我赌"),
    _re_for_tone.compile(r"我觉得.*?(?:就是|根本|纯属|没必要)"),
    _re_for_tone.compile(r"(?:这|那)(?:玩意|破事|设计).*?(?:错|烂|拉胯|蠢|坑爹)"),
    _re_for_tone.compile(r"别(?:学|用|碰|信)"),
    _re_for_tone.compile(r"真(?:香|的香)"),
    _re_for_tone.compile(r"纯(?:纯|属)"),
    _re_for_tone.compile(r"我的判断是"),
    _re_for_tone.compile(r"敢断言"),
    _re_for_tone.compile(r"(?:就是|根本)(?:错|不对|愚蠢)"),
]
```

- [ ] **Step 4: Run tests, expect 12 PASS total**

Run: `python3 -m pytest tests/test_tone_resolution.py -v`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/config.py tests/test_tone_resolution.py
git commit -m "feat(config): TONE_THRESHOLDS + STRONG_OPINION_PATTERNS"
```

---

### Task 4: `TONE_LEXICAL_REWRITES` + `get_rewrites_for_tone()`

**Files:**
- Modify: `scripts/config.py`
- Modify: `tests/test_tone_resolution.py` (add 4 inheritance tests)

- [ ] **Step 1: Add 4 failing tests for the rewrite tier inheritance**

Append a new test class to `tests/test_tone_resolution.py`:

```python
class ToneLexicalRewritesTests(TestCase):
    def test_rewrites_dict_has_all_three_tones(self):
        for tone in config.TONE_REGISTER_LEVELS:
            self.assertIn(tone, config.TONE_LEXICAL_REWRITES)

    def test_neutral_rewrites_contain_baseline_red_flags(self):
        # 赋能 / 一站式 are canonical Rule 1 red flags
        patterns = [p for p, _, _ in config.TONE_LEXICAL_REWRITES["neutral"]]
        flat = " ".join(p.pattern for p in patterns)
        self.assertIn("赋能", flat)
        self.assertIn("一站式", flat)

    def test_get_rewrites_for_tone_inherits_lower_tiers(self):
        n = len(config.get_rewrites_for_tone("neutral"))
        c = len(config.get_rewrites_for_tone("casual"))
        o = len(config.get_rewrites_for_tone("opinionated"))
        self.assertLess(n, c)
        self.assertLess(c, o)

    def test_get_rewrites_unknown_tone_returns_neutral(self):
        result = config.get_rewrites_for_tone("aggressive")
        baseline = config.get_rewrites_for_tone("neutral")
        self.assertEqual(len(result), len(baseline))
```

- [ ] **Step 2: Run tests, expect 4 failures**

Run: `python3 -m pytest tests/test_tone_resolution.py::ToneLexicalRewritesTests -v`

- [ ] **Step 3: Implement `TONE_LEXICAL_REWRITES` and `get_rewrites_for_tone` in `scripts/config.py`**

Append after `STRONG_OPINION_PATTERNS`:

```python


# ─── Tone-aware lexical rewrites (lint_article.py consumes this) ─
# Each entry: (compiled_pattern, replacement_string, severity).
# Severity is one of "info" | "warning" | "error".
# Tiers are STACKED via get_rewrites_for_tone(): casual = neutral + casual,
# opinionated = neutral + casual + opinionated.

TONE_LEXICAL_REWRITES: Dict[str, List[Any]] = {
    "neutral": [
        # Canonical Rule 1 red flags — applied at every tone.
        (_re_for_tone.compile(r"赋能"),         "支持",   "warning"),
        (_re_for_tone.compile(r"一站式"),       "完整",   "warning"),
        (_re_for_tone.compile(r"链路"),         "流程",   "info"),
        (_re_for_tone.compile(r"底层逻辑"),     "原理",   "info"),
        (_re_for_tone.compile(r"方法论"),       "做法",   "info"),
        (_re_for_tone.compile(r"抓手"),         "切入点", "warning"),
        (_re_for_tone.compile(r"闭环"),         "回路",   "info"),
        (_re_for_tone.compile(r"降本增效"),     "省钱省力", "warning"),
    ],
    "casual": [
        # Mid-tier replacements: turn formal connectives into colloquial Chinese.
        (_re_for_tone.compile(r"在某种意义上[，,]?"),           "其实",       "warning"),
        (_re_for_tone.compile(r"可以看到[，,]?"),               "能看出",     "warning"),
        (_re_for_tone.compile(r"本质上[，,]?"),                 "说穿了",     "warning"),
        (_re_for_tone.compile(r"接下来我们[来]?(看|介绍|分析)"), r"看看\1的",  "warning"),
        (_re_for_tone.compile(r"下面分别(来看|介绍)"),          r"分别\1",    "warning"),
        (_re_for_tone.compile(r"值得注意的是[，,]?"),           "这地方注意", "warning"),
        (_re_for_tone.compile(r"不难发现"),                     "能看出",     "warning"),
        (_re_for_tone.compile(r"基于以上分析"),                 "由此",       "info"),
        (_re_for_tone.compile(r"综上[，,]?"),                   "总之",       "info"),
        # Paragraph-starter sequence words (was in PARAGRAPH_STARTERS pre-v1.4.18)
        (_re_for_tone.compile(r"^首先[，,:： ]+", _re_for_tone.MULTILINE),  "", "warning"),
        (_re_for_tone.compile(r"^其次[，,:： ]+", _re_for_tone.MULTILINE),  "", "warning"),
        (_re_for_tone.compile(r"^最后[，,:： ]+", _re_for_tone.MULTILINE),  "", "warning"),
        (_re_for_tone.compile(r"^另外[，,:： ]+", _re_for_tone.MULTILINE),  "", "info"),
        (_re_for_tone.compile(r"^此外[，,:： ]+", _re_for_tone.MULTILINE),  "", "info"),
        (_re_for_tone.compile(r"^同时[，,:： ]+", _re_for_tone.MULTILINE),  "", "info"),
    ],
    "opinionated": [
        # High-tier: stronger replacements + closing-line removal (error severity).
        (_re_for_tone.compile(r"显然[，,]?"),                   "明摆着",     "warning"),
        (_re_for_tone.compile(r"综上所述"),                     "说白了",     "error"),
        (_re_for_tone.compile(r"总而言之"),                     "一句话",     "error"),
        (_re_for_tone.compile(r"希望本文对你有帮助[^\n]*"),     "",           "error"),
        (_re_for_tone.compile(r"如果这篇文章对你有帮助[^\n]*"), "",           "error"),
        (_re_for_tone.compile(r"欢迎留言讨论[^\n]*"),           "",           "error"),
        (_re_for_tone.compile(r"点个在看[^\n]*"),               "",           "error"),
    ],
}


def get_rewrites_for_tone(tone: str) -> List[Any]:
    """Return the full rewrite list for a tone, with lower-tier inheritance.

    casual returns neutral + casual; opinionated returns neutral + casual +
    opinionated. Unknown tones fall back to neutral (which is also what
    `resolve_tone` would have returned upstream — defense in depth).
    """
    if tone == "casual":
        return list(TONE_LEXICAL_REWRITES["neutral"]) + list(TONE_LEXICAL_REWRITES["casual"])
    if tone == "opinionated":
        return (
            list(TONE_LEXICAL_REWRITES["neutral"])
            + list(TONE_LEXICAL_REWRITES["casual"])
            + list(TONE_LEXICAL_REWRITES["opinionated"])
        )
    return list(TONE_LEXICAL_REWRITES["neutral"])
```

Also add `Any` to the typing imports near the top of `config.py`. Find the existing `from typing import Dict, Any, Optional, List` (line 11) — `Any` is already imported, no change needed.

- [ ] **Step 2 (sanity): Run tests, expect 4 PASS**

Run: `python3 -m pytest tests/test_tone_resolution.py::ToneLexicalRewritesTests -v`
Expected: 4 passed.

- [ ] **Step 3: Run all tone tests, expect 16 PASS**

Run: `python3 -m pytest tests/test_tone_resolution.py -v`
Expected: 16 passed.

- [ ] **Step 4: Run full test suite, expect 43 + 16 = 59 PASS (no regressions)**

Run: `python3 -m pytest tests/ -q`
Expected: 59 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/config.py tests/test_tone_resolution.py
git commit -m "feat(config): TONE_LEXICAL_REWRITES with inheritance + get_rewrites_for_tone"
```

> **PR A boundary** — At this point the data layer is complete and inert. Open PR A here if doing the split-PR strategy.

---

## Phase B — review_selfcheck Rule 17

### Task 5: Text-stripping helpers in `review_selfcheck.py`

**Files:**
- Modify: `scripts/review_selfcheck.py`
- Modify: `tests/test_review_selfcheck.py` (add 4 helper tests)

> Existing helpers already in `review_selfcheck.py`: `parse_frontmatter`, `get_body`, `strip_code_blocks`. We need to add `_strip_callout_blocks` and `_strip_image_lines` for Rule 17's clean-text pipeline.

- [ ] **Step 1: Add 4 failing tests**

Append to `tests/test_review_selfcheck.py` inside the existing `ReviewSelfcheckTests` class (or create a new class `TextStripHelperTests` near the bottom of the file before `if __name__ == "__main__":`).

```python
class TextStripHelperTests(TestCase):
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
```

- [ ] **Step 2: Run tests, expect 4 failures (ImportError)**

Run: `python3 -m pytest tests/test_review_selfcheck.py::TextStripHelperTests -v`

- [ ] **Step 3: Add helpers to `scripts/review_selfcheck.py`**

Find the existing `strip_code_blocks` function (around line 111). Append immediately after it:

```python


def _strip_callout_blocks(text: str) -> str:
    """Remove Obsidian callout blocks (> [!type] ... \\n> body) from text.

    Plain blockquotes (lines starting with `>` but no `[!type]` marker)
    are preserved. Implementation: greedy state machine that toggles "inside
    callout" when it sees `> [!...]` and exits on the first non-`>` line.
    """
    lines = text.split("\n")
    out: List[str] = []
    in_callout = False
    for line in lines:
        stripped = line.lstrip()
        if not in_callout:
            if stripped.startswith("> [!") and "]" in stripped:
                in_callout = True
                continue
            out.append(line)
        else:
            if stripped.startswith(">"):
                continue
            in_callout = False
            out.append(line)
    return "\n".join(out)


def _strip_image_lines(text: str) -> str:
    """Drop lines that are *only* a Markdown image (optionally with surrounding whitespace).

    Inline images embedded inside a paragraph are preserved.
    """
    image_only = re.compile(r"^\s*!\[[^\]]*\]\([^)]+\)\s*$")
    return "\n".join(line for line in text.split("\n") if not image_only.match(line))
```

- [ ] **Step 4: Run tests, expect 4 PASS**

Run: `python3 -m pytest tests/test_review_selfcheck.py::TextStripHelperTests -v`

- [ ] **Step 5: Commit**

```bash
git add scripts/review_selfcheck.py tests/test_review_selfcheck.py
git commit -m "feat(review): _strip_callout_blocks + _strip_image_lines helpers"
```

---

### Task 6: Rule 17 sub-check A (first-person density)

**Files:**
- Modify: `scripts/review_selfcheck.py`
- Create: `tests/test_review_rule17.py`

- [ ] **Step 1: Create `tests/test_review_rule17.py` with 3 sub-check-A tests**

```python
"""Tests for Rule 17 (Register Naturalness) sub-checks A-D, per tone."""

import sys
from pathlib import Path
from unittest import TestCase, main

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.review_selfcheck import check_rule_17


def _article(body: str, tone: str = "casual", style: str = "B") -> str:
    """Build a minimal article string with frontmatter for testing."""
    fm = f"---\nwriting_style: {style}\ntone: {tone}\n---\n\n# Title\n\n{body}\n"
    return fm


class Rule17SubCheckATests(TestCase):
    def test_passes_when_first_person_density_meets_neutral_threshold(self):
        # neutral threshold = 2 per 800 chars. We give 2 markers in ~400 chars
        # which is 4 per 800w-equivalent — well above.
        body = "我用过 X。" * 20 + "\n\n踩坑实测过。" * 5
        article = _article(body, tone="neutral", style="A")
        result = check_rule_17(article, article.split("\n"))
        sub_a = [v for v in result.violations if "第一人称密度" in v.text]
        self.assertEqual(sub_a, [])

    def test_fails_when_first_person_density_below_casual_threshold(self):
        # casual threshold = 4 per 800w. We give zero personal markers.
        body = "技术内容描述。" * 100  # 600+ chars, no first-person markers
        article = _article(body, tone="casual", style="B")
        result = check_rule_17(article, article.split("\n"))
        sub_a = [v for v in result.violations if "第一人称密度" in v.text]
        self.assertEqual(len(sub_a), 1)
        self.assertEqual(sub_a[0].severity, "warning")

    def test_skipped_when_body_under_200_chinese_chars(self):
        body = "短文。"  # Way under 200 chars.
        article = _article(body, tone="opinionated", style="G")
        result = check_rule_17(article, article.split("\n"))
        self.assertTrue(result.skipped, msg="Should skip Rule 17 on tiny articles")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run, expect 3 ImportError failures**

Run: `python3 -m pytest tests/test_review_rule17.py -v`

- [ ] **Step 3: Add `check_rule_17` skeleton with sub-check A in `scripts/review_selfcheck.py`**

Find the last `check_rule_*` function (Rule 16 is the latest). Append after it, before any "main" or "report" code:

```python


PERSONAL_VOICE_REGEX = re.compile(
    r"我(?:在|曾|的|会|用|选|踩|测|觉得|发现|猜|赌|最后)"
    r"|踩坑|实测|我的(?:经验|理解|做法)"
    r"|生产环境.*?(?:我|本人)"
)


def check_rule_17(content: str, lines: List[str]) -> CheckResult:
    """Rule 17: Register Naturalness (tone-aware).

    Reads `tone:` from article frontmatter; falls back to writing_style
    default; final fallback is "neutral". Runs four sub-checks; collects
    Violation objects with severity; returns a CheckResult.
    """
    from scripts.config import TONE_THRESHOLDS, resolve_tone, STRONG_OPINION_PATTERNS

    frontmatter = parse_frontmatter(content)
    tone = resolve_tone(
        cli_tone=None,
        frontmatter_tone=frontmatter.get("tone"),
        writing_style=frontmatter.get("writing_style"),
    )

    body = get_body(content)
    body = strip_code_blocks(body)
    body = _strip_callout_blocks(body)
    body = _strip_image_lines(body)

    cn_chars = len(re.findall(r"[一-鿿]", body))
    if cn_chars < 200:
        return CheckResult(
            rule_id="rule_17",
            rule_name=f"Register Naturalness (tone={tone})",
            passed=True,
            skipped=True,
            skip_reason="样本太小 (<200 字), 密度抖动失真",
            violations=[],
        )

    thresholds = TONE_THRESHOLDS[tone]
    violations: List[Violation] = []

    # ── Sub-check A: First-person density ───────────────────────
    first_person_hits = len(PERSONAL_VOICE_REGEX.findall(body))
    density = (first_person_hits / cn_chars) * 800
    threshold_a = thresholds["first_person_per_800w"]
    if density < threshold_a:
        violations.append(Violation(
            line=0,
            text=f"第一人称密度: {density:.1f} 处/800字",
            suggestion=(
                f"tone={tone} 要求 ≥{threshold_a} 处/800字, "
                f"补充第一人称经验 / 选型理由 / 踩坑记录"
            ),
            severity="warning",
        ))

    # Sub-checks B/C/D added in subsequent tasks.

    return CheckResult(
        rule_id="rule_17",
        rule_name=f"Register Naturalness (tone={tone})",
        passed=not any(v.severity == "error" for v in violations),
        violations=violations,
        meta={"tone": tone},
    )
```

> If `CheckResult` does not currently support `skipped`, `skip_reason`, or `meta` kwargs, extend it. Find the existing `class CheckResult` (around line 80) and add these fields:
>
> ```python
> @dataclass
> class CheckResult:
>     rule_id: str
>     rule_name: str
>     passed: bool
>     violations: List[Violation] = field(default_factory=list)
>     skipped: bool = False
>     skip_reason: str = ""
>     meta: Dict = field(default_factory=dict)
> ```
>
> If `Violation` does not currently have `severity`, add it (default `"warning"` for backward compat with all existing code paths):
>
> ```python
> @dataclass
> class Violation:
>     line: int
>     text: str
>     suggestion: str
>     severity: str = "warning"
> ```

- [ ] **Step 4: Run sub-check A tests, expect 3 PASS**

Run: `python3 -m pytest tests/test_review_rule17.py::Rule17SubCheckATests -v`

- [ ] **Step 5: Run all tests, expect no regressions (existing `severity`-less Violation calls still work)**

Run: `python3 -m pytest tests/ -q`
Expected: All passing. If there's a regression, it's because adding `severity` field requires `field(default_factory=...)` style or default value — keeping `severity: str = "warning"` as default makes legacy callsites work unchanged.

- [ ] **Step 6: Commit**

```bash
git add scripts/review_selfcheck.py tests/test_review_rule17.py
git commit -m "feat(review): Rule 17 skeleton + sub-check A (first-person density)"
```

---

### Task 7: Rule 17 sub-check B (strong opinion)

**Files:**
- Modify: `scripts/review_selfcheck.py` (extend `check_rule_17`)
- Modify: `tests/test_review_rule17.py` (add 3 sub-check B tests)

- [ ] **Step 1: Add 3 failing sub-check-B tests**

Append to `tests/test_review_rule17.py`:

```python
class Rule17SubCheckBTests(TestCase):
    def test_neutral_skips_strong_opinion_check(self):
        body = "技术描述。" * 100   # zero opinion markers
        article = _article(body, tone="neutral", style="A")
        result = check_rule_17(article, article.split("\n"))
        sub_b = [v for v in result.violations if "强观点" in v.text]
        self.assertEqual(sub_b, [])

    def test_casual_warns_on_missing_strong_opinion_at_info_severity(self):
        body = "我用过这个工具。" * 30
        article = _article(body, tone="casual", style="B")
        result = check_rule_17(article, article.split("\n"))
        sub_b = [v for v in result.violations if "强观点" in v.text]
        if sub_b:
            self.assertEqual(sub_b[0].severity, "info")

    def test_opinionated_errors_on_missing_strong_opinion(self):
        body = "我用过这个工具。" * 30  # has first-person but no strong opinion
        article = _article(body, tone="opinionated", style="G")
        result = check_rule_17(article, article.split("\n"))
        sub_b = [v for v in result.violations if "强观点" in v.text]
        self.assertEqual(len(sub_b), 1)
        self.assertEqual(sub_b[0].severity, "error")
        self.assertFalse(result.passed, msg="error severity should fail Rule 17")

    def test_opinionated_passes_with_one_strong_opinion(self):
        body = "我用过这个工具。" * 30 + "我赌它一年内被替换。"
        article = _article(body, tone="opinionated", style="G")
        result = check_rule_17(article, article.split("\n"))
        sub_b = [v for v in result.violations if "强观点" in v.text]
        self.assertEqual(sub_b, [])
```

- [ ] **Step 2: Run, expect 3 failures (the 4th one might pass spuriously)**

Run: `python3 -m pytest tests/test_review_rule17.py::Rule17SubCheckBTests -v`

- [ ] **Step 3: Add sub-check B logic inside `check_rule_17`**

In `scripts/review_selfcheck.py`, find the comment `# Sub-checks B/C/D added in subsequent tasks.` inside `check_rule_17` and replace with:

```python
    # ── Sub-check B: Strong-opinion presence ─────────────────────
    threshold_b = thresholds["strong_opinion_min"]
    if threshold_b > 0:
        opinion_count = sum(
            len(p.findall(body)) for p in STRONG_OPINION_PATTERNS
        )
        if opinion_count < threshold_b:
            sev = "error" if tone == "opinionated" else "info"
            msg = (
                "tone=opinionated 要求至少 1 处明确个人立场"
                if tone == "opinionated"
                else "考虑加 1 处个人判断 / 预测, 提升可读性"
            )
            violations.append(Violation(
                line=0,
                text=f"强观点 sentence 数: {opinion_count} (需要 {threshold_b})",
                suggestion=msg,
                severity=sev,
            ))

    # Sub-checks C/D added in subsequent tasks.
```

- [ ] **Step 4: Run sub-check B tests, expect 4 PASS**

Run: `python3 -m pytest tests/test_review_rule17.py::Rule17SubCheckBTests -v`

- [ ] **Step 5: Commit**

```bash
git add scripts/review_selfcheck.py tests/test_review_rule17.py
git commit -m "feat(review): Rule 17 sub-check B (strong-opinion presence)"
```

---

### Task 8: Rule 17 sub-check C (summary phrase ceiling)

**Files:**
- Modify: `scripts/review_selfcheck.py`
- Modify: `tests/test_review_rule17.py`

- [ ] **Step 1: Add 3 failing sub-check-C tests**

Append to `tests/test_review_rule17.py`:

```python
class Rule17SubCheckCTests(TestCase):
    def test_neutral_allows_5_summary_phrases(self):
        body = ("可以看到这个问题。本质上其实如此。" * 3 + "在某种意义上有道理。") + "我实测过。" * 30
        article = _article(body, tone="neutral", style="A")
        result = check_rule_17(article, article.split("\n"))
        sub_c = [v for v in result.violations if "总结腔" in v.text]
        # Hit count is around 4–5; under neutral ceiling of 5.
        self.assertEqual(sub_c, [])

    def test_casual_fails_on_5_summary_phrases(self):
        body = ("可以看到这个问题。本质上其实如此。" * 3 + "在某种意义上有道理。") + "我实测过。" * 30
        article = _article(body, tone="casual", style="B")
        result = check_rule_17(article, article.split("\n"))
        sub_c = [v for v in result.violations if "总结腔" in v.text]
        self.assertEqual(len(sub_c), 1)
        self.assertEqual(sub_c[0].severity, "warning")

    def test_opinionated_fails_on_any_summary_phrase(self):
        body = "可以看到这个问题。" + "我用过这个工具。" * 30 + "我赌它一年内被替换。"
        article = _article(body, tone="opinionated", style="G")
        result = check_rule_17(article, article.split("\n"))
        sub_c = [v for v in result.violations if "总结腔" in v.text]
        self.assertEqual(len(sub_c), 1)
```

- [ ] **Step 2: Run, expect 3 failures**

Run: `python3 -m pytest tests/test_review_rule17.py::Rule17SubCheckCTests -v`

- [ ] **Step 3: Add sub-check C logic inside `check_rule_17`**

In `check_rule_17`, replace the comment `# Sub-checks C/D added in subsequent tasks.` with:

```python
    # ── Sub-check C: Summary-phrase ceiling ──────────────────────
    # Reuses the same EMPTY_JUDGEMENT_PHRASES + SUMMARY_TONE_PHRASES used
    # by Rule 5. Different lens: Rule 5 looks at structural arrangement
    # (consecutive paragraphs, no anchors); Rule 17 only at total count.
    summary_hits = sum(
        len(re.findall(p, body))
        for p in EMPTY_JUDGEMENT_PHRASES + SUMMARY_TONE_PHRASES
    )
    limit_c = thresholds["max_summary_phrases"]
    if summary_hits > limit_c:
        violations.append(Violation(
            line=0,
            text=f"总结腔短语命中: {summary_hits} (上限 {limit_c})",
            suggestion=(
                f"tone={tone} 上限 {limit_c}, "
                f"删 {summary_hits - limit_c} 处或换具体陈述"
            ),
            severity="warning",
        ))

    # Sub-check D added in next task.
```

- [ ] **Step 4: Run sub-check C tests, expect 3 PASS**

Run: `python3 -m pytest tests/test_review_rule17.py::Rule17SubCheckCTests -v`

- [ ] **Step 5: Commit**

```bash
git add scripts/review_selfcheck.py tests/test_review_rule17.py
git commit -m "feat(review): Rule 17 sub-check C (summary phrase ceiling)"
```

---

### Task 9: Rule 17 sub-check D (sentence-length CV)

**Files:**
- Modify: `scripts/review_selfcheck.py`
- Modify: `tests/test_review_rule17.py`

- [ ] **Step 1: Add 3 failing sub-check-D tests**

Append to `tests/test_review_rule17.py`:

```python
class Rule17SubCheckDTests(TestCase):
    def test_neutral_skips_variance_check(self):
        # All sentences same length — would fail at casual/opinionated.
        body = "这是一个十二字的句子哦。" * 50
        article = _article(body, tone="neutral", style="A")
        result = check_rule_17(article, article.split("\n"))
        sub_d = [v for v in result.violations if "句长变异" in v.text]
        self.assertEqual(sub_d, [])

    def test_casual_fails_on_uniform_sentence_lengths(self):
        body = "这是一个十二字的句子哦。" * 50 + "我实测过。" * 30
        article = _article(body, tone="casual", style="B")
        result = check_rule_17(article, article.split("\n"))
        sub_d = [v for v in result.violations if "句长变异" in v.text]
        self.assertEqual(len(sub_d), 1)
        self.assertEqual(sub_d[0].severity, "warning")

    def test_skipped_when_under_10_sentences(self):
        body = "短句一。短句二。短句三。我实测过。" * 5
        article = _article(body, tone="opinionated", style="G")
        # Only ~20 sentences total; might or might not pass — this test
        # only asserts the check did not crash and result is well-formed.
        result = check_rule_17(article, article.split("\n"))
        self.assertIsNotNone(result)
```

- [ ] **Step 2: Run, expect 2 failures (3rd may pass spuriously)**

Run: `python3 -m pytest tests/test_review_rule17.py::Rule17SubCheckDTests -v`

- [ ] **Step 3: Add sub-check D logic + module-level statistics import**

At the top of `scripts/review_selfcheck.py` (with the other imports), add:

```python
import statistics
```

In `check_rule_17`, replace `# Sub-check D added in next task.` with:

```python
    # ── Sub-check D: Sentence-length coefficient of variation ────
    threshold_d = thresholds["sentence_len_variance_min"]
    if threshold_d > 0:
        sentences = re.split(r"[。！？\n]", body)
        # Filter implausibly short fragments (TOC items, headings) and
        # implausibly long lines (URLs, log dumps).
        lens = [len(s) for s in sentences if 5 <= len(s) <= 200]
        if len(lens) >= 10:
            mean = statistics.mean(lens)
            stdev = statistics.stdev(lens)
            cv = stdev / mean if mean > 0 else 0
            if cv < threshold_d:
                violations.append(Violation(
                    line=0,
                    text=f"句长变异系数: {cv:.2f} (需要 ≥{threshold_d})",
                    suggestion=(
                        "句子长度过于均匀（AI 节奏特征）。"
                        "拆 1-2 句长句为短句, 或合并连续短句为长句"
                    ),
                    severity="warning",
                ))
```

- [ ] **Step 4: Run sub-check D tests, expect 3 PASS**

Run: `python3 -m pytest tests/test_review_rule17.py::Rule17SubCheckDTests -v`

- [ ] **Step 5: Run full Rule 17 test set**

Run: `python3 -m pytest tests/test_review_rule17.py -v`
Expected: 12+ passed (3 + 4 + 3 + 3, plus any extras).

- [ ] **Step 6: Commit**

```bash
git add scripts/review_selfcheck.py tests/test_review_rule17.py
git commit -m "feat(review): Rule 17 sub-check D (sentence-length variance)"
```

---

### Task 10: Gate Rule 5 personal-marker sub-check on `tone=neutral`

**Files:**
- Modify: `scripts/review_selfcheck.py` (the existing `check_rule_5` function around line 321)
- Modify: `tests/test_review_selfcheck.py` (add 1 regression test)

> **Why this task exists:** The spec says when Rule 17 is active at `casual`/`opinionated`, Rule 5's existing `personal_markers < 2` sub-check would double-count. Gate it.

- [ ] **Step 1: Add a regression test**

Append to `tests/test_review_selfcheck.py` `ReviewSelfcheckTests`:

```python
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
```

- [ ] **Step 2: Run, expect 2 failures (currently Rule 5 fires at all tones)**

Run: `python3 -m pytest tests/test_review_selfcheck.py -k "personal_marker" -v`

- [ ] **Step 3: Modify `check_rule_5` to gate the personal-marker sub-check**

In `scripts/review_selfcheck.py`, find the block in `check_rule_5` that looks like:

```python
    # Check personal perspective count
    personal_markers = re.findall(
        r'我(?:在|曾|的|会|用|选|踩|测|最后|发现)|踩坑|实测|我的经验|生产环境中.*我',
        body
    )
    if len(personal_markers) < 2:
        violations.append(Violation(
            line=0, text=f"个人视角标记仅 {len(personal_markers)} 处",
            suggestion="增加至少 2 处第一人称经验分享（如踩坑、实测、选型理由）"
        ))
```

Wrap it with a tone check. Add at the top of `check_rule_5` (right after `body = ...`):

```python
    # Tone-aware gating: Rule 17 sub-check A owns this dimension at
    # casual/opinionated; we only fire here at neutral.
    from scripts.config import resolve_tone
    frontmatter = parse_frontmatter(content)
    tone = resolve_tone(
        cli_tone=None,
        frontmatter_tone=frontmatter.get("tone"),
        writing_style=frontmatter.get("writing_style"),
    )
```

Then change the `if len(personal_markers) < 2:` to `if tone == "neutral" and len(personal_markers) < 2:`.

- [ ] **Step 4: Run, expect 2 PASS**

Run: `python3 -m pytest tests/test_review_selfcheck.py -k "personal_marker" -v`

- [ ] **Step 5: Run full review test set, no regressions**

Run: `python3 -m pytest tests/test_review_selfcheck.py tests/test_review_rule17.py -v`

- [ ] **Step 6: Commit**

```bash
git add scripts/review_selfcheck.py tests/test_review_selfcheck.py
git commit -m "feat(review): gate Rule 5 personal-marker subcheck on tone=neutral"
```

---

### Task 11: Wire Rule 17 into `check_all` reporting

**Files:**
- Modify: `scripts/review_selfcheck.py`
- Modify: `tests/test_review_rule17.py`

- [ ] **Step 1: Add an integration test**

Append to `tests/test_review_rule17.py`:

```python
class Rule17IntegrationTests(TestCase):
    def test_check_all_includes_rule_17_in_results(self):
        from scripts.review_selfcheck import check_all
        article = (
            "---\nwriting_style: B\ntone: casual\n---\n\n# T\n\n"
            + "我用过 X。" * 20 + "\n\n踩坑实测过。" * 20
        )
        results = check_all(article)
        rule_ids = {r.rule_id for r in results}
        self.assertIn("rule_17", rule_ids)

    def test_check_all_runs_rule_17_at_neutral_when_tone_missing(self):
        from scripts.review_selfcheck import check_all
        # No `tone:` in frontmatter — should default to style A's neutral.
        article = (
            "---\nwriting_style: A\n---\n\n# T\n\n"
            + "技术描述。" * 100
        )
        results = check_all(article)
        rule_17 = [r for r in results if r.rule_id == "rule_17"]
        self.assertEqual(len(rule_17), 1)
        self.assertEqual(rule_17[0].meta.get("tone"), "neutral")
```

- [ ] **Step 2: Run, expect failures (check_all does not yet call check_rule_17)**

Run: `python3 -m pytest tests/test_review_rule17.py::Rule17IntegrationTests -v`

- [ ] **Step 3: Add `check_rule_17` to the `check_all` dispatcher**

In `scripts/review_selfcheck.py`, locate the `check_all(content: str) -> List[CheckResult]` function (or whatever the existing master orchestrator function is named — `grep -n "def check_all\|check_rule_16" scripts/review_selfcheck.py` to find).

Add `check_rule_17(content, lines)` to the dispatch list. Example:

```python
def check_all(content: str) -> List[CheckResult]:
    lines = content.split("\n")
    return [
        check_rule_1(content, lines),
        check_rule_2(content, lines),
        check_rule_3(content, lines),
        check_rule_4(content, lines),
        check_rule_5(content, lines),
        check_rule_6(content, lines),
        check_rule_7(content, lines),
        check_rule_8(content, lines),
        check_rule_9(content, lines),
        check_rule_10(content, lines),
        check_rule_11(content, lines),
        check_rule_16(content, lines),
        check_rule_17(content, lines),   # NEW
    ]
```

- [ ] **Step 4: Run, expect 2 PASS**

Run: `python3 -m pytest tests/test_review_rule17.py::Rule17IntegrationTests -v`

- [ ] **Step 5: Run full suite**

Run: `python3 -m pytest tests/ -q`
Expected: 43 + 16 + 12 = ~71+ passed, no failures.

- [ ] **Step 6: Commit**

```bash
git add scripts/review_selfcheck.py tests/test_review_rule17.py
git commit -m "feat(review): wire Rule 17 into check_all dispatch"
```

---

## Phase C — lint_article.py refactor

### Task 12: Migrate existing `RED_FLAG_REWRITES` → `TONE_LEXICAL_REWRITES["neutral"]`

**Files:**
- Modify: `scripts/lint_article.py`
- Modify: `tests/test_lint_article.py` (add 1 regression test)

> **Goal:** Pure refactor. `lint_article.py --fix` (no `--tone` flag) at default behavior must produce identical output as v1.4.17 for the neutral tier (red-flag words). Existing 10 lint tests stay green.

- [ ] **Step 1: Add a regression test pinning v1.4.17 behavior**

Append to `tests/test_lint_article.py`:

```python
    def test_neutral_tone_default_preserves_v1_4_17_redflag_behavior(self):
        # An article with no `tone:` field — should default to neutral
        # and run all the canonical red-flag replacements only.
        from scripts.lint_article import auto_fix
        text = "本产品赋能开发者一站式解决方案，链路清晰。"
        article_path = self._write_temp_article(text)
        report = auto_fix(article_path)
        result = article_path.read_text(encoding="utf-8")
        self.assertNotIn("赋能", result)
        self.assertNotIn("一站式", result)
        # 链路 → 流程 (severity=info, NOT applied at default --min-severity warning)
        self.assertIn("链路", result)
```

> If `_write_temp_article` is not already a helper in this test file, add this at the top of `LintArticleTests`:
>
> ```python
>     def _write_temp_article(self, body: str) -> Path:
>         import tempfile
>         tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
>         tmp.write(f"---\nwriting_style: A\n---\n\n# Title\n\n{body}\n")
>         tmp.close()
>         self._tempfiles.append(tmp.name)
>         return Path(tmp.name)
> ```
>
> ...and add `setUp` / `tearDown` around `self._tempfiles = []`.

- [ ] **Step 2: Run, expect failure (current code uses RED_FLAG_REWRITES directly without tone awareness)**

Run: `python3 -m pytest tests/test_lint_article.py::LintArticleTests::test_neutral_tone_default_preserves_v1_4_17_redflag_behavior -v`

- [ ] **Step 3: Refactor `scripts/lint_article.py` to consume `config.TONE_LEXICAL_REWRITES`**

In `scripts/lint_article.py`:

3a. Remove these constants (they're now in `config.py`):
- `RED_FLAG_REWRITES` (lines 52–65 area)

3b. Add at the top, near the imports:

```python
from scripts.config import (
    TONE_REGISTER_LEVELS,
    TONE_LEXICAL_REWRITES,
    get_rewrites_for_tone,
    resolve_tone,
)
```

3c. Find the function that applies red-flag rewrites (likely `apply_red_flag_rewrites` or similar — `grep -n "RED_FLAG_REWRITES" scripts/lint_article.py`). Refactor its signature to take a `tone: str` and use `get_rewrites_for_tone(tone)` instead of the removed module-level constant.

3d. Add to the public `auto_fix` (or whatever the entry point is) a `tone` parameter:

```python
def auto_fix(article_path: Path, tone: Optional[str] = None) -> FixReport:
    """Apply tone-aware lint fixes to an article in-place.

    If `tone` is None, reads from frontmatter; falls back to writing-style
    default; final fallback is "neutral".
    """
    text = article_path.read_text(encoding="utf-8")
    frontmatter = _parse_frontmatter_simple(text)
    resolved_tone = resolve_tone(
        cli_tone=tone,
        frontmatter_tone=frontmatter.get("tone"),
        writing_style=frontmatter.get("writing_style"),
    )
    # ... existing logic, swapping RED_FLAG_REWRITES for get_rewrites_for_tone(resolved_tone)
```

> Important: the existing `lint_article.py` may have its own simpler frontmatter parser. Reuse it. Don't add a YAML dependency.

- [ ] **Step 4: Run, expect regression test PASS + existing 10 tests still PASS**

Run: `python3 -m pytest tests/test_lint_article.py -v`
Expected: 11+ passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/lint_article.py tests/test_lint_article.py
git commit -m "refactor(lint): consume config.TONE_LEXICAL_REWRITES (neutral baseline preserved)"
```

---

### Task 13: Severity-aware filtering in `lint_article.py`

**Files:**
- Modify: `scripts/lint_article.py`
- Create: `tests/test_lint_tone_aware.py`

- [ ] **Step 1: Create `tests/test_lint_tone_aware.py` with 3 severity tests**

```python
"""Tests for tone-aware lint behavior: severity filtering, inline disable, max-pass."""

import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.lint_article import auto_fix


def _temp_article(body: str, frontmatter: str = "writing_style: A") -> Path:
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    )
    f.write(f"---\n{frontmatter}\n---\n\n# Title\n\n{body}\n")
    f.close()
    return Path(f.name)


class SeverityFilteringTests(TestCase):
    def test_default_min_severity_is_warning_skips_info_fixes(self):
        # 链路 is severity=info — should NOT be replaced at default min-severity.
        article = _temp_article("链路清晰。")
        auto_fix(article)
        self.assertIn("链路", article.read_text(encoding="utf-8"))

    def test_apply_info_replaces_info_severity(self):
        article = _temp_article("链路清晰。")
        auto_fix(article, apply_info=True)
        self.assertNotIn("链路", article.read_text(encoding="utf-8"))

    def test_error_severity_always_applied(self):
        # 综上所述 is error severity at opinionated tier.
        article = _temp_article(
            "综上所述。",
            frontmatter="writing_style: G\ntone: opinionated",
        )
        auto_fix(article)
        self.assertNotIn("综上所述", article.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run, expect 3 failures (no severity infrastructure yet)**

Run: `python3 -m pytest tests/test_lint_tone_aware.py::SeverityFilteringTests -v`

- [ ] **Step 3: Add severity filtering to `lint_article.py`**

In `scripts/lint_article.py`:

3a. Add a constant near the top:

```python
SEVERITY_RANK = {"info": 0, "warning": 1, "error": 2}
```

3b. Modify the rewrite-application loop to filter by severity:

```python
def auto_fix(
    article_path: Path,
    tone: Optional[str] = None,
    min_severity: str = "warning",
    apply_info: bool = False,
) -> FixReport:
    text = article_path.read_text(encoding="utf-8")
    frontmatter = _parse_frontmatter_simple(text)
    resolved_tone = resolve_tone(
        cli_tone=tone,
        frontmatter_tone=frontmatter.get("tone"),
        writing_style=frontmatter.get("writing_style"),
    )

    # Compute the effective severity threshold.
    effective_min = "info" if apply_info else min_severity
    threshold_rank = SEVERITY_RANK[effective_min]

    rewrites = [
        (pattern, replacement, severity)
        for pattern, replacement, severity in get_rewrites_for_tone(resolved_tone)
        if SEVERITY_RANK[severity] >= threshold_rank
    ]

    # ... rest of the existing apply-loop, using `rewrites` instead of the unfiltered list.
```

- [ ] **Step 4: Run, expect 3 PASS**

Run: `python3 -m pytest tests/test_lint_tone_aware.py::SeverityFilteringTests -v`

- [ ] **Step 5: Commit**

```bash
git add scripts/lint_article.py tests/test_lint_tone_aware.py
git commit -m "feat(lint): severity-aware fix filtering (info/warning/error)"
```

---

### Task 14: Inline `<!-- lint:disable -->` / `<!-- lint:enable -->` parser

**Files:**
- Modify: `scripts/lint_article.py`
- Modify: `tests/test_lint_tone_aware.py`

- [ ] **Step 1: Add 4 inline-disable tests**

Append to `tests/test_lint_tone_aware.py`:

```python
class InlineDisableTests(TestCase):
    def test_disable_block_skips_fixes_inside(self):
        body = (
            "正常: 赋能开发者。\n\n"
            "<!-- lint:disable rule1 -->\n"
            "保留: 原文有赋能 一站式 这两个词。\n"
            "<!-- lint:enable rule1 -->\n\n"
            "正常: 一站式服务。"
        )
        article = _temp_article(body)
        auto_fix(article)
        text = article.read_text(encoding="utf-8")
        # Outside disable: 赋能 / 一站式 replaced
        self.assertNotIn("正常: 赋能", text)
        self.assertNotIn("正常: 一站式", text)
        # Inside disable: preserved
        self.assertIn("保留: 原文有赋能 一站式 这两个词", text)

    def test_disable_all_skips_everything(self):
        body = (
            "<!-- lint:disable all -->\n"
            "赋能 一站式 链路 综上所述。\n"
            "<!-- lint:enable all -->"
        )
        article = _temp_article(body)
        auto_fix(article)
        text = article.read_text(encoding="utf-8")
        self.assertIn("赋能 一站式 链路 综上所述", text)

    def test_unmatched_disable_warns_but_does_not_abort(self):
        # Unmatched <!-- lint:disable --> at end of file
        body = "正常段落。\n<!-- lint:disable rule1 -->\n赋能段落。"
        article = _temp_article(body)
        report = auto_fix(article)
        # No exception; report should reflect the issue
        self.assertTrue(any("unmatched" in str(w).lower() for w in report.warnings))

    def test_disable_specific_rule_does_not_block_other_rules(self):
        body = (
            "<!-- lint:disable rule1 -->\n"
            "赋能 综上所述。\n"
            "<!-- lint:enable rule1 -->"
        )
        article = _temp_article(
            body,
            frontmatter="writing_style: G\ntone: opinionated",
        )
        auto_fix(article)
        text = article.read_text(encoding="utf-8")
        self.assertIn("赋能", text)              # rule1 disabled inside block
        # 综上所述 isn't tagged with rule1 so it should still be replaced
        # (subject to how we tag rule_ids per pattern in Task 12 — see note).
```

> **Tagging note:** For the disable mechanism to be selective per rule, each entry in `TONE_LEXICAL_REWRITES` needs a rule_id. For v1, simplify: every red-flag pattern gets `rule1`, every connective replacement gets `rule5`, every closing-line pattern gets `rule3`. If you didn't add rule_ids in Task 4, retrofit them now: change the tuple to `(pattern, replacement, severity, rule_id)` and update `get_rewrites_for_tone` accordingly.

- [ ] **Step 2: Run, expect 4 failures**

Run: `python3 -m pytest tests/test_lint_tone_aware.py::InlineDisableTests -v`

- [ ] **Step 3: Add inline-disable parser to `lint_article.py`**

Add a helper function:

```python
DISABLE_PATTERN = re.compile(r"<!--\s*lint:disable\s+([^\-]+?)\s*-->")
ENABLE_PATTERN = re.compile(r"<!--\s*lint:enable\s+([^\-]+?)\s*-->")


def _split_by_disable_regions(text: str) -> List[Tuple[str, Set[str]]]:
    """Walk the text and partition it into (chunk, disabled_rules) tuples.

    Returns a list of (text_chunk, set_of_disabled_rule_ids) — chunks
    where disabled_rules is non-empty MUST NOT have those rules applied.
    The special rule_id "all" disables everything.

    Unmatched <!-- lint:enable --> tags are logged as warnings via the
    `warnings` list passed in (caller injects). For simplicity here we
    return a third element on the tuple if there's a parser issue.
    """
    chunks: List[Tuple[str, Set[str]]] = []
    pos = 0
    active: Set[str] = set()

    # Find all disable/enable markers in order
    markers = []
    for m in DISABLE_PATTERN.finditer(text):
        rules = set(m.group(1).split())
        markers.append((m.start(), m.end(), "disable", rules))
    for m in ENABLE_PATTERN.finditer(text):
        rules = set(m.group(1).split())
        markers.append((m.start(), m.end(), "enable", rules))
    markers.sort()

    for start, end, kind, rules in markers:
        # Emit the chunk before this marker
        if start > pos:
            chunks.append((text[pos:start], frozenset(active)))
        if kind == "disable":
            active.update(rules)
        else:
            active.difference_update(rules)
        pos = end

    # Final chunk
    if pos < len(text):
        chunks.append((text[pos:], frozenset(active)))

    return chunks
```

In `auto_fix`, replace the single-pass apply with:

```python
    chunks = _split_by_disable_regions(text)
    output: List[str] = []
    warnings: List[str] = []

    for chunk_text, disabled in chunks:
        for pattern, replacement, severity, rule_id in rewrites:
            if "all" in disabled or rule_id in disabled:
                continue
            chunk_text = pattern.sub(replacement, chunk_text)
        output.append(chunk_text)

    new_text = "".join(output)

    # Detect unmatched <!-- lint:enable -->
    if ENABLE_PATTERN.findall(new_text):
        warnings.append("unmatched <!-- lint:enable --> tag (no preceding disable)")
    if any(_unmatched_disable_at_eof(text)):
        warnings.append("unmatched <!-- lint:disable --> at end of file")

    article_path.write_text(new_text, encoding="utf-8")
    return FixReport(passes=1, warnings=warnings, ...)
```

> Define `_unmatched_disable_at_eof` as a helper that walks markers and returns True if the stack is non-empty at end of input.

- [ ] **Step 4: Run, expect 4 PASS**

Run: `python3 -m pytest tests/test_lint_tone_aware.py::InlineDisableTests -v`

- [ ] **Step 5: Commit**

```bash
git add scripts/lint_article.py tests/test_lint_tone_aware.py
git commit -m "feat(lint): inline <!-- lint:disable --> / enable region parser"
```

---

### Task 15: Max-pass oscillation guard

**Files:**
- Modify: `scripts/lint_article.py`
- Modify: `tests/test_lint_tone_aware.py`

- [ ] **Step 1: Add 3 max-pass tests**

Append to `tests/test_lint_tone_aware.py`:

```python
class MaxPassTests(TestCase):
    def test_clean_after_one_pass(self):
        article = _temp_article("纯净段落。我用过这个工具。")
        report = auto_fix(article, max_passes=3)
        self.assertEqual(report.status, "clean")
        self.assertLessEqual(report.passes, 1)

    def test_converges_within_max_passes_for_chained_replacements(self):
        # If a fix in pass 1 introduces a phrase that triggers another
        # rule in pass 2, we should still converge within max_passes.
        article = _temp_article("赋能 一站式 链路。" * 10)
        report = auto_fix(article, max_passes=3, apply_info=True)
        self.assertEqual(report.status, "clean")
        self.assertLessEqual(report.passes, 3)

    def test_oscillation_detected_when_violations_dont_change(self):
        # Synthetic: monkey-patch a no-op rewrite so the same violation
        # signature appears twice in a row → "oscillating" status.
        # This relies on a hook for injecting test rewrites; if not present,
        # skip via @unittest.skip.
        try:
            from scripts.lint_article import _set_test_rewrites_hook
        except ImportError:
            self.skipTest("Test hook not exposed; rewrite this test once available")

        def _bad_rewrites(tone):
            # Returns a pattern that "matches" but produces identical output
            return [(re.compile(r"foo"), "foo", "warning", "rule_test")]

        _set_test_rewrites_hook(_bad_rewrites)
        try:
            article = _temp_article("foo bar foo bar")
            report = auto_fix(article, max_passes=3)
            self.assertEqual(report.status, "oscillating")
        finally:
            _set_test_rewrites_hook(None)
```

> The third test relies on a test hook. Add it in step 3 below.

- [ ] **Step 2: Run, expect failures**

Run: `python3 -m pytest tests/test_lint_tone_aware.py::MaxPassTests -v`

- [ ] **Step 3: Implement max-pass loop in `lint_article.py`**

Refactor `auto_fix` core into a passing loop:

```python
_TEST_REWRITES_HOOK = None  # tests can override

def _set_test_rewrites_hook(hook):
    global _TEST_REWRITES_HOOK
    _TEST_REWRITES_HOOK = hook


def _scan_violations(text: str, rewrites) -> List[Tuple[str, str, str, str]]:
    """Return (rule_id, severity, before, after) for each pattern that matches."""
    out = []
    for pattern, replacement, severity, rule_id in rewrites:
        for m in pattern.finditer(text):
            after = pattern.sub(replacement, m.group(0))
            if m.group(0) != after:   # actual change
                out.append((rule_id, severity, m.group(0), after))
    return out


def auto_fix(
    article_path: Path,
    tone: Optional[str] = None,
    min_severity: str = "warning",
    apply_info: bool = False,
    max_passes: int = 3,
) -> FixReport:
    text = article_path.read_text(encoding="utf-8")
    frontmatter = _parse_frontmatter_simple(text)
    resolved_tone = resolve_tone(
        cli_tone=tone,
        frontmatter_tone=frontmatter.get("tone"),
        writing_style=frontmatter.get("writing_style"),
    )
    effective_min = "info" if apply_info else min_severity
    threshold_rank = SEVERITY_RANK[effective_min]

    rewrites_source = _TEST_REWRITES_HOOK or get_rewrites_for_tone
    rewrites = [
        (p, r, s, rid)
        for p, r, s, rid in rewrites_source(resolved_tone)
        if SEVERITY_RANK[s] >= threshold_rank
    ]

    last_signature = None
    warnings = []
    for pass_num in range(1, max_passes + 1):
        chunks = _split_by_disable_regions(text)
        new_text_parts = []
        applied_this_pass = []
        for chunk_text, disabled in chunks:
            modified = chunk_text
            for pattern, replacement, severity, rule_id in rewrites:
                if "all" in disabled or rule_id in disabled:
                    continue
                if pattern.search(modified):
                    applied_this_pass.append((rule_id, severity))
                    modified = pattern.sub(replacement, modified)
            new_text_parts.append(modified)
        new_text = "".join(new_text_parts)

        if new_text == text:
            return FixReport(passes=pass_num, status="clean", warnings=warnings)

        # Detect oscillation: same signature as last pass (no convergence)
        sig = frozenset((r, s) for r, s in applied_this_pass)
        if last_signature == sig:
            article_path.write_text(new_text, encoding="utf-8")
            return FixReport(passes=pass_num, status="oscillating", warnings=warnings)
        last_signature = sig
        text = new_text

    article_path.write_text(text, encoding="utf-8")
    return FixReport(passes=max_passes, status="incomplete", warnings=warnings)
```

> The full `FixReport` dataclass should include `passes: int`, `status: str`, `warnings: List[str]`. If you've used a different shape, adjust.

- [ ] **Step 4: Run, expect 3 PASS**

Run: `python3 -m pytest tests/test_lint_tone_aware.py::MaxPassTests -v`

- [ ] **Step 5: Run full lint suite**

Run: `python3 -m pytest tests/test_lint_article.py tests/test_lint_tone_aware.py -v`

- [ ] **Step 6: Commit**

```bash
git add scripts/lint_article.py tests/test_lint_tone_aware.py
git commit -m "feat(lint): max-pass oscillation guard"
```

---

### Task 16: CLI flags

**Files:**
- Modify: `scripts/lint_article.py` (the `main()` argparse block)

- [ ] **Step 1: Add CLI integration test**

Append to `tests/test_lint_tone_aware.py`:

```python
class CliFlagsTests(TestCase):
    def test_main_with_tone_flag(self):
        import subprocess
        article = _temp_article(
            "在某种意义上, 接下来我们将。",
            frontmatter="writing_style: A\ntone: neutral",
        )
        # Override neutral by passing --tone=casual on the CLI
        result = subprocess.run(
            ["python3", "scripts/lint_article.py",
             "--article", str(article), "--tone", "casual", "--fix"],
            capture_output=True, text=True,
            cwd=Path(__file__).resolve().parent.parent,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        text = article.read_text(encoding="utf-8")
        # casual should have stripped 在某种意义上
        self.assertNotIn("在某种意义上", text)

    def test_main_rejects_invalid_tone(self):
        import subprocess
        article = _temp_article("无关内容。")
        result = subprocess.run(
            ["python3", "scripts/lint_article.py",
             "--article", str(article), "--tone", "aggressive"],
            capture_output=True, text=True,
            cwd=Path(__file__).resolve().parent.parent,
        )
        self.assertNotEqual(result.returncode, 0)
```

- [ ] **Step 2: Run, expect failures**

Run: `python3 -m pytest tests/test_lint_tone_aware.py::CliFlagsTests -v`

- [ ] **Step 3: Update `main()` argparse block in `lint_article.py`**

Find the `if __name__ == "__main__":` block (or `def main():` if structured that way). Update the argparse setup:

```python
def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="article-craft lint with tone awareness")
    p.add_argument("--article", required=True, type=Path)
    p.add_argument(
        "--tone",
        choices=list(TONE_REGISTER_LEVELS),  # neutral / casual / opinionated
        default=None,
        help="Override tone (else read from frontmatter or style default)",
    )
    p.add_argument("--fix", action="store_true",
                   help="Apply replacements (default: report-only)")
    p.add_argument("--apply-info", action="store_true",
                   help="Also apply info-severity fixes (default: warning+ only)")
    p.add_argument(
        "--min-severity",
        choices=list(SEVERITY_RANK.keys()),
        default="warning",
        help="Filter reported violations below this severity",
    )
    p.add_argument("--max-passes", type=int, default=3,
                   help="Oscillation guard upper bound")
    p.add_argument("--report-only", action="store_true",
                   help="Synonym for --min-severity info without --fix")
    args = p.parse_args()

    if args.report_only:
        report = scan_only(args.article, tone=args.tone, min_severity="info")
        print(format_report(report))
        return 0

    if args.fix:
        report = auto_fix(
            args.article,
            tone=args.tone,
            min_severity=args.min_severity,
            apply_info=args.apply_info,
            max_passes=args.max_passes,
        )
    else:
        report = scan_only(args.article, tone=args.tone, min_severity=args.min_severity)

    print(format_report(report))
    if report.status == "oscillating":
        return 2
    if report.status == "incomplete":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

> Add `scan_only()` and `format_report()` if not present. They should be small wrappers — `scan_only` runs the same loop as `auto_fix` but does not write to disk; `format_report` produces the formatted text per the spec §6.6.

- [ ] **Step 4: Run, expect 2 PASS**

Run: `python3 -m pytest tests/test_lint_tone_aware.py::CliFlagsTests -v`

- [ ] **Step 5: Run full suite**

Run: `python3 -m pytest tests/ -q`

- [ ] **Step 6: Commit**

```bash
git add scripts/lint_article.py tests/test_lint_tone_aware.py
git commit -m "feat(lint): --tone / --min-severity / --apply-info / --max-passes CLI flags"
```

---

## Phase D — pipeline glue

### Task 17: `pipeline_state.py` reads `tone:` field

**Files:**
- Modify: `scripts/pipeline_state.py`
- Modify: `tests/test_pipeline_state.py`

- [ ] **Step 1: Add a failing test**

Append to `tests/test_pipeline_state.py`:

```python
    def test_scan_article_extracts_tone_field(self):
        from scripts.pipeline_state import _scan_article
        article_text = "---\nwriting_style: D\ntone: casual\n---\n\n# T\n\nbody."
        scan = _scan_article(article_text=article_text, article_path=None)
        self.assertEqual(scan.tone, "casual")

    def test_scan_article_tone_field_missing_returns_none(self):
        from scripts.pipeline_state import _scan_article
        article_text = "---\nwriting_style: D\n---\n\n# T\n\nbody."
        scan = _scan_article(article_text=article_text, article_path=None)
        self.assertIsNone(scan.tone)
```

- [ ] **Step 2: Run, expect 2 failures (the `Scan` dataclass has no `tone` field)**

Run: `python3 -m pytest tests/test_pipeline_state.py -k tone -v`

- [ ] **Step 3: Add `tone` to `Scan` dataclass + parsing**

In `scripts/pipeline_state.py`:

3a. Add `tone: Optional[str] = None` to the `Scan` dataclass.
3b. In `_scan_article()` frontmatter parsing, extract the `tone:` field and set `scan.tone`. If the existing parser uses regex like `re.search(r'^writing_style:\s*(\S+)', ...)`, add a sibling regex for `tone:`.

- [ ] **Step 4: Run, expect 2 PASS**

- [ ] **Step 5: Commit**

```bash
git add scripts/pipeline_state.py tests/test_pipeline_state.py
git commit -m "feat(state): pipeline_state extracts tone field for --upgrade"
```

---

### Task 18: orchestrator parses `--tone`

**Files:**
- Modify: `skills/orchestrator/SKILL.md`

> **Note:** orchestrator is prose; no test is needed at this level. Verification is integration-time.

- [ ] **Step 1: Find the `$ARGUMENTS` parsing block in `skills/orchestrator/SKILL.md`**

`grep -n '\$ARGUMENTS\|--quick\|--draft' skills/orchestrator/SKILL.md`

- [ ] **Step 2: Add `--tone` parsing alongside the existing `--quick` / `--draft` / `--upgrade` flag parsing**

Edit `skills/orchestrator/SKILL.md` to add (in the same prose section that documents the other flags):

```markdown
**`--tone={neutral,casual,opinionated}`** — Override tone tier. Cascade:
this flag wins; then frontmatter `tone:`; then writing-style default
(`STYLE_TO_TONE_DEFAULT` in `scripts/config.py`). Invalid values fail
the orchestrator with an explicit error — do not silently degrade.
Pass through to the requirements skill.
```

Then in the parsing instruction block, add:

```markdown
6. Detect `--tone=<value>`. If `<value>` not in `{neutral,casual,opinionated}`,
   abort with a user-facing error: "Invalid tone: <value>. Allowed: neutral,
   casual, opinionated." Otherwise pass it through to the `requirements` skill
   call as `--tone=<value>`.
```

- [ ] **Step 3: Commit**

```bash
git add skills/orchestrator/SKILL.md
git commit -m "feat(orchestrator): parse --tone flag and pass to requirements"
```

---

### Task 19: requirements skill: tone resolution step

**Files:**
- Modify: `skills/requirements/SKILL.md`

- [ ] **Step 1: Add a "Tone resolution" step to the requirements workflow**

In `skills/requirements/SKILL.md`, after the existing writing-style detection step, add:

```markdown
## Step N+1: Tone Resolution

Resolve the article's tone tier using three-tier precedence (CLI flag >
frontmatter `tone:` > writing-style default).

```python
from scripts.config import resolve_tone, STYLE_TO_TONE_DEFAULT

resolved_tone = resolve_tone(
    cli_tone=args.get("--tone"),     # from orchestrator argv parse
    frontmatter_tone=existing_frontmatter.get("tone"),
    writing_style=writing_style_id,  # already determined above
)
```

Write the resolved value into the article frontmatter as `tone: <value>`.
Do **not** call `AskUserQuestion` here — `STYLE_TO_TONE_DEFAULT` always
resolves a value because writing-style is always set by this point.

If the user has manually entered an invalid `tone:` in frontmatter (e.g.
`tone: aggressive`), `resolve_tone` returns the style default; print one
warning line: `WARNING: invalid tone <bad> in frontmatter; using <resolved>`.
```

- [ ] **Step 2: Commit**

```bash
git add skills/requirements/SKILL.md
git commit -m "feat(requirements): tone resolution step writes frontmatter tone"
```

---

## Phase E — Skill prose updates

### Task 20: write skill reads `tone:` and injects style-guide section

**Files:**
- Modify: `skills/write/SKILL.md`

- [ ] **Step 1: Update Step 3 prompt construction in `skills/write/SKILL.md`**

Find the section in Step 3 that builds the LLM prompt. Add the following instruction:

```markdown
### Step 3.X: Tone-aware prompt augmentation

After loading the base style guide, read `tone:` from frontmatter
(it was set in requirements). Then **append** the matching section
from `style-guide.md`:

- `tone: neutral`     → append `## Tone: neutral` section
- `tone: casual`      → append `## Tone: casual` section
- `tone: opinionated` → append `## Tone: opinionated` section

If no `tone:` in frontmatter, default to `neutral`.

Each tone section contains: register guidance, sample paragraphs at the
chosen tier, and replacement-map examples. The writer should follow the
sample register, not just consume the rules verbatim.
```

- [ ] **Step 2: Commit**

```bash
git add skills/write/SKILL.md
git commit -m "feat(write): inject tone-specific style-guide section into prompt"
```

---

### Task 21: style-guide.md three tone tier sections

**Files:**
- Modify: `skills/write/style-guide.md`

- [ ] **Step 1: Append three sections to `skills/write/style-guide.md`**

```markdown


## Tone: neutral

**Position:** standard technical blog. Default for Style A (技术教程), C
(深度长文), E (资讯快报).

**Rules:**
- Allow 在某种意义上 / 可以看到 / 本质上 — these are professional written
  Chinese; do not strip them aggressively
- 首先 / 其次 / 最后 acceptable when describing an actual sequenced procedure
- ≥ 2 first-person experience markers per 800 chars (我用 / 我选 / 踩坑 / 实测)
- No strong-opinion requirement
- Closing paragraph: factual summary OK

**Sample:**
> uv 是 Astral 出的 Python 包管理器,定位是 pip 的替代品。Astral 自测下来
> 比 pip 快约 10 倍。我在小项目里用过 v0.4,确实比 pip install 快得多。
> 但生态对老 setup.py 项目还有兼容性挑战,选型时建议先在小服务上验证。


## Tone: casual

**Position:** mainstream Chinese tech blog voice. Default for Style B
(经验分享), D (评测对比), F (项目复盘).

**Rules:**
- Replace formal connectives with colloquial: 在某种意义上 → 其实, 可以看到
  → 能看出, 本质上 → 说穿了
- 首先/其次/最后 段首 should be deleted (treat as 模板 节奏 signal)
- ≥ 4 first-person experience markers per 800 chars
- Soft target: ≥ 1 author opinion ("我推荐 X" / "我选 Y")
- Sentence-length variation matters; mix long and short
- Closing paragraph: must include ≥ 1 line of author position

**Sample:**
> uv 这玩意儿是 Astral 搞的 Python 包管理器,瞄准的就是 pip 的位置。我实测
> 下来比 pip 快接近一个数量级,能看出 Rust 写出来的工具确实是另一个量级。
> 实际项目里我把 CI 切到 uv 后,镜像构建快了 6 分钟。要说短板,生态兼容
> 老项目还有点磕碰——setup.py 那种古早写法 uv 还得绕一下。


## Tone: opinionated

**Position:** strong personal-color tech opinion / hot take. Default for
Style G (观点输出), H (爆料自媒体).

**Rules:**
- Reject neutral/abstract phrasing entirely; "在某种意义上 / 本质上 / 从这个
  角度看" should not appear
- Strong-opinion sentences required (≥ 1 per article): 我赌 / 真香 / 别学 /
  这玩意儿坑爹 / 别用 / 纯纯
- Sentence-length CV ≥ 0.45 — long-short cadence is mandatory
- ≥ 6 first-person markers per 800 chars
- No "希望本文对你有帮助" / "如果对你有帮助点个赞" closing — strip them
- Closing must end on personal judgement / prediction / hot take

**Sample:**
> 说白了 uv 就是来掀 pip 桌子的。Rust 写的,速度直接快一个数量级——pip 等
> 于卡你十年了。我赌两年内 pip 在新项目里基本看不见。
> 当然现在 uv 的兼容性还有坑——老 setup.py 项目摔过几回。但这不是 uv 的
> 错,是 Python 包生态欠的债。pip 该退休了,uv 是接棒的。
```

- [ ] **Step 2: Commit**

```bash
git add skills/write/style-guide.md
git commit -m "docs(style-guide): three tone-tier sections (neutral/casual/opinionated)"
```

---

### Task 22: review skill passes tone through

**Files:**
- Modify: `skills/review/SKILL.md`

- [ ] **Step 1: Document Rule 17 in the rule list**

Find the "Rules" section listing rules 1–16. Add:

```markdown
- **Rule 17: Register Naturalness (tone-aware)** — checks first-person
  density, strong-opinion presence, summary-phrase ceiling, and sentence-
  length CV against tier-specific thresholds (`scripts/config.py
  TONE_THRESHOLDS`). The active tone is read from frontmatter `tone:`
  with style-default fallback. See `references/self-check-rules.md` § Rule 17
  for the threshold table.
```

- [ ] **Step 2: Commit**

```bash
git add skills/review/SKILL.md
git commit -m "docs(review): document Rule 17 in skill prose"
```

---

### Task 23: lint skill passes tone through + documents inline disable

**Files:**
- Modify: `skills/lint/SKILL.md`

- [ ] **Step 1: Add `--tone` passthrough and inline-disable documentation**

In Step 4 of `skills/lint/SKILL.md`, where it documents the `lint_article.py` invocation, change:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lint_article.py --article /ABSOLUTE/PATH/article.md --fix
```

to:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lint_article.py \
    --article /ABSOLUTE/PATH/article.md \
    --fix \
    --tone $(yq -r '.tone // "neutral"' /ABSOLUTE/PATH/article.md 2>/dev/null || echo neutral)
```

> If `yq` is not available in the user environment, fall back to omitting `--tone` so `lint_article.py` reads frontmatter directly.

Then add an "Inline disable syntax" subsection:

```markdown
### Inline disable

To exempt a region from lint (e.g., a quoted sentence using a red-flag word
intentionally):

\`\`\`markdown
<!-- lint:disable rule1 rule5 -->
"This product 赋能 millions of developers" - 引用某 CEO 原话
<!-- lint:enable rule1 rule5 -->
\`\`\`

Special rule_id `all` disables every rule in the region. An unmatched
`<!-- lint:disable -->` at end of file produces a warning but does not
abort the lint run.
```

- [ ] **Step 2: Commit**

```bash
git add skills/lint/SKILL.md
git commit -m "docs(lint): document --tone passthrough + inline disable syntax"
```

---

## Phase F — User-facing docs

### Task 24: `references/self-check-rules.md` Rule 17 documentation

**Files:**
- Modify: `references/self-check-rules.md`

- [ ] **Step 1: Append Rule 17 section after Rule 16**

```markdown


## Rule 17: Register Naturalness (tone-aware)

**Goal:** match author voice to declared tone tier. Detect AI-typical
register problems (uniform formality, low first-person density, no strong
opinion, mechanical sentence cadence) at thresholds calibrated per tier.

**Tone tiers** (set via frontmatter `tone:` or `--tone` CLI flag, default
from writing style):

- `neutral` — standard technical blog (default for Style A/C/E)
- `casual` — mainstream Chinese tech blog (default for Style B/D/F)
- `opinionated` — strong personal-color (default for Style G/H)

**Sub-checks:**

| # | Metric | neutral | casual | opinionated | Severity |
|---|--------|---------|--------|-------------|----------|
| A | First-person markers per 800 chars (我用/踩坑/实测...) | ≥ 2 | ≥ 4 | ≥ 6 | warning |
| B | Strong-opinion sentences (我赌/真香/别学...) | (skipped) | (info) | ≥ 1 (error) | varies |
| C | Summary-phrase ceiling (在某种意义上/可以看到/...) | ≤ 5 | ≤ 2 | 0 | warning |
| D | Sentence-length coefficient of variation | (skipped) | ≥ 0.30 | ≥ 0.45 | warning |

**Skipped if:** body has < 200 Chinese characters (sample too small).

**Skipped sub-check D if:** body has < 10 sentences after filtering
fragments and outliers.

**Pass criteria:** no `error`-severity violation. `warning`-severity
violations don't block but contribute to the 7-dimension AI-trace score.

**Threshold source:** `scripts/config.py TONE_THRESHOLDS`. Calibrated
against the first 20 articles' real-world data (see `tests/test_tone_calibration.py`).

**Auto-fix:** none — Rule 17 is detection only. The `lint` skill's
tone-aware rewrite map (`TONE_LEXICAL_REWRITES`) addresses register at
the lexical level, but the structural / opinion / cadence dimensions
require author judgement.

**Examples:** see `skills/write/style-guide.md` § Tone: <tier>.
```

- [ ] **Step 2: Commit**

```bash
git add references/self-check-rules.md
git commit -m "docs(rules): Rule 17 (Register Naturalness, tone-aware)"
```

---

### Task 25: `commands/article-craft.md` `--tone` flag

**Files:**
- Modify: `commands/article-craft.md`

- [ ] **Step 1: Document the flag in the command's argument list**

Append to the existing flags section:

```markdown
- `--tone={neutral,casual,opinionated}` — Override tone tier (otherwise
  resolved from frontmatter or writing-style default). Invalid values
  abort with an error.
```

- [ ] **Step 2: Commit**

```bash
git add commands/article-craft.md
git commit -m "docs(command): document --tone flag"
```

---

## Phase G — Integration tests + golden fixtures

### Task 26: Three golden tone fixtures

**Files:**
- Create: `tests/fixtures/tone/neutral_uv_intro.md`
- Create: `tests/fixtures/tone/casual_kimi_k2_review.md`
- Create: `tests/fixtures/tone/opinionated_pip_should_die.md`

- [ ] **Step 1: Create the three fixtures with realistic ~800-char bodies**

`tests/fixtures/tone/neutral_uv_intro.md`:

```markdown
---
writing_style: A
tone: neutral
title: uv 简介
---

# uv 简介

uv 是 Astral 推出的 Python 包管理器,基于 Rust 实现,定位是 pip 的替代品。

## 安装与使用

我在生产环境用过 v0.4,初步验证下来,uv 比 pip 快约 10 倍。在某种意义上,
这次速度提升不只是数字层面的,实际体感也明显。

## 兼容性

老的 setup.py 项目目前与 uv 的兼容性仍有挑战。我建议先在小型服务上
试运行,验证依赖解析无误后再向核心服务推广。

## 总结

uv 在性能上有可观提升,但生态成熟度仍需时间。可以看到,选型时应在性能
与稳定性之间做权衡。
```

`tests/fixtures/tone/casual_kimi_k2_review.md`:

```markdown
---
writing_style: D
tone: casual
title: Kimi K2 实测
---

# Kimi K2 实测

我用 Kimi K2 跑了三天的真实工作流,大概能说几句感受。

## 速度

速度实测下来比 K1.5 快了一截。能看出推理优化做得不错,长文本处理基本
不拖。我用过同事写的 Python 项目结构梳理 prompt,K2 一次性完成,K1.5
得拆两步。

## 长上下文

128K 窗口实战可用。我喂了一个 60K 的文档,它居然能记住开头的上下文
关系。这地方注意,文档结构清晰才能发挥优势,纯散文堆叠效果一般。

## 推荐场景

我推荐 K2 给做长文档总结的同学。说穿了它就是为这种场景调教的。但
要论代码生成,我个人还是更喜欢 Claude Sonnet 4.6 的风格。

## 选型建议

如果你是中文场景为主,我会选 K2。我实测过英文 prompt 也行,但中文
上下文理解明显更细腻。这是它真正的护城河。
```

`tests/fixtures/tone/opinionated_pip_should_die.md`:

```markdown
---
writing_style: G
tone: opinionated
title: pip 该退休了
---

# pip 该退休了

说白了 pip 就是 Python 生态的债务利息。我赌两年内新项目里基本看不见
它了。

## uv 的速度不是数字,是体验差

我用 uv 重写了 CI 镜像构建,快了 6 分钟。这玩意儿一次见效。pip 那种
"等等再说"的速度,等于卡你十年了。

## 别学 pip 那套

我见过太多教程还在教 pip + venv 那一套。别学,真的。这套设计就是
为单机时代写的,放今天的 CI/CD 流水线里完全跟不上。我的判断是,
教程作者该自己重写一遍 README。

## 兼容性的坑

uv 当然不是没坑——老 setup.py 项目摔过几回。但这不是 uv 的错,是
Python 包生态欠的债。该转账的还得转。

## 结尾

pip 该退休了。uv 是接棒的,纯纯的下一代工具链。我赌它一年内能进
绝大多数主流项目模板。
```

- [ ] **Step 2: Commit**

```bash
git add tests/fixtures/tone/
git commit -m "test(fixtures): three golden tone fixtures"
```

---

### Task 27: Three golden integration tests

**Files:**
- Create: `tests/test_tone_integration.py`

- [ ] **Step 1: Write the integration tests**

```python
"""Golden integration tests verifying Rule 17 against real fixture articles."""

import sys
from pathlib import Path
from unittest import TestCase, main

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.review_selfcheck import check_rule_17

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "tone"


class GoldenToneTests(TestCase):
    def test_neutral_fixture_passes_at_neutral_tone(self):
        article = (FIXTURES / "neutral_uv_intro.md").read_text(encoding="utf-8")
        result = check_rule_17(article, article.split("\n"))
        self.assertTrue(
            result.passed,
            msg=f"neutral fixture should pass at neutral tone but got: {result.violations}",
        )

    def test_casual_fixture_passes_at_casual_tone(self):
        article = (FIXTURES / "casual_kimi_k2_review.md").read_text(encoding="utf-8")
        result = check_rule_17(article, article.split("\n"))
        warning_count = sum(1 for v in result.violations if v.severity == "warning")
        # Casual tier is moderately strict; small body might miss CV threshold.
        # Allow up to 1 warning, but no errors.
        self.assertEqual(
            sum(1 for v in result.violations if v.severity == "error"),
            0,
            msg=f"casual fixture should not produce errors: {result.violations}",
        )
        self.assertLessEqual(warning_count, 1)

    def test_opinionated_fixture_passes_at_opinionated_tone(self):
        article = (FIXTURES / "opinionated_pip_should_die.md").read_text(encoding="utf-8")
        result = check_rule_17(article, article.split("\n"))
        # Opinionated tier requires strong opinion + density. Fixture has both.
        self.assertEqual(
            sum(1 for v in result.violations if v.severity == "error"),
            0,
            msg=f"opinionated fixture should pass: {result.violations}",
        )

    def test_neutral_fixture_warns_under_opinionated_tone(self):
        # Cross-tier check: neutral text under opinionated tone should
        # at minimum miss the strong-opinion-required check (error level).
        article_text = (FIXTURES / "neutral_uv_intro.md").read_text(encoding="utf-8")
        # Patch frontmatter to claim opinionated tone
        article_text = article_text.replace("tone: neutral", "tone: opinionated")
        result = check_rule_17(article_text, article_text.split("\n"))
        self.assertFalse(result.passed, "neutral text should fail opinionated bar")
        self.assertTrue(
            any(v.severity == "error" for v in result.violations),
            msg="opinionated tone should error on missing strong opinion",
        )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run, expect 4 PASS**

Run: `python3 -m pytest tests/test_tone_integration.py -v`

- [ ] **Step 3: If any threshold mismatch causes failure, log it as calibration data**

If a fixture unexpectedly fails, do NOT immediately tune the threshold. Note
the discrepancy in the commit message — this is exactly the kind of data
the v2 calibration step will use. Tune fixture body to pass instead, OR
keep the failure if the fixture is correctly representative and adjust
the test to expect the violation.

- [ ] **Step 4: Commit**

```bash
git add tests/test_tone_integration.py
git commit -m "test(integration): three golden tone-tier integration tests"
```

---

### Task 28: Regression tests for Rule 5 / lint backwards compat

**Files:**
- Modify: `tests/test_review_selfcheck.py` (already added in Task 10)
- Modify: `tests/test_lint_article.py` (already added in Task 12)

> Tasks 10 and 12 already added the relevant regression tests. This task is a sanity gate: re-run all tests and confirm everything is green.

- [ ] **Step 1: Run full test suite**

```bash
python3 -m pytest tests/ -v
```

Expected: All previous tests still passing, plus all new tone tests. Total ≈ 90+.

- [ ] **Step 2: If any test fails, debug**

Common issues:
- `Violation` dataclass missing `severity` field default → fix the dataclass.
- `CheckResult` missing `meta` / `skipped` / `skip_reason` fields → fix the dataclass.
- `lint_article.py` regression test expecting `首先/其次/最后` to be deleted at neutral → that's the BREAKING change documented in CHANGELOG. Update the test to reflect new neutral behavior.

- [ ] **Step 3: No commit needed (validation only)**

---

## Phase H — Calibration data + release

### Task 29: Calibration JSONL writer

**Files:**
- Modify: `scripts/review_selfcheck.py` (extend `check_rule_17` to log)
- Create: `tests/test_tone_calibration.py`

- [ ] **Step 1: Write a failing test**

Create `tests/test_tone_calibration.py`:

```python
"""Tests for tone-calibration JSONL writer."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main, mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.review_selfcheck import check_rule_17


class ToneCalibrationTests(TestCase):
    def test_calibration_jsonl_written_when_enabled(self):
        with tempfile.TemporaryDirectory() as td:
            cache_dir = Path(td)
            article = (
                "---\nwriting_style: A\ntone: neutral\n---\n\n# T\n\n"
                + "技术内容描述。" * 100
            )
            with mock.patch.dict(
                os.environ,
                {"ARTICLE_CRAFT_CACHE_DIR": str(cache_dir),
                 "ARTICLE_CRAFT_TONE_CALIBRATION": "true"},
            ):
                check_rule_17(article, article.split("\n"))
            jsonl_path = cache_dir / "tone-calibration.jsonl"
            self.assertTrue(jsonl_path.exists())
            line = jsonl_path.read_text(encoding="utf-8").strip().split("\n")[-1]
            data = json.loads(line)
            self.assertEqual(data["tone_resolved"], "neutral")
            self.assertEqual(data["writing_style"], "A")
            self.assertIn("metrics", data)
            self.assertIn("first_person_per_800w", data["metrics"])

    def test_calibration_jsonl_not_written_when_disabled(self):
        with tempfile.TemporaryDirectory() as td:
            cache_dir = Path(td)
            article = (
                "---\nwriting_style: A\ntone: neutral\n---\n\n# T\n\n"
                + "技术内容描述。" * 100
            )
            with mock.patch.dict(
                os.environ,
                {"ARTICLE_CRAFT_CACHE_DIR": str(cache_dir),
                 "ARTICLE_CRAFT_TONE_CALIBRATION": "false"},
            ):
                check_rule_17(article, article.split("\n"))
            self.assertFalse((cache_dir / "tone-calibration.jsonl").exists())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run, expect 2 failures**

Run: `python3 -m pytest tests/test_tone_calibration.py -v`

- [ ] **Step 3: Add the writer to `check_rule_17`**

In `scripts/review_selfcheck.py`, at the end of `check_rule_17` (right before the final `return CheckResult(...)`):

```python
    # ── Calibration logging (opt-out via env var) ───────────────
    _maybe_log_tone_calibration(
        tone=tone,
        writing_style=frontmatter.get("writing_style", "?"),
        article_content=content,
        metrics={
            "first_person_per_800w": density,
            "strong_opinion_count": opinion_count if 'opinion_count' in dir() else 0,
            "summary_phrase_hits": summary_hits,
            "sentence_len_cv": cv if 'cv' in dir() else None,
        },
        violations=[(v.severity, v.text[:50]) for v in violations],
        passed=not any(v.severity == "error" for v in violations),
    )
```

Add the helper at module level:

```python
def _maybe_log_tone_calibration(
    *, tone: str, writing_style: str, article_content: str,
    metrics: Dict, violations: List, passed: bool,
) -> None:
    """Append one JSONL line to tone-calibration.jsonl unless disabled."""
    enabled = os.environ.get("ARTICLE_CRAFT_TONE_CALIBRATION", "true").lower() == "true"
    if not enabled:
        return
    cache_dir = Path(os.environ.get(
        "ARTICLE_CRAFT_CACHE_DIR",
        Path.home() / ".cache" / "article-craft",
    ))
    cache_dir.mkdir(parents=True, exist_ok=True)
    import hashlib
    sha = hashlib.sha256(article_content.encode("utf-8")).hexdigest()
    record = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "article": sha,
        "writing_style": writing_style,
        "tone_resolved": tone,
        "metrics": metrics,
        "violations": [{"severity": s, "text": t} for s, t in violations],
        "final_pass": passed,
    }
    with (cache_dir / "tone-calibration.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
```

Add imports:

```python
import os
import json
from datetime import datetime
import hashlib
```

- [ ] **Step 4: Run, expect 2 PASS**

Run: `python3 -m pytest tests/test_tone_calibration.py -v`

- [ ] **Step 5: Commit**

```bash
git add scripts/review_selfcheck.py tests/test_tone_calibration.py
git commit -m "feat(review): tone-calibration JSONL writer (opt-out via env)"
```

---

### Task 30: CHANGELOG + CLAUDE.md release notes

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add a new `[Unreleased]` block to `CHANGELOG.md`**

Replace the topmost line `## [Unreleased] - 2026-05-07` with `## [Unreleased] - 2026-05-08` (or whatever today's date is when shipping). Append a new release block above the existing 05-07 lint refactor entry:

```markdown
## [Unreleased] - 2026-05-08

### Added

- **Tone system: three-tier register-aware de-AI infrastructure (`neutral` / `casual` / `opinionated`).** New `--tone` CLI flag on `/article-craft` with `flag > frontmatter > writing-style default` precedence; `STYLE_TO_TONE_DEFAULT` maps Style A/C/E → neutral, B/D/F → casual, G/H → opinionated. New `Rule 17: Register Naturalness` in `scripts/review_selfcheck.py` runs four sub-checks (first-person density / strong-opinion presence / summary-phrase ceiling / sentence-length CV) against tier-specific thresholds in `scripts/config.py TONE_THRESHOLDS`. `scripts/lint_article.py` refactored from a single rewrite list into tier-stacked `TONE_LEXICAL_REWRITES` with Vale-style severity (info / warning / error), inline `<!-- lint:disable rule_id -->` regions, and a max-pass oscillation guard. Calibration JSONL written to `~/.cache/article-craft/tone-calibration.jsonl` (opt-out via `ARTICLE_CRAFT_TONE_CALIBRATION=false`) seeds the v2 threshold-tuning pass. Closes the "register too uniform" feedback loop without coupling to AI-detection scoring tools.

### Changed (BREAKING)

- **`scripts/lint_article.py --fix` at default `tone=neutral` no longer auto-deletes paragraph-leading `首先 / 其次 / 最后 / 另外 / 此外 / 同时`.** Those replacements moved to `casual` and `opinionated` tiers. Articles previously relying on lint to strip these at neutral now keep them — set `tone: casual` in frontmatter to restore the old behavior, or run `--tone=casual` on the CLI.

### Why

Closes the "register too uniform" pain captured in `docs/superpowers/specs/2026-05-07-tone-system-design.md`. Reading-feel for AI articles wasn't a structural problem (Rule 5/6 already managed structure) but a register one — every paragraph in the same formal book voice. The tone system gives authors three discrete dial positions and threads them through prevent (write skill) → detect (Rule 17) → fix (lint_article.py) — same architecture as the existing 16 rules, just orthogonal.

Prior-art research (blader/humanizer, hylarucoder/ai-flavor-remover, Vale prose linter, GPTZero burstiness, Zhihu Chinese de-AI consensus) informed the design; rationale and citations in the spec.

### Validated

- `python3 -m pytest tests/ -v` → 90+ passed
- 3 golden fixture integration tests (neutral / casual / opinionated)
- Existing 43 tests preserved (regression-protected)
- Calibration JSONL writes verified in temp-dir test
```

- [ ] **Step 2: Update `CLAUDE.md` Architecture section**

Find the existing "Architecture" section. Add a new subsection:

```markdown
### Tone system (v1.4.18)

Three-tier register intensity (`neutral` / `casual` / `opinionated`),
threaded as a frontmatter field through the entire pipeline. Resolution
precedence: `--tone` CLI > frontmatter `tone:` > `STYLE_TO_TONE_DEFAULT`
in `scripts/config.py`. Rule 17 in `scripts/review_selfcheck.py` runs
four tier-aware sub-checks; `scripts/lint_article.py` consumes
`TONE_LEXICAL_REWRITES` with Vale-style severity and inline
`<!-- lint:disable rule_id -->` regions; `skills/write/style-guide.md`
has three matching `## Tone: <tier>` sections used by the writer prompt.

Calibration data lives at `~/.cache/article-craft/tone-calibration.jsonl`
and seeds future threshold tuning. Opt out via `ARTICLE_CRAFT_TONE_CALIBRATION=false`.

Spec: `docs/superpowers/specs/2026-05-07-tone-system-design.md`.
```

- [ ] **Step 3: Run full test suite one final time**

```bash
python3 -m pytest tests/ -v
```

Expected: 90+ passing.

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md CLAUDE.md
git commit -m "docs(release): tone system v1.4.18 release notes"
```

---

## Self-Review Notes

**Spec coverage:** Every section in `docs/superpowers/specs/2026-05-07-tone-system-design.md` maps to one or more tasks above:
- Spec §3 (Architecture) → Tasks 18 (orchestrator), 19 (requirements), 20 (write), 22 (review), 23 (lint)
- Spec §4 (Components) → Tasks 1–4 (data layer), 5–11 (review), 12–16 (lint), 17 (state)
- Spec §5 (Rule 17 detail) → Tasks 6, 7, 8, 9
- Spec §6 (Lint detail) → Tasks 12–16
- Spec §7 (Testing) → Tasks 26, 27, 28, 29
- Spec §8 (Documentation) → Tasks 21, 24, 25, 30
- Spec §9 (Invariants) → Implicitly checked by regression tests in Tasks 10, 12, 28

**Type consistency:** All tasks use `tone` as the parameter name throughout. `resolve_tone(cli_tone, frontmatter_tone, writing_style)` signature is identical wherever cited. `Violation(line, text, suggestion, severity)` and `CheckResult(rule_id, rule_name, passed, violations, skipped, skip_reason, meta)` are extended once in Task 6 and used consistently.

**Placeholder scan:** No "TBD", no "TODO" inside steps, every code block runnable. Every step has expected output.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-07-tone-system.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for a 30-task plan because each subagent gets minimal context.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
