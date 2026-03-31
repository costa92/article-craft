---
name: article-craft:requirements
version: 1.1.0
description: "Gather article requirements through smart inference + minimal questions. Use before writing to clarify topic, audience, and depth."
---

# Requirements Gathering

Collect article requirements through **smart inference first, questions second**. Most requirements can be inferred from the topic and invocation context. Only ask when genuinely ambiguous.

**Invoke**: `/article-craft:requirements`

---

## Smart Inference Rules

Before asking any question, analyze the user's input for signals. Apply these rules to auto-fill fields:

### Topic → Writing Style (auto-detect)

| Signal in topic | Inferred style | Inferred depth | Inferred format |
|----------------|---------------|----------------|-----------------|
| "教程"、"指南"、"入门"、"实战"、"部署" | A (教程) | tutorial | standard |
| "分享"、"推荐"、"技巧"、"隐藏"、title contains "N个" | B (分享) | tutorial | listicle |
| "原理"、"源码"、"架构"、"设计"、"底层" | C (深度) | deep-dive | standard |
| "对比"、"评测"、"vs"、"选型"、"哪个好" | D (评测) | tutorial | comparison |
| "更新"、"发布"、"新版本"、"changelog" | E (资讯) | overview | standard |
| "复盘"、"踩坑"、"迁移"、"优化了"、"从X到Y" | F (复盘) | tutorial | standard |
| "为什么"、"我认为"、"不推荐"、"应该" | G (观点) | tutorial | standard |

### Depth → Length (auto-map)

| Depth | Length | Character range |
|-------|--------|-----------------|
| overview | short | 500-1000 |
| tutorial | medium | 2000-3000 |
| deep-dive | long | 4000+ |

No need to ask length separately — it follows from depth.

### Audience defaults

- If not specified: **intermediate** (covers most technical blog readers)
- If topic contains "入门" or "beginner": **beginner**
- If topic contains "源码" "原理" "内核": **advanced**

### Mode-aware skipping

| Mode | Skip questions |
|------|---------------|
| `--draft` | Images, Image style (draft has no image processing) |
| `--quick` | Image style defaults to "placeholders" |
| standard | Ask all applicable questions |

---

## Execution Flow

### Step 1: Analyze input and infer

Read the user's topic and any flags. Apply the inference rules above. Determine which fields are already known.

### Step 2: Confirm inferences or ask

**If topic provides enough signal** (e.g., "写一篇关于 uv 包管理器的技术教程"):
- Infer: style=A, depth=tutorial, length=medium, audience=intermediate, format=standard
- Show the inferred values and ask one confirmation question:

```
Question: "Based on your topic, here's what I'll write. Adjust if needed:"
Options:
  - Looks good — start writing (Recommended)
  - Change audience (currently: Intermediate)
  - Change depth (currently: Tutorial / 2000-3000 chars)
  - Let me specify everything manually
```

**If topic is ambiguous** (e.g., "写一篇关于 Docker 的文章"):
- Ask only the questions that cannot be inferred, one at a time
- Skip questions that have clear answers from context

### Step 3: Handle remaining questions (only if needed)

Only ask questions whose answers were NOT inferred. Follow this order:

**Q1: Depth** (only if ambiguous — no trigger words matched)

```
Question: "What depth do you want?"
Options:
  - Quick overview (500-1000 chars) — introduce the concept, basic usage
  - Tutorial (2000-3000 chars) — step-by-step with runnable code (Recommended)
  - Deep-dive (4000+ chars) — internals, performance, advanced patterns
```

**Q2: Audience** (only if ambiguous — rarely needed)

```
Question: "Who is the target reader?"
Options:
  - Beginner — detailed step-by-step, basic concepts explained
  - Intermediate — code examples and best practices (Recommended)
  - Advanced — architecture insights, performance analysis, edge cases
```

**Q3: Images** (skip in draft mode)

```
Question: "Do you need images?"
Options:
  - Yes — generate cover + rhythm images (Recommended for publishing)
  - Placeholders only — insert comments for later batch generation
  - No images — pure text
```

Image style is auto-selected based on writing style:
- Style A/C/G → S2 (Isometric) or S1 (Minimal Flat)
- Style B/F → S4 (Hand-drawn) or S5 (Data Viz)
- Style D → S5 (Data Viz)
- Style E → S1 (Minimal Flat)

No separate question needed.

---

## Output

After inference + optional questions, summarize:

```
## Collected Requirements
- Topic: [topic]
- Writing style: [A-G] ([name]) — [how it was determined: inferred/user-selected]
- Audience: [beginner/intermediate/advanced]
- Depth: [overview/tutorial/deep-dive] ([character range])
- Images: [yes/placeholders/none]
- Visual style: [S1-S6] ([name]) — auto-selected from writing style
```

Then state: "Requirements collected. Proceeding to writing."

---

## Design Principles

- **Infer first, ask second**: Most topics contain enough signal to skip 4-5 questions
- **One confirmation beats five questions**: Show inferred values, let user adjust
- **Respect the mode**: Draft mode should feel fast — minimal interaction
- **Contextual follow-ups**: Only ask what you genuinely don't know
- **No redundant axes**: Depth determines length; writing style determines format and visual style
