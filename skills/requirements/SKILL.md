---
name: article-craft:requirements
version: 1.9.11
description: "Enhanced requirements gathering with intelligent inference + source trust detection — topic analysis, intent detection, ambiguity resolution, and context-aware suggestions. Uses multi-signal matching and collaborative confirmation."
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - WebSearch
  - WebFetch
  - AskUserQuestion
---

# Requirements Gathering (Enhanced)

Collect article requirements through **intelligent inference first, questions second**. The enhanced version uses multi-signal analysis, intent detection, and context awareness to minimize questions.

**Invoke**: `/article-craft:requirements`

---

## Smart Inference Engine

The inference engine analyzes multiple signal layers to determine article parameters:

### Layer 1: Topic Analysis (Intent Detection)

Before matching rules, first understand **what the user actually wants** by analyzing the topic structure:

| Input Pattern | Detected Intent | Why |
|--------------|---------------|-----|
| "写一篇关于 X" | tutorial | Generic request, default to tutorial |
| "X 快速入门" | quick-start | Explicit speed signal |
| "X 到底值不值" / "X 好不好" | comparison | Decision-making intent |
| "X 是怎么工作的" | deep-dive | Understanding intent |
| "我被 X 坑了" | pitfall | Negative experience, pain-first |
| "X vs Y" / "X 和 Y 哪个好" | comparison | Explicit comparison |
| "X 3.0 发布" / "X 新版本" | news | Release-focused |
| "为什么要用 X" | opinion | Questioning/argumentative |
| 完整句子描述场景 | experience | Story-driven, needs extraction |

**Topic Extraction**: If user provides a full sentence (e.g., "我想把项目的 Python 迁移到 uv"), extract the core topic ("uv") and intent (migration/experience).

### Layer 2: Keyword Signal Matching

Apply signal keywords to infer writing style, depth, and audience:

| Signal Keyword | Style | Depth | Audience |
|---------------|-------|-------|----------|
| "教程"、"指南"、"入门"、"实战"、"部署"、"学会"、"从零" | A | tutorial | beginner |
| "快速入门"、"5 分钟"、"十分钟" | A | overview | beginner |
| "分享"、"推荐"、"技巧"、"隐藏"、"N 个"、"你可能不知道" | B | tutorial | intermediate |
| "原理"、"源码"、"内核"、"底层"、"内部"、"如何实现" | C | deep-dive | advanced |
| "架构"、"设计模式"、"为什么这样" | C | deep-dive | advanced |
| "对比"、"评测"、"vs"、"选型"、"哪个好"、"值不值" | D | tutorial | intermediate |
| "更新"、"发布"、"新版本"、"changelog"、"3.0" | E | overview | intermediate |
| "复盘"、"踩坑"、"迁移"、"优化了"、"从 X 到 Y" | F | tutorial | intermediate |
| "为什么"、"我认为"、"不推荐"、"应该"、"别再" | G | tutorial | intermediate |
| "Bug"、"问题"、"故障"、"错误" | F | tutorial | intermediate |

### Layer 3: Context Awareness

Use the working environment to add context:

| Context Signal | Inference |
|--------------|-----------|
| Current dir is a code repo | Add repo-specific context |
| File path contains "02-技术/" | Knowledge base article, long-form |
| Recent git history shows X changes | Could be a "what changed" news article |
| User has written similar articles before | Suggest same style |

### Layer 4: Ambiguity Resolution

When multiple signals conflict, resolve with priority rules:

| Conflict | Resolution Rule |
|----------|-----------------|
| "Docker 深度教程" (C + tutorial) | Depth wins: deep-dive |
| "uv vs pnpm 对比" (D + tutorial) | Comparison wins: comparison |
| "Go 源码分析" (C + beginner signal) | Analysis wins: deep-dive, audience=advanced |

### Layer 4.5: WeChat Action Inference (NEW, v1.7+)

Infer the primary CTA action (`wechat_action`) based on style + intent. This is the field the write skill uses to select closing-CTA template from `references/writing-styles.md` § Closing Templates.

| Style / Intent | Default wechat_action | Why |
|---|---|---|
| Style A (教程) / B (经验分享) "N 个 XX" 型 | `collect` | 工具/命令清单读者会想收藏慢慢试 |
| Style B (经验分享) 非清单型 | `heart` | 经验分享适合点♡ / 在看 |
| Style C (深度长文) | `heart` | 深度内容适合点♡推荐 |
| Style D (评测对比) / E (资讯快报) | `share` | 选型/资讯转发价值最高 |
| Style F (项目复盘) | `comment` | 复盘话题开放讨论 |
| Style G (观点输出) | `comment` | 观点议题鼓励留言反馈 |
| Style H (爆料自媒体) | `share` | 爆料适合转发扩散 |
| Default | `heart` | 兜底 |

**Note**: User can override via frontmatter `wechat_action: <value>`. If frontmatter has explicit value, use that; otherwise inference applies.

**Why only one action**: Algorithm权重 + 实测 — 公众号读者对"一键三连"会全部忽略，单一引导转化率更高（详见 `wechat-push-mechanism-2026.md` §5.2，B 级实测经验）。

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

### Layer 5: Source Trust Detection (NEW)

**Automatically detect trusted sources for the topic** to help verify step:

```
Topic: "uv 包管理器"
    ↓
Query trusted sources:
    ↓
✅ https://docs.astral.sh/uv/          (T0 - Official docs)
✅ https://github.com/astral-sh/uv     (T1 - Official repo, 28k stars)
✅ https://astral.sh/blog/uv           (T2 - Official blog)
```

**Detection method:**
1. Use WebSearch to find official docs URL
2. Verify via GitHub API (stars, recency)
3. Classify into T0-T5 trust tier
4. Pass trusted sources to verify skill

**Detection command:**
```bash
# Find official docs
gh search repos "$TOPIC" --owner=TOPIC --limit=5 --json name,url,stargazerCount,pushedAt --jq '.[] | select(.stargazerCount > 100)'

# Or use WebSearch for official docs
WebSearch query: "$TOPIC official documentation site:docs.TOPIC.com OR site:TOPIC.com/docs"
```

**Why this matters:**
- Verify skill can skip link checking for T0/T1 sources
- Focus verification effort on lower-tier sources
- Article can cite authoritative sources with confidence

---

## Execution Flow

### Step 1: Parse Input & Extract Intent

1. **Clean the topic**: Remove filler words ("帮我写一个", "关于", "请教")
2. **Detect intent**: Apply Layer 1 rules
3. **Apply keyword signals**: Apply Layer 2 rules, collect all matches
4. **Check context**: Apply Layer 3 if applicable
5. **Resolve conflicts**: Apply Layer 4 rules

### Step 2: Build Inference Summary

After analysis, compile a summary showing **how each value was determined**:

```
## Inferred Requirements

| Field | Value | Confidence | Evidence |
|-------|-------|------------|----------|
| Topic | Docker 容器网络 | high | explicit |
| Style | A (教程) | high | keyword "部署" + intent "tutorial" |
| Depth | tutorial (2000-3000) | high | "教程" keyword |
| Audience | intermediate | medium | "教程" default + "Docker" assumed known |
| Intent | how-to guide | high | structure "X 怎么用" |

Confidence levels: high (clear signal), medium (inferred), low (guessing)
```

**Only show confidence levels** — don't ask about evidence.

### Step 3: Collaborative Confirmation (Single Question)

Show inferred values and ask **one confirmation question**:

```
Based on analyzing your topic, here's what I'll write. Confirm or adjust:

Topic: "Docker 容器网络" (intent: how-to guide)
Style: A 技术教程 (2000-3000 chars)
Audience: Intermediate
Images: Yes (placeholders)

[Looks good — start writing] (Recommended)
[Change style — currently A, want B/G/other]
[Change depth — currently tutorial, want overview/deep-dive]
[Change audience — currently intermediate]
[Let me specify manually]
```

**Why collaborative confirmation beats 5 questions**:
- User sees the full picture at once
- Can adjust any field without sequential questioning
- Clear evidence builds trust ("I saw '部署' in your topic")

### Step 4: Handle Adjustments

If user chooses to adjust a field:
- **Style change**: Show style options with brief descriptions
- **Depth change**: Show length implications
- **Manual input**: Collect all fields at once

### Step 5: Tone Resolution

Resolve the article's tone tier (`neutral` / `casual` / `opinionated`) using
three-tier precedence: CLI flag (`--tone=X`) > frontmatter `tone:` > writing-style default.

```python
from scripts.config import resolve_tone, STYLE_TO_TONE_DEFAULT

resolved_tone = resolve_tone(
    cli_tone=args.get("--tone"),                  # from orchestrator
    frontmatter_tone=existing_frontmatter.get("tone"),
    writing_style=writing_style_id,               # already determined above
)
```

Write the resolved value into article frontmatter as `tone: <value>` so
downstream skills (write / review / lint) can read it.

Write the resolved value into article frontmatter as `body_form: <value>` (default `wechat-native`) so downstream skills (write / review / publish) can read it.

**Why no user question**: writing-style is always determined by this point
(Step 1–4 guarantee it), so `STYLE_TO_TONE_DEFAULT` always resolves a valid tone,
even when CLI flag and frontmatter are both empty. The three-source-empty
branch is unreachable.

**If the user manually entered an invalid `tone:` in frontmatter** (e.g.
`tone: aggressive`), `resolve_tone()` silently degrades to the style
default. Print one warning line:

```
WARNING: invalid tone <bad> in frontmatter; using <resolved>
```

---

## Depth → Length Mapping

| Depth | Character Range | When |
|-------|-----------------|------|
| overview | 500-1000 | Explicit "快速", "概要" |
| tutorial | 2000-3000 | Default, no depth keyword |
| deep-dive | 4000+ | Explicit "深度", "原理", "源码" |

---

## Mode-Aware Behavior

| Mode | Skip Questions |
|------|---------------|
| `--draft` | Images → "none" |
| `--quick` | Images → "placeholders" |
| standard | Full inference |

---

## Enhanced Output

After inference + confirmation, output structured context for downstream skills:

```
## Collected Requirements

- topic: "Docker 容器网络"
- intent: tutorial
- style: A (技术教程)
- audience: intermediate
- depth: tutorial (2000-3000)
- visual_style: S2 (Isometric)
- keywords: ["Docker", "网络", "容器"]
- context: from_knowledge_base (detected 02-技术/)
- _confidence: high
- _inference_log:
    - "教程" → style A
    - "部署" → depth tutorial
    - intent "tutorial" → audience default intermediate
- wechat_action: heart  # CTA primary action: heart/share/collect/comment (Layer 4.5)
- body_form: wechat-native  # 正文形态: wechat-native (默认) | long-form (KB/博客长文)
- _trusted_sources:
    - url: https://docs.astral.sh/uv/
      tier: T0
      type: Official docs
    - url: https://github.com/astral-sh/uv
      tier: T1
      type: Official repo
      stars: 28000+
      updated: 2026
```

Then state: "Requirements collected. Proceeding to writing."

---

## Design Principles

- **Multi-layer inference**: Never trust a single signal — collect evidence from multiple layers
- **Intent-first**: Understand what the user wants before determining how to write it
- **Confidence transparency**: Show user how values were determined
- **One confirmation**: Collaborative confirmation beats multiple sequential questions
- **Context awareness**: Use environment to add relevant context
- **Default to tutorial**: When in doubt, default to tutorial style (most common for tech blogs)
- **Source trust detection**: Automatically find official docs/repo/blog for the topic
- **Trust-tier verification**: Pass trust-tier info to verify skill to focus verification effort
