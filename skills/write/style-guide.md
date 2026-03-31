# Writing Style Guide — Technical Blog Edition

> Part of article-craft plugin
> For use by the `article-craft:write` skill. All rules below are mandatory.

---

## Scoring Optimization Rules (aligned with content-reviewer 6-dimension scoring)

### Title Formula (Title & Hook dimension, target 9+)

**Hard rules**:
- Length: 15-25 characters (excluding punctuation)
- Must contain the core technology keyword
- Must promise a clear reader benefit (time commitment, outcome, pain point resolution)

**Formula**: `[Time/Quantity] + [Action] + [Tech Keyword] + [Benefit]`

| Type | Bad title | Good title |
|---|---|---|
| Quick start | "Docker 入门" (5 chars) | "5 分钟用 Docker 部署你的第一个 Web 应用" (19 chars) |
| Tutorial | "uv 使用教程" (6 chars) | "uv 实战教程：用 Rust 速度管理 Python 项目" (19 chars) |
| Deep dive | "Go 内存管理" (6 chars) | "Go GC 调优实战：从 200ms 停顿降到 5ms 的全过程" (22 chars) |

### Hook Opening (Title & Hook dimension, target 9+)

**The first 100 characters must contain three elements**: pain point/scenario -> solution -> reading value.

**Template A: Pain-point lead**
```
[Specific pain, 1-2 sentences] + [tool/solution name] + [one sentence on how it solves the problem] + [article scope]
```
Example: "pip 装包慢、venv 命令长、pyenv 配置烦——这三个痛点困扰 Python 开发者多年。uv 用一个二进制文件解决了全部问题。"

**Template B: Scenario lead**
```
[Real scenario the reader encounters] + [current approach weakness] + [this article's approach advantage]
```
Example: "团队里每个人的 Python 环境都不一样，requirements.txt 写了 200 行还是装不上。锁文件本该解决这个问题，但 pip 不支持。"

**Template C: Data lead**
```
[Counter-intuitive data/fact] + [why it's the case] + [what this article will show]
```
Example: "同一个项目，pip install 用了 45 秒，uv 只用了 2.1 秒——快了 20 倍。这不是营销数据，是我本机实测的结果。"

**Forbidden openers**:
- "在当今...的时代" / "随着...的发展"
- Starting with a definition: "XXX 是一个..."
- Engagement-bait: "你是否也有这样的困扰？"

### Anti-AI Structure Patterns (AI trace dimension, target 9+)

**Paragraph structure variation rules**:
- Consecutive paragraphs must NOT use the same structure. If the previous paragraph was "concept -> explain -> code", the next must use a different pattern.
- Available structures: code-first with reverse explanation, Q&A dialogue, experience-then-principle, comparison table then conclusion.

**Personal perspective insertion points** (at least 2 per article):
- Pitfall experience: "我在迁移旧项目时发现——"
- Choice rationale: "选 uv 而不是 poetry 的原因很简单——"
- Judgement: "这个功能设计得很克制，只做了该做的事"
- Real benchmarks: "本机实测，冷启动 2.1 秒"

**Diverse paragraph openings**:
- Never start 2 consecutive paragraphs with "此外" / "另外" / "同时" / "值得注意的是"
- Replace transition words with direct content: jump straight to the next point instead of "另外，还有一个功能..."

**Closing rules**:
- Forbidden: "希望本文对你有帮助" / "如果有问题欢迎留言"
- Good: end with a concrete next-step action: "装好 uv 后，在现有项目里跑一次 `uv pip install -r requirements.txt`，体感一下速度差异。"
- Good: end with a brief technical outlook (max 2 sentences): "uv 的 workspace 功能还在快速迭代，monorepo 支持值得关注。"

### Platform Adaptation Rules (Platform adaptation dimension, target 9+)

**WeChat Official Account adaptation**:
- `description` field required in frontmatter, max 120 characters, used as WeChat summary
- External links: use inline `[Name](url)` format (converter auto-extracts footnotes). In body text for WeChat-primary content, consider replacing with "参见文末链接" or search guidance.
- Individual code blocks: max 30 lines (mobile reading). Split longer code into multiple blocks with explanatory text between.
- Pure text passages must not exceed 800 characters without a figure/table/code block to break monotony.
- Heading levels: max 3 levels (##, ###, ####). Never use #####.

**Readability rhythm**:
- Paragraphs: max 150 characters, split if longer
- Between code blocks: at least 2-3 sentences of explanation. Never place two code blocks back-to-back without text.
- Long sentences: max 60 characters, break if longer
- Insert one rhythm image every 400-600 words (screenshot or AI-generated)

---

## Core Principle: Remove "AI Flavor"

### Forbidden Content

**1. Marketing-style writing**
- Emotional openers: "你是否也有这样的困扰？"
- Fake engagement: "欢迎在评论区分享" / "点个在看" / "转发给朋友"
- Marketing buzzwords: "赋能" / "颠覆" / "极致" / "一站式"
- Empty parallel sentences and vague superlatives
- Excessive emoji and exclamation marks

**2. AI generation traces**
- "在当今快速发展的..."
- "随着...的不断发展..."
- "让我们一起探索..."
- "综上所述..."

**3. False promises**
- "效率提升 300%"
- "彻底改变你的工作方式"
- "从入门到精通"

---

## Recommended Style

### 1. Article Structure

**YAML frontmatter** (required):
```yaml
---
title: 文章标题
date: 2024-01-25
tags:
  - tag1
  - tag2
category: 分类
status: draft
aliases:
  - alias1
description: "120 字以内摘要"
---
```

**Core structure**:
```markdown
# 标题

<!-- IMAGE: cover - 封面图 (16:9) -->
<!-- PROMPT: ... -->

> [!abstract] 核心要点
> Brief summary of core content

---

## Section 1

Content...

---

## Section N

Content...
```

### 2. Obsidian Callout Syntax

Use standard callout syntax, applied judiciously:

```markdown
> [!info] Information
> Content

> [!tip] Usage Tip
> Content

> [!warning] Warning
> Content

> [!note] Note
> Content

> [!success] Success Case
> Content

> [!abstract] Summary
> Content

> [!quote] Quote
> Content
```

### 3. Code Examples

**Must include**:
- Complete, runnable code
- Type annotations (where applicable)
- Comments for non-obvious lines
- Error handling

**Example**:
```python
def quick_sort(arr: list[int]) -> list[int]:
    """
    Quick sort implementation.

    Args:
        arr: List of integers to sort

    Returns:
        Sorted list
    """
    if len(arr) <= 1:
        return arr

    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]

    return quick_sort(left) + middle + quick_sort(right)
```

### 4. Technical Comparison Tables

**Use parameterized comparisons**, avoid subjective evaluation:

```markdown
| Dimension | Option A | Option B |
|---|---|---|
| **Cost** | Free | $10/month |
| **Latency** | < 100ms | 200-500ms |
| **Memory** | 8GB | 16GB |
```

### 5. Troubleshooting Format

**Use concrete diagnostic steps**:

```markdown
### Q1: Error message text

**Cause**: Specific root cause

**Fix**:
```bash
# Concrete command
command --option
```
```

---

## Article Structure Requirements

### Required Sections

1. **YAML frontmatter** (with description field)
2. **Title + cover image placeholder**
3. **Core summary** (callout)
4. **Technical explanation** (architecture/principles)
5. **Installation & configuration** (step-by-step, reproducible)
6. **Practical usage** (real code examples)
7. **FAQ** (common problems with solutions)

> Reference links are inlined throughout the body, NOT in a separate section.

### Optional Sections

- Performance optimization
- Advanced usage
- Use case analysis (suitable / not suitable)
- Comparative analysis

### Forbidden Sections

- "互动环节" (engagement section)
- "写在最后" (closing thoughts)
- "一句话总结" (one-line summary)
- "下期预告" (next episode preview)
- Standalone "参考资料" / "参考链接" section at the end

---

## Link Format Rules

### Correct: Inline Links

All reference links must be inlined at first mention using `[Name](url)`:

```markdown
Visit the [Ollama website](https://ollama.com) to download the installer.
See the [GLM4 GitHub repo](https://github.com/THUDM/GLM-4) for source code.
```

The WeChat converter auto-extracts these into footnote references at the bottom.

### Forbidden: Obsidian Wiki Links

```markdown
- [[Ollama 官方文档]]  — WRONG
- [[GLM4 使用指南]]    — WRONG
```

### Forbidden: Standalone Reference Section

```markdown
## 参考资料          — WRONG (causes duplication with converter output)
- **Name**: url      — WRONG
```

---

## Image Rules

### Placement

- **Cover**: immediately after the title (first image)
- **Architecture diagram**: in the technical explanation section
- **Flow diagram**: in the installation/configuration section
- **Comparison chart**: after performance/approach comparisons
- **Tutorial screenshots**: in the practical usage section

### Image Placeholder Format

```markdown
<!-- IMAGE: name - description (ratio) -->
<!-- PROMPT: Generation prompt in Chinese, simple and direct -->
```

### Rhythm

- 1 cover + 4-6 rhythm images per 3000-word article
- One rhythm image every 400-600 words
- Unique filenames per article (e.g., `ollama_cover.jpg`, `docker_architecture.jpg`)
- No two images with the same purpose in the same section

---

## Language Style

### Recommended

- **Direct statement**: "通过 Ollama 部署 GLM4 模型"
- **Technically precise**: "7B 参数，量化后 2.6GB"
- **Verifiable**: "延迟 < 100ms（测试环境：M1 Max）"
- **Pragmatic**: "适合处理公司内部代码"

### Avoid

- **Emotional**: "你是否也遇到过..."
- **Exaggerated**: "效率提升 10 倍"
- **Vague**: "大大提升了性能"
- **Filler**: "在实际应用中我们发现..."

---

## Pre-Save Checklist

Before saving the article, confirm:

- [ ] YAML frontmatter complete (including `description` field)
- [ ] Obsidian callouts used appropriately
- [ ] Code is complete and runnable
- [ ] Tables use measurable technical parameters
- [ ] All links are explicit inline links `[Name](url)`
- [ ] No standalone reference section at the end
- [ ] No fake engagement content
- [ ] No marketing fluff
- [ ] No AI boilerplate phrases
- [ ] Emoji used sparingly, never in headings
- [ ] Image placeholders use CDN-ready format
- [ ] At least 2 personal perspective insertions
- [ ] No 2 consecutive paragraphs with identical structure
- [ ] Hook is within 100 characters
- [ ] Closing is a concrete action or brief outlook
