# WeChat-Native Body Form Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an orthogonal `body_form` axis (`wechat-native` default / `long-form` opt-in) threaded through the article pipeline like the existing `tone` axis, so a generic request produces a mobile-shaped 公众号 article instead of a blog one — while keeping the A–H content styles and a one-switch path to long-form for the KB copy.

**Architecture:** `body_form` is a new frontmatter field resolved with `--body-form CLI > frontmatter body_form: > legacy wechat_target:false alias > default wechat-native`. A pure resolver in `scripts/config.py` (mirroring `resolve_tone`) is the testable core. The writer injects a new `## Body Form: wechat-native` section from `style-guide.md` (same mechanism as tone injection); callouts become form-conditional. Enforcement is augmentation-only: a soft review Phase-2 signal + a form-aware Rule 6 threshold, **no new write gate**.

**Tech Stack:** Python 3 (config.py, review_selfcheck.py), pytest, prompt-first SKILL.md / style-guide.md markdown. Spec: `docs/superpowers/specs/2026-05-29-wechat-native-body-form-design.md`.

---

## File Structure

- `scripts/config.py` — **modify**: add `BODY_FORM_LEVELS`, `DEFAULT_BODY_FORM`, `resolve_body_form()`. The pure, testable core of the axis.
- `tests/test_body_form_resolution.py` — **create**: precedence + alias + degradation tests (mirrors `tests/test_tone_resolution.py`).
- `scripts/review_selfcheck.py` — **modify**: `check_rule_6` reads `body_form`; `wechat-native` lowers the per-section code-block threshold by 1 (min 1).
- `tests/test_review_selfcheck.py` — **modify**: add Rule 6 form-aware tests.
- `skills/write/style-guide.md` — **modify**: new `## Body Form: wechat-native` section; absorb the existing "Platform Adaptation Rules" block into it.
- `skills/requirements/SKILL.md` — **modify**: emit `body_form` into resolved frontmatter, default `wechat-native`, `long-form` only on explicit opt-in.
- `skills/write/SKILL.md` — **modify**: Step 3a injects the Body Form section; form-conditional callout rendering; repoint the `wechat_target` read at resolved `body_form`.
- `skills/publish/SKILL.md` — **modify**: repoint the `wechat_target` read at resolved `body_form`.
- `skills/review/SKILL.md` — **modify**: add a soft `body-form 一致性` signal to Phase 2's 结构可读 / 看一看友好度 dimensions.
- `skills/orchestrator/SKILL.md` — **modify**: parse `--body-form=<value>` in Step 1 and pass through to requirements (mirrors `--tone`); add `body_form` to the status tracker. *(Not in the spec's file list — required for the CLI flag path to work; see Task 8.)*

---

## Task 1: `resolve_body_form()` core in config.py

**Files:**
- Modify: `scripts/config.py` (add near `resolve_tone`, ~line 416)
- Test: `tests/test_body_form_resolution.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_body_form_resolution.py`:

```python
"""Tests for body-form resolution: levels enum, resolve_body_form() precedence + wechat_target alias."""

import sys
from pathlib import Path
from unittest import TestCase, main

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import config


class BodyFormLevelsTests(TestCase):
    def test_levels_enum_is_two_strings_in_order(self):
        self.assertEqual(config.BODY_FORM_LEVELS, ("wechat-native", "long-form"))

    def test_default_is_wechat_native(self):
        self.assertEqual(config.DEFAULT_BODY_FORM, "wechat-native")


class ResolveBodyFormTests(TestCase):
    def test_default_when_everything_missing(self):
        self.assertEqual(config.resolve_body_form(), "wechat-native")

    def test_cli_wins(self):
        self.assertEqual(
            config.resolve_body_form(cli_body_form="long-form",
                                     frontmatter_body_form="wechat-native",
                                     frontmatter_wechat_target=True),
            "long-form",
        )

    def test_frontmatter_body_form_wins_over_alias(self):
        self.assertEqual(
            config.resolve_body_form(frontmatter_body_form="long-form",
                                     frontmatter_wechat_target=True),
            "long-form",
        )

    def test_legacy_wechat_target_false_maps_to_long_form(self):
        self.assertEqual(
            config.resolve_body_form(frontmatter_wechat_target=False),
            "long-form",
        )

    def test_legacy_wechat_target_string_false_maps_to_long_form(self):
        # frontmatter parser yields strings, not bools
        self.assertEqual(
            config.resolve_body_form(frontmatter_wechat_target="false"),
            "long-form",
        )

    def test_wechat_target_true_stays_native(self):
        self.assertEqual(
            config.resolve_body_form(frontmatter_wechat_target=True),
            "wechat-native",
        )

    def test_invalid_values_degrade_to_default(self):
        self.assertEqual(
            config.resolve_body_form(cli_body_form="blog",
                                     frontmatter_body_form="zzz"),
            "wechat-native",
        )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_body_form_resolution.py -q`
Expected: FAIL — `AttributeError: module 'scripts.config' has no attribute 'BODY_FORM_LEVELS'`.

- [ ] **Step 3: Implement the constants + resolver in config.py**

Add immediately after the `resolve_tone` function (after line ~438, before `TONE_THRESHOLDS`):

```python
# ─── Body-form axis (orthogonal to style/tone/depth) ───────────────
# wechat-native: mobile-shaped 公众号 body (short paras, no callouts, ≤3
#   headings, image rhythm). The default — 公众号 is the primary target.
# long-form: today's blog behavior (callouts allowed, deep sections) — the
#   KB / blog archive copy.
BODY_FORM_LEVELS = ("wechat-native", "long-form")
DEFAULT_BODY_FORM = "wechat-native"


def resolve_body_form(
    cli_body_form: Optional[str] = None,
    frontmatter_body_form: Optional[str] = None,
    frontmatter_wechat_target=None,
) -> str:
    """Resolve final body form: CLI > frontmatter body_form: > legacy
    wechat_target alias > default wechat-native.

    `wechat_target: false` (bool or the string "false") is the back-compat
    alias for long-form. Any invalid value at a tier degrades to the next.
    Returns one of BODY_FORM_LEVELS, never None.
    """
    if cli_body_form in BODY_FORM_LEVELS:
        return cli_body_form
    if frontmatter_body_form in BODY_FORM_LEVELS:
        return frontmatter_body_form
    if frontmatter_wechat_target in (False, "false", "False"):
        return "long-form"
    return DEFAULT_BODY_FORM
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_body_form_resolution.py -q`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/config.py tests/test_body_form_resolution.py
git commit -m "feat(config): add body_form axis resolver (wechat-native default, wechat_target alias)"
```

---

## Task 2: Rule 6 form-aware threshold

**Files:**
- Modify: `scripts/review_selfcheck.py:764-814` (`check_rule_6`)
- Test: `tests/test_review_selfcheck.py` (add to `Rule6` test class or near existing Rule 6 tests)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_review_selfcheck.py` (near the existing `check_rule_6` test around line 158):

```python
    def test_rule6_wechat_native_lowers_threshold(self):
        # Style A default threshold is 2. A section with 1 code block FAILS
        # under long-form but PASSES under wechat-native (native lowers by 1).
        article = """---
title: demo
description: "demo"
writing_style: A
body_form: wechat-native
---

# 标题

## 实战一节

这一节有实际内容，超过两百字的正文用来触发深度检查。""" + ("占" * 200) + """

```python
print("only one block")
```
"""
        result = review_selfcheck.check_rule_6(article, article.splitlines())
        self.assertTrue(result.passed, result.details)

    def test_rule6_long_form_keeps_threshold(self):
        article = """---
title: demo
description: "demo"
writing_style: A
body_form: long-form
---

# 标题

## 实战一节

这一节有实际内容，超过两百字的正文用来触发深度检查。""" + ("占" * 200) + """

```python
print("only one block")
```
"""
        result = review_selfcheck.check_rule_6(article, article.splitlines())
        self.assertFalse(result.passed, result.details)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_review_selfcheck.py -k rule6_ -q`
Expected: FAIL — `test_rule6_wechat_native_lowers_threshold` fails because the section with 1 block is still flagged (threshold not yet form-aware).

- [ ] **Step 3: Make `check_rule_6` form-aware**

In `scripts/review_selfcheck.py`, inside `check_rule_6`, after the existing `base_threshold = STYLE_CODE_BLOCK_THRESHOLD.get(...)` line (line 780), insert:

```python
    # Body-form-aware: wechat-native sections are punchier and fewer, so they
    # need one fewer code block per section (min 1). long-form keeps the full
    # style threshold. Missing field degrades to wechat-native (the default).
    body_form_raw = (frontmatter.get("body_form", "") or "").strip()
    if frontmatter.get("wechat_target") in (False, "false", "False"):
        body_form_raw = "long-form"
    if body_form_raw != "long-form":  # wechat-native or unset (default)
        base_threshold = max(1, base_threshold - 1)
```

Then update the `details=` line (line 813) to surface the form:

```python
        details=f"{len(violations)} 个浅层章节 (style={style_key or '?'}, body_form={'long-form' if body_form_raw=='long-form' else 'wechat-native'}, threshold={base_threshold})"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_review_selfcheck.py -k rule6 -q`
Expected: PASS (both new tests + the pre-existing Rule 6 test).

- [ ] **Step 5: Run the full self-check suite (no regressions)**

Run: `python3 -m pytest tests/test_review_selfcheck.py -q`
Expected: PASS (all tests — the existing `test_cli_write_gate_*` fixtures have no `body_form` field, so they degrade to wechat-native; verify none flip).

- [ ] **Step 6: Commit**

```bash
git add scripts/review_selfcheck.py tests/test_review_selfcheck.py
git commit -m "feat(review): Rule 6 threshold is body-form-aware (wechat-native -1)"
```

---

## Task 3: `## Body Form` section in style-guide.md

**Files:**
- Modify: `skills/write/style-guide.md` (add a top-level `## Body Form: wechat-native` section; fold the existing "Platform Adaptation Rules" block into it)
- Test: `tests/test_body_form_styleguide.py` (create — structural guard)

- [ ] **Step 1: Write the failing structural test**

Create `tests/test_body_form_styleguide.py`:

```python
"""Structural guard: style-guide.md must document both body forms so the
writer prompt has something to inject (Task 5 depends on these anchors)."""

import sys
from pathlib import Path
from unittest import TestCase, main

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "skills" / "write" / "style-guide.md"


class BodyFormStyleGuideTests(TestCase):
    def setUp(self):
        self.text = GUIDE.read_text(encoding="utf-8")

    def test_has_wechat_native_section(self):
        self.assertIn("## Body Form: wechat-native", self.text)

    def test_documents_callout_ban(self):
        # The native form must explicitly forbid Obsidian callouts.
        self.assertRegex(self.text, r"Body Form: wechat-native[\s\S]*?callout")

    def test_documents_long_form(self):
        self.assertIn("long-form", self.text)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_body_form_styleguide.py -q`
Expected: FAIL — section not present yet.

- [ ] **Step 3: Add the Body Form section**

In `skills/write/style-guide.md`, locate the existing `### Platform Adaptation Rules` block (the one listing 30-line code / ≤3 heading / inline-link / 800-字 rules). Replace that block's heading and content with a new top-level section that absorbs it:

````markdown
## Body Form: wechat-native (default) vs long-form

`body_form` is resolved by the requirements skill (default `wechat-native`).
The writer applies these rules **on top of** the chosen content style (A–H).
`wechat-native` is the default because 公众号 is the primary target; `long-form`
is the opt-in KB/blog form (today's behavior, callouts allowed).

| Dimension | wechat-native (default) | long-form (opt-in) |
|---|---|---|
| Paragraph | ≤ ~200 字 / 3–4 短句, frequent breaks | unconstrained |
| Cold open | first screen (~100 字) must hook, zero "本文将…" runway | softer intro OK |
| Callouts | **banned** (公众号 doesn't render `> [!abstract]`) → use a **bold 引导句** or a single `>` quote | Obsidian `> [!abstract]` allowed |
| Headings | ≤ 2 levels (`##`/`###`), no deep nesting | ≤ 3 levels |
| Sections | fewer, punchier (≈3–5), one idea each | many deep sections OK |
| Image rhythm | a visual every ~2–3 screens (~600 字) | 1 图/章 |
| Throughline | one core question/conflict carried start→end | survey-of-subtopics OK |
| Code blocks | ≤30 行/块, split长代码 | ≤30 行/块 |

These numbers are guidance, not a hard gate (review surfaces violations as a
Phase-2 signal). The constraints formerly under "Platform Adaptation Rules"
(30-line code, ≤3 headings, inline links, 800-字 text-break) are subsumed here.
````

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_body_form_styleguide.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Verify no orphaned duplicate platform block remains**

Run: `grep -n "Platform Adaptation Rules" skills/write/style-guide.md`
Expected: no output (the old block heading was replaced, not duplicated).

- [ ] **Step 6: Commit**

```bash
git add skills/write/style-guide.md tests/test_body_form_styleguide.py
git commit -m "docs(write): add Body Form section to style-guide, absorb platform-adaptation block"
```

---

## Task 4: requirements emits `body_form`

**Files:**
- Modify: `skills/requirements/SKILL.md` (the resolved-frontmatter emission block near line 210, where `writing_style`/`tone`/`wechat_action` are emitted)

- [ ] **Step 1: Locate the emission block**

Run: `grep -n "writing_style=\|wechat_action\|tone:" skills/requirements/SKILL.md`
Expected: shows the resolved-output block (~line 210) and the frontmatter example (~line 272).

- [ ] **Step 2: Add `body_form` to the resolved-output block**

In `skills/requirements/SKILL.md`, in the resolved-fields block (~line 210, alongside `writing_style=...`), add a line:

```
    body_form=body_form_value,                    # default "wechat-native"; "long-form" only on explicit opt-in
```

And in the frontmatter example block (~line 272, near `wechat_action:`), add:

```
- body_form: wechat-native  # 正文形态: wechat-native (默认) | long-form (KB/博客长文)
```

- [ ] **Step 3: Add a "Layer" note describing the default rule**

Immediately after the existing Layer 4.5 (WeChat Action Inference) section, add a short subsection:

```markdown
### Layer 4.6: Body Form (NEW, v1.8+)

`body_form` decides正文形态, **orthogonal to style and depth**. Default is
**`wechat-native`** for every request — 公众号 is the primary target, so a
generic "写一篇关于 X" gets a mobile-shaped body (the content *style* still
resolves to A/tutorial, only the *form* is native).

Emit `long-form` **only** on an explicit signal — never auto-inferred from
depth/教程 keywords (that is the blog bias we are removing):
- `--body-form long-form` CLI flag (passed through by the orchestrator), or
- frontmatter `body_form: long-form`, or
- legacy frontmatter `wechat_target: false` (back-compat alias).

The canonical resolver is `config.resolve_body_form()`.
```

- [ ] **Step 4: Verify the field is documented**

Run: `grep -n "body_form" skills/requirements/SKILL.md`
Expected: at least the emission line, the frontmatter example, and the Layer 4.6 note.

- [ ] **Step 5: Commit**

```bash
git add skills/requirements/SKILL.md
git commit -m "feat(requirements): emit body_form (default wechat-native, long-form opt-in only)"
```

---

## Task 5: write injects Body Form + form-conditional callouts + repoint wechat_target

**Files:**
- Modify: `skills/write/SKILL.md` (Step 3a injection area near line 271-290; the callout instructions around line 332-343; the `wechat_target` read at line 169)

- [ ] **Step 1: Locate the tone-injection step and the callout + wechat_target sites**

Run: `grep -n "tone:\|## Tone\|wechat_target\|callout\|abstract\|Step 3a" skills/write/SKILL.md`
Expected: shows the Step 3a tone-injection block, the callout-usage instructions, and the `wechat_target: false` read.

- [ ] **Step 2: Add Body Form injection alongside tone injection**

In `skills/write/SKILL.md` Step 3a (where it already instructs the writer to read the matching `## Tone:` section from style-guide.md), add a parallel instruction:

```markdown
**同时注入 Body Form 形态规则**：从 `style-guide.md` 读取 `## Body Form: wechat-native`
段，按已解析的 `body_form` 字段应用对应列的规则到正文写作上下文：
- `wechat-native`（默认）：短段（≤~200 字）、强冷开场、**禁用 Obsidian callout**（改 bold 引导句 / 单行 `>` 引用）、标题 ≤2 级、章节少而利落、每 ~600 字一个视觉物、单主线。
- `long-form`：今天的行为（callout 允许、深章节），用于 KB/博客副本。
`body_form` 缺失时按 `wechat-native` 处理。
```

- [ ] **Step 3: Make the callout instruction form-conditional**

Find the instruction that mandates Obsidian callouts (e.g. `> [!abstract]`) for Styles A/C/D. Wrap it with a form condition:

```markdown
> **形态条件**：以下 callout（`> [!abstract]` 等）规则**仅在 `body_form: long-form` 下生效**。
> 在 `body_form: wechat-native`（默认）下，公众号不渲染 Obsidian callout —— 改写成
> **bold 引导句**（`**一句话重点**`）或单行 `>` 普通引用，不要用 `> [!type]` 语法。
```

- [ ] **Step 4: Repoint the wechat_target read at resolved body_form**

Find the `wechat_target: false` exception (line ~169) and change it to read the resolved form:

```markdown
- 当 `body_form: long-form`（含 legacy `wechat_target: false` 别名）时，跳过此步骤，直接用单一标题
```

- [ ] **Step 5: Verify**

Run: `grep -n "Body Form\|body_form\|形态条件" skills/write/SKILL.md`
Expected: shows the injection instruction, the form-conditional callout note, and the repointed read.

- [ ] **Step 6: Commit**

```bash
git add skills/write/SKILL.md
git commit -m "feat(write): inject Body Form rules, form-conditional callouts, repoint wechat_target read"
```

---

## Task 6: publish repoints wechat_target at body_form

**Files:**
- Modify: `skills/publish/SKILL.md:289` (the `wechat_target: false` checklist-skip exception)

- [ ] **Step 1: Locate the read**

Run: `grep -n "wechat_target" skills/publish/SKILL.md`
Expected: the line (~289) where `wechat_target: false` skips the WeChat publish checklist.

- [ ] **Step 2: Repoint it**

Change the exception to:

```markdown
**例外**：如果文章 `body_form: long-form`（含 legacy `wechat_target: false` 别名，即明确非公众号场景，如纯 blog/KB 输出），可以跳过此 checklist。
```

- [ ] **Step 3: Verify**

Run: `grep -n "body_form\|wechat_target" skills/publish/SKILL.md`
Expected: shows the repointed exception mentioning `body_form: long-form`.

- [ ] **Step 4: Commit**

```bash
git add skills/publish/SKILL.md
git commit -m "feat(publish): skip WeChat checklist on body_form: long-form (was dead wechat_target)"
```

---

## Task 7: review Phase-2 soft form-consistency signal

**Files:**
- Modify: `skills/review/SKILL.md` (Phase 2 scoring, the 结构可读 / 看一看友好度 dimension rows ~line 161-169)

- [ ] **Step 1: Locate the Phase-2 dimension table**

Run: `grep -n "结构可读\|看一看友好度\|8-Dimension" skills/review/SKILL.md`
Expected: the 8-dimension scoring table.

- [ ] **Step 2: Add a body-form consistency note to 结构可读**

In the `结构可读` row's scoring criteria, append:

```
；body-form 一致性（当 body_form=wechat-native 时：无 `> [!type]` callout 残留、段落≤~200字、标题≤3级）
```

- [ ] **Step 3: Add a Phase-2 reminder paragraph**

Below the dimension table, add:

```markdown
> **Body-form 软检查（v1.8+，仅诊断不阻断）**：当 `body_form: wechat-native`（默认）时，
> 在 `结构可读` 维度扣分项里记入：残留的 Obsidian callout（`> [!abstract]` 等）、
> 超长段落、标题层级 >3、整篇缺图节奏。这是软信号，**不新增 write GATE**——与项目
> augmentation > gating 哲学一致。`long-form` 文章不受此检查约束。
```

- [ ] **Step 4: Verify**

Run: `grep -n "body-form\|body_form" skills/review/SKILL.md`
Expected: shows the dimension-criteria addition and the reminder paragraph.

- [ ] **Step 5: Commit**

```bash
git add skills/review/SKILL.md
git commit -m "feat(review): soft body-form consistency signal in Phase 2 (no gate)"
```

---

## Task 8: orchestrator parses & passes `--body-form`

**Files:**
- Modify: `skills/orchestrator/SKILL.md` (Step 1 flag parsing ~line 148 where `--tone` is handled; the status tracker ~line 159; the Inputs section ~line 48; `commands/article-craft.md` flags doc)

- [ ] **Step 1: Locate the --tone handling (the pattern to mirror)**

Run: `grep -n "\-\-tone\|Determine Mode\|requirements:" skills/orchestrator/SKILL.md`
Expected: the Step 1 `--tone` parse line (~148) and the requirements call.

- [ ] **Step 2: Add `--body-form` parsing in Step 1**

After the `--tone` parsing line (~148), add:

```markdown
- Detect `--body-form=<value>` (also accept the bare `--long-form` shorthand for `--body-form=long-form`). If `<value>` not in `{wechat-native,long-form}`, abort with: "Invalid body-form: <value>. Allowed: wechat-native, long-form." Otherwise pass it through to the `requirements` skill as `--body-form=<value>`. If absent, requirements applies the default (`wechat-native`).
```

- [ ] **Step 3: Add `body_form` to the Inputs section**

In the orchestrator Inputs list (~line 48, after the Tone flag), add:

```markdown
- **Body-form flag** (optional): `--body-form={wechat-native,long-form}` (or `--long-form`). Cascade: this flag > frontmatter `body_form:` > legacy `wechat_target:false` > default `wechat-native`. Pass through to requirements.
```

- [ ] **Step 4: Add `body_form` to the status tracker**

In the Step 2 status-tracker block, under the `requirements:` sub-bullets (~line 161), add:

```
    └─ body form: wechat-native (default) / long-form
```

- [ ] **Step 5: Document the flag in the slash command**

In `commands/article-craft.md`, in the Flags section (where `--tone`/`--series` are listed), add a line:

```markdown
- `--body-form={wechat-native,long-form}` (or `--long-form`) — 正文形态。默认 `wechat-native`（公众号原生短文体）；`long-form` 产出博客/KB 长文体。
```

- [ ] **Step 6: Verify**

Run: `grep -n "body-form\|body_form" skills/orchestrator/SKILL.md commands/article-craft.md`
Expected: parsing line, Inputs entry, tracker line, and the command flag doc.

- [ ] **Step 7: Commit**

```bash
git add skills/orchestrator/SKILL.md commands/article-craft.md
git commit -m "feat(orchestrator): parse --body-form / --long-form, pass through to requirements"
```

---

## Task 9: Full-suite regression + version bump

**Files:**
- Modify: version files via `scripts/bump_version.py`

- [ ] **Step 1: Run the entire test suite**

Run: `python3 -m pytest tests/ -q`
Expected: PASS — previous 506 + Task 1 (9) + Task 2 (2) + Task 3 (3) = 520 tests.

- [ ] **Step 2: Sanity-check the default path end-to-end (manual)**

Run:
```bash
python3 -c "import sys; sys.path.insert(0,'scripts'); import config; \
print(config.resolve_body_form()); \
print(config.resolve_body_form(frontmatter_wechat_target='false'))"
```
Expected: `wechat-native` then `long-form`.

- [ ] **Step 3: Bump the minor version (new feature axis)**

Run: `python3 scripts/bump_version.py minor --no-tag`
Expected: `v1.8.0`; plugin.json + marketplace.json + all 14 SKILL.md frontmatter updated.

- [ ] **Step 4: Update the spec status + CLAUDE.md**

In `docs/superpowers/specs/2026-05-29-wechat-native-body-form-design.md`, change `**Status**: design` → `**Status**: implemented (v1.8.0)`. In `CLAUDE.md`, add a short "Body-form axis (v1.8.0)" subsection near the Tone-system section describing the orthogonal axis + `resolve_body_form` + the `wechat_target` alias.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore(release): v1.8.0 — orthogonal body-form axis (wechat-native default)"
```

---

## Self-Review (completed during planning)

- **Spec coverage:** §3 axis → Tasks 1,4,8; §4 native rules → Task 3; §5 enforcement (augmentation, soft review, Rule 6) → Tasks 7,2; §6 file list → Tasks 1-7; `wechat_target` revival → Tasks 1,5,6. **Gap found & added:** spec §6 omitted the orchestrator, but the `--body-form` CLI flag needs it → Task 8. Success criteria §8.1-8.5 → Tasks 4 (default native), 5/6 (long-form parity), 1 (degradation), 9 (suite green + bump), 7 (form-consistency signal).
- **Placeholder scan:** none — every code/prompt step has concrete content.
- **Type consistency:** `resolve_body_form(cli_body_form, frontmatter_body_form, frontmatter_wechat_target)`, `BODY_FORM_LEVELS`, `DEFAULT_BODY_FORM` used identically across Tasks 1, 2, 9. `body_form` frontmatter key + `wechat-native`/`long-form` values consistent across Tasks 2-8.
- **Scope:** single feature axis, no decomposition needed. Deferred (per spec §2/§7): simultaneous two-form output, per-section overrides, AI-detection.
