# Writing Style Guide — Technical Blog Edition

> Part of article-craft plugin
> For use by the `article-craft:write` skill. All rules below are mandatory.

---

## Scoring Optimization Rules (aligned with the `review` skill's 8-dimension scoring)

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

**Concrete evidence rules**:
- Every long article must contain at least 2 concrete anchors: measured numbers, command output, version numbers, file paths, error text, benchmark results, or before/after comparisons.
- Abstract judgement must be attached to evidence. Don't write "这个设计很优雅" alone; write "这个设计很克制：它只暴露 3 个命令，省掉了 poetry 那套多层配置。"
- At least 1 paragraph must explicitly state a tradeoff: what the tool does well, what it does poorly, or where you would not use it.

**Personal perspective insertion points** (at least 2 per article):
- Pitfall experience: "我在迁移旧项目时发现——"
- Choice rationale: "选 uv 而不是 poetry 的原因很简单——"
- Judgement: "这个功能设计得很克制，只做了该做的事"
- Real benchmarks: "本机实测，冷启动 2.1 秒"

**Diverse paragraph openings**:
- Never start 2 consecutive paragraphs with "此外" / "另外" / "同时" / "值得注意的是"
- Replace transition words with direct content: jump straight to the next point instead of "另外，还有一个功能..."
- Avoid repeated paragraph starters like "首先..." / "其次..." / "最后..." / "总的来说..." / "本质上..." / "从这个角度看...".

**Template-summary ban**:
- Do not write roadmap-style filler such as "本文将从 A、B、C 三个方面展开" / "接下来我们逐一来看" / "下面分别介绍".
- Do not use empty judgement wrappers such as "可以看到" / "不难发现" / "某种意义上" / "回到问题本身".
- If you want to summarize structure, compress it into one sentence with a real payoff: "后面我只看三件事：它快在哪、坑在哪、值不值得换。"

**Closing rules**:
- Forbidden: "希望本文对你有帮助" / "如果有问题欢迎留言"
- Good: end with a concrete next-step action: "装好 uv 后，在现有项目里跑一次 `uv pip install -r requirements.txt`，体感一下速度差异。"
- Good: end with a brief technical outlook (max 2 sentences): "uv 的 workspace 功能还在快速迭代，monorepo 支持值得关注。"

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

**朋友推荐适配（v1.7.1+，B 级官方间接）**:

依据：2025-03 微信团队**扩大**了对公众号信息流"朋友入口"的测试范围（腾讯新闻 2025-03-21 等多家媒体引用）。朋友推荐池的触发器是粉丝点 ♡ / 在看 / 转发 → 平台推送给该粉丝的好友。这是粉丝 <1000 的小号最重要的破圈通道。

**软约束**（不阻断，仅写作引导）：
- 标题应该让"粉丝的非技术好友也能 get 痛点"——纯技术术语标题在朋友推荐池里会被好友划过
- ❌ "LLM Wiki 三层架构：Raw层Wiki层Schema层设计详解"
- ✅ "我用半年整理的笔记系统，3 个反直觉决定让 AI 不再金鱼脑"
- 文末 CTA 应直接引导 ♡ / 在看 / 转发，而非仅"下一篇预告"（Rule 3 已强制）
- 文章开头 100 字内应有钩子（数字、反差、痛点），避免被系列骨架/导航占满

**不要做**（基于官方调研修正）:
- ❌ 不要在 SKILL.md 或 article 中写"朋友推荐占流量 45.9%"——这是 36 氪自报数据，**不是微信官方公开数字**
- ❌ 不要写"完播率有 1.3 倍流量加成"——无官方依据，CSDN 个人博客虚构
- ❌ 不要写"算法权重 40/30/20/10"——mp.weixin.qq.com 从未公开任何权重数字

官方一手依据：
- 微信珊瑚安全 2025-08-31 公告（多家媒体引用原文：财联社、光明网、腾讯新闻）
- 《微信公众号推荐运营规范》developers.weixin.qq.com/community/develop/doc/000cac23600b40d219814a85467809
- 2025-03 微信扩大朋友入口测试范围（腾讯新闻 news.qq.com/rain/a/20250321A05GDI00）

### WeChat 低质 / 合规硬约束（v1.10+，写作时贴在屏幕上）

对齐平台与国标后，`wechat-native` 正文还要避开这些**会被判低质或违规**的模式：

| 风险 | 要求 | 写作动作 |
|---|---|---|
| **低创作度 AIGC**（推荐规范：非真人自动化 / 空壳整理） | 主体内容须有作者实测、判断、可复现步骤 | ≥2 处第一人称踩坑；≥1 处本机命令输出；禁止纯文档搬运 |
| **AIGC 标识**（GB 45438-2025 + 珊瑚安全 2025-08-31） | 显式声明 AI 参与；禁止删改平台标识 | 文末脚注 `本文由 AI 辅助创作…`；发布时后台勾选「创作来源 → 内容由 AI 生成」 |
| **AIGC 反向声明**（Rule 23 error） | 禁止「纯人工 / 无 AI 生成」等伪造 | 绝不写反向声明 |
| **标题党**（推荐规范） | 禁止震惊体；标题宜 ≤28 字且兑现 | 痛点/数字/反差钩子；正文必须给到标题承诺 |
| **虚构数字**（Rule 24） | 无来源的「效率提升 300%」类 | 数字旁写环境与日期；估速标 `est.`；未跑的 bench 直说 |
| **空壳结构** | 手册十二章 + 大表连表 + callout 堆砌 | 3–6 个短节；少表；**无** `> [!abstract]`；段落 1–3 句 |
| **外链硬堆** | 公众号正文硬链体验差 | 行内 `[名](url)` 或「GitHub 搜项目名」；禁独立「参考资料」章 |

**去 AI 味（wechat-native 优先顺序）**：

1. 开场用**真实失败/选择**，不用「本文将从三方面展开」
2. 段落长短交错；禁止相邻两段同一句式（概念→解释→代码 连打）
3. 用「我这台机器 / 我核对过 / 老实交代没跑 bench」替代第三人称说明书
4. 工具对比只保留**读者会照着做的命令**，删掉百科式「维度大表」
5. 结语给**一条可复制命令**，不给鸡汤 CTA / 一键三连堆砌

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
- "首先/其次/最后" 三段式平铺
- "本文将..."、"接下来我们将..."、"下面分别..."
- "可以看到..."、"不难发现..."、"本质上..."、"从这个角度看..."

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
- "写在最后" as empty emotional outro (closing thoughts with no CTA) — prefer a concrete next-step heading like "下次 pull 之前"
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
- [ ] No "本文将/接下来/下面分别" style roadmap filler
- [ ] No repeated paragraph starters like "首先/其次/最后/另外"
- [ ] Emoji used sparingly, never in headings
- [ ] Image placeholders use CDN-ready format
- [ ] At least 2 personal perspective insertions
- [ ] At least 2 concrete anchors: numbers, versions, commands, paths, errors, or measured output
- [ ] At least 1 explicit tradeoff paragraph: where this tool is weak, costly, or not worth using
- [ ] No 2 consecutive paragraphs with identical structure
- [ ] Hook is within 100 characters
- [ ] Closing is a concrete action or brief outlook


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

### Style G + opinionated 加强模板（v1.7.3+，应对 4 篇实测全失败）

实测 4 篇已发布 Style G 文章在 review_selfcheck 上 **100% 失败** Rule 17
强观点 + Rule 22 主观判断——通用模板（"开篇抛出争议性结论 + 后文论据"）
不够具体，导致 LLM 写到结尾退化成中立技术教程。本模板给出可填空的句式，
让作者写作时直接套。

#### 个人经历句式表（每篇 ≥ 2 处，Rule 22 检查项）

按"锚点类型"组合，至少命中 2 种：

| 锚点类型 | 句式 | 例子 |
|---|---|---|
| **时间锚** | 我自己跑了 [X 时间] | "我自己跑了半年" / "去年 3 月..." / "前几个月..." |
| **项目锚** | 我做 X 时发现 Y | "我做 article-craft 时发现文档漂移..." |
| **失败锚** | 我试过 X，没跑通 | "我试过 LangChain 的 X，3 天没跑通" |
| **选择锚** | 我选 X 而不是 Y，因为 Z | "我选 uv 而不是 poetry，因为冷启动差 10 倍" |
| **数字锚** | 本机实测 [数] [单位] | "本机实测冷启动 2.1 秒" |

**4 篇实测反例**（A2 金鱼脑全文 0 个个人锚点）：

```text
❌ A2 现状（中立技术教程腔）:
   "每次 query 重新检索、知识不累积、判断不能持久。"

✅ 改成（加个人锚点）:
   "我自己跑过半年 RAG，最痛的就是这点——每次 query 重新检索，
    上次明明判断过的问题这次还得重新决策。"
```

#### 主观判断句式表（每篇 ≥ 1 处，Rule 22 检查项）

| 句式 | 适用场景 |
|---|---|
| "**我推荐 X 因为 Y**" | 推荐工具/做法 |
| "**我不用 Y 因为 Z**" | 反向推荐 |
| "**我觉得 X 就是 Y**" | 评价 |
| "**适合 X 的人是 Y，不适合的是 Z**" | 范围限定 |
| "**如果让我重做，我会 X 而不是 Y**" | 反思 |

**4 篇实测**：A1-A4 全部 **0** 处主观判断——这是 Style G 退化为技术教程的核心症状。

#### 强观点句式表（每篇 ≥ 1 处，Rule 17 检查项）

`STRONG_OPINION_PATTERNS` 在 `scripts/config.py` 定义，命中其一即可：

| 句式 | 例子 |
|---|---|
| **我赌 X 半年内会 Y** | "我赌两年内 pip 在新项目里基本看不见" |
| **我敢断言 X** | "我敢断言这条规则会越收越紧" |
| **别学 X / 别用 X / 别碰 X / 别信 X** | "别学那种'等出问题再说'的拖延" |
| **X 这玩意儿就是 Y** | "这设计就是错的——根本不解决问题" |
| **纯属 X / 纯纯** | "这套方案纯属为了卖工具" |
| **X 该退休了 / X 已经过时了** | "pip 该退休了" |
| **我的判断是 X** | "我的判断是这条规则 6 个月内会被收紧" |

#### 具体锚点句式（每章节 ≥ 1 处，Rule 5 反 AI 检查项）

`_has_concrete_anchor()` 在 `scripts/review_selfcheck.py:350` 定义，命中
其一即算锚点：backtick `..` / 版本号 `vX.Y.Z` / 路径 `/foo/bar` / 关键词
（报错/error/%/ms/MB/GB/警告码 等）。

每章节写完后过一遍：**有没有至少 1 段含命令/数字/路径/报错/实测结果**？没有
就补，否则 Rule 5 会标"连续 3 段缺锚点"。

#### 4 篇实测对照表（写作时贴在屏幕上）

| 维度 | A1 | A2 | A3 | A4 | 通过要求 |
|---|:---:|:---:|:---:|:---:|---|
| 个人经历 | 10 ✅ | **0** ❌ | 19 ✅ | 4 ✅ | ≥2 |
| **主观判断** | **0** ❌ | **0** ❌ | **0** ❌ | **0** ❌ | ≥1 |
| **强观点 sentence** | **0** ❌ | **0** ❌ | **0** ❌ | **0** ❌ | ≥1 |
| 第一人称密度/800字 | 3.1 ⚠️ | **0.0** ❌ | 3.3 ⚠️ | 0.4 ❌ | ≥6 |
| 总结腔短语 | 1 ❌ | 1 ❌ | 1 ❌ | 1 ❌ | =0 |

**主观判断 + 强观点 0/4 全失败**说明这是写作模板缺失导致的系统性偏差，
不是单篇运气问题。这个加强模板就是为了堵这个洞——写之前把句式表打开，
写完后过一遍每个表至少命中 1 个。
