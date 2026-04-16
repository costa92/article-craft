---
name: article-craft:write
version: 1.4.1
description: "Enhanced technical article writer with structure auto-check — generates articles with style guide, auto-validates section depth, and enforces code completeness."
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - AskUserQuestion
---

# article-craft:write — Technical Article Writer

Generate a complete technical blog article in Markdown/Obsidian format, with YAML frontmatter, callouts, code examples, and image placeholders.

---

## Inputs

This skill accepts context from two sources:

### A. Orchestrated mode (from article-craft:requirements)

When invoked by the orchestrator, the requirements skill passes structured context:

- **topic** — what the article is about
- **audience** — target reader profile (beginner / intermediate / advanced)
- **depth** — article length class (see Word Count table below)
- **key_points** — specific points to cover
- **save_path** — target file path (if determined)

Use all provided fields directly. Do not re-ask the user.

### B. Standalone mode (user invokes directly)

If no requirements context is provided, apply the same **smart inference** as the requirements skill:

1. Analyze the topic for writing style, depth, and audience signals (see `requirements/SKILL.md` inference rules)
2. If topic provides clear signals (e.g., "Docker 教程" → style=A, depth=tutorial, audience=intermediate), use defaults directly
3. Only ask if genuinely ambiguous — show inferred values and let user adjust in one confirmation question

### Word Count Reference

| Article Type | Character Range | Trigger Words |
|---|---|---|
| Quick start | 500-1000 | "快速入门" "quick start" "简短" |
| Tutorial | 2000-3000 | default |
| Deep dive | 4000+ | "深度" "详细" "全面" |

> Word count is guided by user choice. Never truncate content to fit a platform limit — if the user chose deep dive, write 4000+ characters.

---

## Writing Style Selection

文章有 7 种写作风格，根据内容类型自动选择或由用户指定。

**完整风格定义见：** `references/writing-styles.md`

| 风格 | 适用场景 | 关键特征 |
|------|---------|---------|
| **A: 技术教程** | 教程、指南、入门 | Callouts + 完整代码 + 对比表格 |
| **B: 经验分享** | 工具分享、技巧清单、"N个..." | 极短段落 + 口语 + 高频截图 |
| **C: 深度长文** | 原理解析、源码分析 | 长段论述 + 架构图 + 源码 |
| **D: 评测对比** | 产品对比、框架选型 | 多维度表格 + 基准数据 + 明确推荐 |
| **E: 资讯快报** | 新版本发布、更新解读 | 极简段落 + 截图 + 链接密集 |
| **F: 项目复盘** | 踩坑记录、架构演进 | 叙事驱动 + before/after 数据 |
| **G: 观点输出** | 技术观点、趋势判断 | 鲜明立场 + 论据充分 + 预设反驳 |
| **H: 爆料自媒体** | 公众号爆款、AI 发布爆料、竞争对垒 | 戏剧标题 + 钩子 H2 + 源图直引 + 必须 `_evidence.json` |

### 自动判断规则

| 内容信号 | 推荐风格 |
|---------|---------|
| "教程"、"指南"、"入门"、"实战"、"部署" | A |
| "分享"、"推荐"、"技巧"、"隐藏"、标题含"N个" | B |
| "原理"、"源码"、"架构"、"设计"、"底层" | C |
| "对比"、"评测"、"vs"、"选型"、"哪个好" | D |
| "更新"、"发布"、"新版本"、"changelog" | E |
| "复盘"、"踩坑"、"迁移"、"优化了"、"从X到Y" | F |
| "为什么"、"我认为"、"不推荐"、"应该" | G |
| "曝光"、"爆料"、"突袭"、"泄露"、"一夜"、"刚刚"、"硬刚"、"神仙打架"、股价/竞品对垒 | H |
| 来自 YouTube 视频转文章 | B |
| 默认 | A |

如果不确定，使用 AskQuestion 让用户选择风格。

**选定风格后，先读 `references/writing-styles.md` 中对应风格的完整规则，再开始写作。**

---

## Process

Follow these steps in order. Each step is mandatory unless marked optional.

### Step 1: Load Style Guide & Select Style

1. Read the style guide: `skills/write/style-guide.md`
2. Read the writing styles reference: `references/writing-styles.md`
3. **Determine the writing style** using the auto-judgment rules in the styles reference (or user specification)
4. Internalize the selected style's rules: opening pattern, section structure, image rhythm, tone, closing pattern

### Step 2: Determine Save Path

1. Check if the working directory contains an Obsidian knowledge base (look for `02-技术/` directory).
2. If found, auto-match a subdirectory under `02-技术/` based on the article's technology category.
3. If no match, `mkdir -p` to create the appropriate subdirectory.
4. If no knowledge base detected, save to the user's current working directory.
5. If a `save_path` was provided by the requirements skill, use that directly.

See `references/knowledge-base-rules.md` for the full directory mapping.

### Step 3: Generate Article Content

Write the full article using the `Write` tool — **NEVER just display content in chat**. The article must follow this structure:

#### 3a. YAML Frontmatter (required)

Every article must begin with complete YAML frontmatter:

```yaml
---
title: "文章标题（15-25 字，含核心技术关键词和读者收益）"
date: YYYY-MM-DD
tags:
  - tag1
  - tag2
  - tag3
category: 分类名称
status: draft
aliases:
  - 别名1
description: "120 字以内摘要，用作微信文章摘要。必须是有意义的概括，不能照搬标题。"
---
```

**Required fields**: title, date, tags, category, status, description.
**Optional fields**: aliases.
**Series fields** (auto-injected when writing as part of a series):
```yaml
series: "系列名称"
series_order: 2
series_total: 5
```

The `description` field is critical — it serves as the WeChat article summary and must be a standalone abstract (max 120 Chinese characters).

#### 3b. Title + Cover Image Placeholder

```markdown
# 文章标题

<!-- IMAGE: cover - 封面图描述 (16:9) -->
<!-- PROMPT: Minimalist technical illustration describing the concept, isometric view, tech blue palette, clean lines -->
```

#### 3b-series. Series Navigation (only if series context is provided)

If writing as part of a series, inject navigation **after the cover image and before the hook**:

```markdown
> [!info] 📚 系列导航
> 本文是《系列名称》系列第 X/Y 篇。
> 上一篇：[上一篇标题](./filename.md) | 下一篇：[下一篇标题](./filename.md)
```

- First article: omit "上一篇"
- Last article: change "下一篇" to "合集：[系列合集](./series-collection.md)"（if exists）
- Visual style prefix: read from series.md, use for ALL image prompts in this article

#### 3c. Opening Hook

**按选定风格的开头模式写开头。** 每种风格的具体开头模板见 `references/writing-styles.md`。

快速参考：
- **A 教程 / D 评测**：痛点 → 方案 → 本文价值（100 字内）
- **B 经验分享**：真实故事/场景切入 → 引出主题 → "话不多说，我们开始"
- **C 深度长文**：结论先行 → 为什么重要 → 本文结构预览
- **E 资讯快报**：一句话说清更新内容 → "快速过一遍"
- **F 项目复盘**：结果先行 → 之前的状况 → 本文讲什么
- **G 观点输出**：争议性结论直接抛出 → 简短说明

**所有风格都禁止的开头**:
- "在当今...的时代" / "随着...的发展"
- 以定义开头: "XXX 是一个..."
- 套路式提问: "你是否也有这样的困扰？"

#### 3d. Core Abstract Callout

**Style A / C / D** — after the hook, include:

```markdown
> [!abstract] 核心要点
> - Point 1
> - Point 2
> - Point 3
```

**Style B / E / F / G** — skip this callout,直接进入正文。

**Style H (爆料自媒体)** — 严禁 Obsidian callouts。替换为加粗【导读】块：

```markdown
##### 【新智元导读】太疯狂了！Anthropic 刚刚发布 XX 新版，上线神秘功能 YY……直接变身「云端员工」。更刺激的是，Opus 4.7 即将本周闪电发布。
```

导读必须：1-3 句、加粗 H5 标题、至少含 1 个爆点 + 1 个预告 + 1 个戏剧形容词（太疯狂/更刺激/直接变身）。

#### 3d-H. Style H 硬约束检查（仅 Style H）

写作**开始前**必须满足：

1. **`_evidence.json` 必须存在**（与 article.md 同目录 / 或 materials.md 同目录）
   - 不存在 → **BLOCK**，提示用户先跑 `/article-craft:evidence <materials.md>`
2. **至少 2 张可用证据图**（`sources[].images` 总数 + `manual[].path` 存在 ≥ 2）
   - 不足 → **BLOCK**，提示补 materials.md
3. **至少 1 条竞争/对手叙事素材**（`gated` 或 `sources` 中含竞品名 / 股价 / 对垒描述）
   - 不足 → 警告，允许继续但 review 会扣分

写作**中**消费 `_evidence.json`：

- **源图直引**：正文写 `<!-- HARVEST: <sources[i].url> idx=<N> caption="..." -->`
  screenshot skill 阶段会展开成 `![caption](远端 url)`
- **本地截图**：走标准 `<!-- SCREENSHOT: /abs/path caption="..." -->`
- **付费墙源**：不配图，用引用句式
  - `据 The Information 独家爆料，…`
  - `知情人士透露，…`
  - `泄露文件显示，…`

写作**结尾**必须：

1. `## 参考资料` 小节列出所有 `sources[].url`，按 tier 排序（T0/T1 官方在前）
2. 公众号三板斧：
   ```markdown
   **⭐点赞、转发、在看一键三连⭐**

   **点亮星标，锁定 [账号名] 极速推送！**
   ```

**Style H H2 钩子句检查**：每个 `## ` 标题必须满足以下至少一条，否则 review 会标记：
- 含感叹号或问号
- 含动词/动作（"直捅"、"闪电"、"变身"、"突袭"、"把活干了"）
- 含代号/数字/爆点（"两周前泄露的 KAIROS"、"Opus 4.7 本周上线"）

**禁止**（Style H 特有）：
- 学术收尾："综上所述"、"总的来说"、"值得注意的是"
- 客观中性 H2："功能介绍"、"使用方法"、"工作原理"
- Obsidian callouts（> [!note] 等全部禁用）
- blockquote（`>` 前缀除代码内引用外禁用）

#### 3e. Body Sections

> [!CRITICAL] 图表规则 — 写作时直接用 IMAGE 占位符，不要画 ASCII 图
>
> **绝对禁止在代码块中画**：架构图、流程图、对比表、时序图、拓扑图、目录树、决策树
> 使用 `│ ├ └ ┌ ─ → ← ▶ ▼` 等制表符/箭头拼的图**全部禁止**。
>
> **正确做法**：需要图表时，直接写 `<!-- IMAGE: name - 描述 (ratio) -->` 占位符，
> 由 images skill 生成专业图片。对比数据用 Markdown 表格（`| A | B |`），不要用 ASCII 框线表。
>
> **代码块只放可执行代码**：bash、yaml、go、python、json 等。

**结构增强：章节深度自动检查**

写作时，**每一章必须满足以下结构要求**：

```
## 章节标题
  ↓
内容（痛点/问题/背景）
  ↓
至少 2 个代码块
  ↓
解释/总结
```

| 结构元素 | 最低要求 | 示例 |
|---------|---------|------|
| 代码块 | ≥2 个/章 | 安装命令 + 运行示例 |
| 解释文字 | ≥2 段 | 每代码块前后说明 |
| 图片占位符 | 1 个/章 | 节奏图或架构图 |

**风格特定的章节结构**：

| 风格 | 最低代码 | 最低段落 | 图片 |
|------|---------|---------|------|
| A 教程 | 3 代码块 | 4 段 | 1 节奏图 |
| B 分享 | 1 代码块 | 2 段 | 截图优先 |
| C 深度 | 5+ 代码块 | 6+ 段 | 2 架构图 |
| D 评测 | 2 代码块 | 3 段 | 对比表+图 |
| E 资讯 | 1 代码块 | 2 段 | 截图 |
| F 复盘 | 2 代码块 | 3 段 | before/after |
| G 观点 | 1 代码块 | 3 段 | 1 数据图 |

**自动检查命令（写作时运行）**：

```bash
# 检查每个 ## 章节下的代码块数量
python3 -c "
import re, sys
content = open(sys.argv[1]).read()
sections = re.split(r'^## ', content, flags=re.MULTILINE)
for i, sec in enumerate(sections[1:], 1):
    title = sec.split('\n')[0][:50]
    blocks = len(re.findall(r'^```', sec, re.MULTILINE))
    print(f'Section {i}: {title}')
    print(f'  Code blocks: {blocks}')
    print(f'  Status: {"✅ PASS" if blocks >= 2 else "❌ FAIL - need " + str(2-blocks) + " more"}')
" article.md
```

**章节深度不足时的补救**：

如果某个章节代码块不足：
1. **添加命令示例** — `uv add requests` / `docker run ...`
2. **添加配置片段** — `pyproject.toml` / `docker-compose.yml`
3. **添加输出示例** — 命令输出结果
4. **添加对比代码** — 旧写法 vs 新写法

> [!tip] 不要等到 post-write validation 再检查 — 写作时实时保持结构完整，后续修复成本更高。

**按选定风格的章节结构写正文。** 每种风格的具体章节模板见 `references/writing-styles.md`。

各风格的核心差异：

| 风格 | 段落长度 | 代码风格 | 图表 | 语气 |
|------|---------|---------|------|------|
| A 教程 | 100-150字 | 完整可运行 | Callouts + 表格 | 专业 |
| B 分享 | 1-2句/段 | 只贴命令 | 截图高频 | 口语化 |
| C 深度 | 150-200字 | 源码片段 | 架构图 | 严谨 |
| D 评测 | 80-120字 | 配置示例 | 多维对比表 | 客观有态度 |
| E 资讯 | 1-3句/段 | 命令摘要 | 截图为主 | 简洁直接 |
| F 复盘 | 80-150字 | 关键变更 | before/after | 复盘冷静 |
| G 观点 | 100-150字 | 少代码 | 少图 | 自信不傲慢 |

**所有风格通用的代码规则：**
- 代码块最长 30 行（移动端阅读）
- 两个代码块之间至少 2-3 句解释
- 不贴与主题无关的样板代码

#### 3f. Image Placeholders

Insert image placeholders throughout the article. The `article-craft:images` skill will process these later.

**架构图、流程图、对比图、决策树等所有非文字内容都必须用 IMAGE 占位符**，不要用 ASCII 代码块画。

**完整风格指南见：** `skills/images/image-guide.md` 的 "Visual Style Guide" 部分。

**核心规则 — 设计 Token 一致性：**
1. 根据文章风格从 6 种视觉风格（S1-S6）中选择一种
2. 封面图的 PROMPT 确定**风格约束前缀**（色调 + 风格 + 背景）
3. 所有后续节奏图的 PROMPT **必须复用相同的风格约束前缀**
4. PROMPT 用英文写，结构：`[风格约束], [背景]. [主体内容], [细节]`

**Format**:
```markdown
<!-- IMAGE: name - description (ratio) -->
<!-- PROMPT: [style prefix from cover], [specific content for this image] -->
```

**Placement rules (by style)**:
- **Cover image**: all styles, immediately after `# Title`. Ratio: 16:9.
- **A 教程 / C 深度 / G 观点**: rhythm images every 400-600 words (Gemini 生成图)
- **B 分享 / E 资讯**: screenshots every 2-4 paragraphs (截图优先)
- **D 评测**: comparison charts and benchmark screenshots
- **F 复盘**: before/after data visualizations + architecture diagrams
- Use unique, descriptive names per image.
- **Do NOT place two images with the same purpose** in the same section.

**最低 AI 图片数量规则（强制，仅统计 IMAGE 占位符，不含 SCREENSHOT）**:
- 文章 ≤ 1500 字：cover 1 张即可
- 文章 1500-3000 字：cover + 至少 1 张节奏图 = 最少 2 张
- 文章 > 3000 字：cover + 至少 2 张节奏图 = 最少 3 张
- SCREENSHOT 占位符不计入此数量（截图由 screenshot skill 处理，与 AI 生成图独立）
- 节奏图应放在章节转换处（两个 `##` 之间），用于视觉分隔和概念可视化
- 如果文章有对比表格或架构描述，优先在这些位置插入节奏图

**Screenshot placeholders** (for referencing external content):
```markdown
<!-- SCREENSHOT: https://example.com -->
<!-- SCREENSHOT: https://example.com #selector -->
<!-- SCREENSHOT: https://example.com WAIT:3 WIDTH:800 -->
```
支持的选项：`#selector`（CSS 选择器）、`WAIT:N`（等待秒数）、`WIDTH:N`（视口宽度）。

> 截图原则：必须是文章直接引用的真实内容页面，避免装饰性截图。截图前会通过 HEAD 请求验证 URL 可用性，404 页面会被跳过。

#### 3g. Inline Reference Links

All reference links must use inline format at the point of first mention:

```markdown
See the [official documentation](https://example.com/docs) for details.
```

**NEVER** create a standalone "参考资料" or "参考链接" section at the end. The WeChat converter auto-generates footnote references from inline links; a manual section causes duplication.

**NEVER** use Obsidian wiki-style links: `[[Page Name]]` — always use standard Markdown `[Name](URL)`.

#### 3h. Closing Paragraph

**按选定风格的结尾模式收尾。** 每种风格的具体结尾模板见 `references/writing-styles.md`。

快速参考：
- **A 教程**：具体下一步操作（一条命令）
- **B 分享**："写在最后" + 情绪升华 + 互动号召
- **C 深度**：总结要点 + 延伸阅读
- **D 评测**：场景化推荐表格 + 个人选择
- **E 资讯**：值不值得升级 + 官方链接
- **F 复盘**：做对了/做错了/重来会怎么做
- **G 观点**：重申立场 + 承认局限 + 期待讨论

**所有风格禁止的结尾：**
- "希望本文对你有帮助"（Style B 的口语变体"希望能有点帮助。。"例外）
- 无上下文的模板化互动"如果有问题欢迎留言"

**系列文章结尾追加**（仅当 series context 存在时）：

在正常 closing paragraph 之后，追加下一篇预告：

```markdown
---

> [!tip] 📚 下一篇预告
> 《下一篇标题》— 下一篇的核心内容简介（1-2 句）。
```

- 最后一篇：改为系列回顾 + 合集链接

### Step 4: Apply Anti-AI Structure Rules + ASCII Diagram Auto-Detection

> [!CRITICAL] 禁用词列表 — 写作时主动避免，不要依赖事后检查
>
> **绝对禁止的词汇**：无缝、赋能、一站式、综上所述、总而言之、值得注意的是、不难发现、深度解析、全面梳理、链路、闭环、抓手、底层逻辑、方法论、降本增效、实际上、事实上、显然、众所周知、不难看出
>
> **绝对禁止的短语**：颠覆、极致、完美解决、"在当今快速发展的..."、"随着...的不断发展..."、"让我们一起探索..."
>
> **禁止的模板化摘要**："本文从...出发，完整拆解..."、"本文将详细介绍..."、"接下来我们将逐一..."
>
> **禁止的结尾**：希望本文对你有帮助、如果有问题欢迎留言、欢迎在评论区分享、点个在看、转发给朋友
>
> 遇到想用这些词的场景，用**具体数据、个人经历或直接行动指令**替代。

Before saving, verify the article does not read like AI-generated text AND detect ASCII diagrams:

#### 4a. ASCII Diagram Detection & Auto-Conversion (MANDATORY)

**ASCII 流程图/架构图绝对禁止（硬规则）：**

Never include ASCII diagrams in code blocks. All diagrams must be converted to image placeholders.

**自动检测规则：** 在保存前，扫描所有代码块（` ``` `）：

1. 使用 Grep 查找代码块内包含这些字符的行：`│ ├ └ ┌ ┐ ─ ▼ ▶ ← → ↑ ↓`
2. 对每个匹配行，检查是否是**可执行代码**（bash/python/json 等）
3. 如果不是可执行代码（例如：流程图、架构图、时序图），**立即转换为 IMAGE 占位符**

**转换步骤：**
```
被检测的 ASCII 图：
~~~
块设备 /dev/xvdf
    ↓ NodeStageVolume（格式化）
全局 staging 路径
    ↓ NodePublishVolume
Pod A 挂载路径
~~~

转换为：
~~~
<!-- IMAGE: name - 图的用途描述 (16:9) -->
<!-- PROMPT: [风格约束前缀], [具体描述 ASCII 图想表达的流程/架构] -->
~~~
```

**为什么强制转换？**
- ASCII 图在移动端渲染不佳，显示错位
- 无法应用文章的共享视觉风格
- AI 生成的图片质量更高，更专业

**检测命令（保存前运行）：**
```bash
grep -n '│\|├\|└\|┌\|┐\|─\|▼\|▶\|←\|→\|↑\|↓' article.md | grep '```' -A 10
```

如果有输出且不是可执行代码，**必须转换**。

#### 4b. Paragraph Structure Rules

**禁止 ASCII 流程图/架构图（硬规则）：**
- **绝不在代码块中画 ASCII 流程图、架构图、时序图、光谱图**（用 `│ ├ └ ┌ ─ ▼ ▶ ←→` 等制表符拼的图）
- 所有流程图、架构图、对比图、光谱图**必须使用 `<!-- IMAGE -->` 占位符**，由 images skill 生成图片
- 只有真正的**可执行代码**（bash/python/json 等）才允许放在代码块里
- 伪代码（如 `while True: ...`）是可以的，但如果它在描述一个流程/架构，优先用 IMAGE 占位符

**Paragraph structure variation**:
- Consecutive paragraphs must NOT repeat the same structure (e.g., "concept -> explain -> code" twice in a row).
- Mix structures: code-first then reverse explanation, Q&A style, experience-then-principle, comparison table then conclusion.

**Personal perspective** (at least 2 per article):
- Bug/pitfall experience: "我在迁移旧项目时发现——"
- Choice rationale: "选 uv 而不是 poetry 的原因很简单——"
- Judgement: "这个功能设计得很克制，只做了该做的事"
- Real benchmarks: "本机实测，冷启动 2.1 秒"

**Diverse paragraph openings**:
- Never start 2 consecutive paragraphs with "此外" / "另外" / "同时" / "值得注意的是".
- Replace transition words with direct content — jump straight to the next point.

### Step 5: Run Self-Check

Canonical source: **`${CLAUDE_PLUGIN_ROOT}/references/self-check-rules.md`**.

Read that file before saving. All 11 rule bodies, canonical grep patterns, and
auto-fix mappings live there — do not re-type them here.

**Write's ownership (per the "Who enforces what" matrix in rules.md):**

- **Pre-save GATE (must pass before Step 6 can save)**:
  - **Rule 1** — red-flag words: apply canonical auto-fix mapping inline
  - **Rule 2** — hook ≤ 100 chars: split if needed
  - **Rule 6** — chapter depth ≥ 2 code blocks per `##`: pad thin sections with
    real content (cost-comparison block, CLI example, config fragment). Never
    leave this for post-write validation
  - **Rule 11** — ASCII diagrams: **auto-convert** to `<!-- IMAGE: -->` +
    `<!-- PROMPT: -->` per the rules.md template. Re-grep until clean. Blocks
    save — see Step 6 GATE
- **Deferred to lint / review (do not duplicate here)**: rules 3, 4, 5, 7, 7b,
  8, 9, 10. Those are lint's or review Phase 1's job.

For the quick convenience sweep before Step 6, use the single combined grep in
the appendix of rules.md.

### Step 6: Save Article (GATE CHECK REQUIRED)

**BEFORE saving**，执行最后的 ASCII 图检查（强制性）：

```bash
grep -nE '│|├|└|┌|┐|─|▼|▶|←|→|↑|↓' article.md
```

**If any matches found**:
1. Verify each match is **executable code** (bash/python/json/etc.)
2. If any match is NOT executable code → **DO NOT SAVE YET**
3. Convert all ASCII diagrams to `<!-- IMAGE -->` placeholders
4. Verify again with the same grep command — **must return 0 results**
5. Only then proceed to save

Use the `Write` tool to save `article.md` to the determined path from Step 2.

Print the absolute file path after saving so subsequent skills can find it.

**Critical**: This GATE check is mandatory. If violations remain, the article cannot be saved. Inform the user and require fixing or conversion before saving.

### Step 7: Handoff Contract Validation (自动验证)

**文件保存后，立即运行自动化验证** — 这是交给 screenshot / images 前的 handoff 契约检查，确保下游 skill 能正确消费。

> **职责分工**:
> - write Step 7 **只检查下游 skill 的硬契约**(格式、占位符、命令正确性),即使被触发 review 也无法从格式层面修复的问题。
> - **内容质量规则**(红旗词、模板化句式、章节深度、结尾行动力等)由 `review` skill 的 Phase 1 (11 条 self-check rules) 统一执行,write 不再重复做。
> - 不要调用 `${CLAUDE_PLUGIN_ROOT}/scripts/review_selfcheck.py` —— 那是 review skill 内部使用的。

**必须检查的 3 项 handoff 契约（精简,只保留真正的下游阻断项）：**

1. **Check A（占位符格式）** — 如果发现非标准占位符（`IMAGE_PLACEHOLDER_*`、不存在的本地图片路径），转换为标准 `<!-- IMAGE: name - desc (ratio) -->` 格式。没转就跑 images 会直接 skip 这些位置。
2. **Check B（IMAGE 占位符双行格式）** ⭐ **CRITICAL** — 验证所有 `<!-- IMAGE:` 占位符匹配 images 脚本的正则格式。这是与下游 images skill 的硬契约，不通过会导致图片生成失败。

   ```
   <!-- IMAGE: slug - description (ratio) -->
   <!-- PROMPT: english prompt text -->
   ```
   正则: `<!--\s*IMAGE:\s*(.*?)\s*-\s*(.*?)\s*\((.*?)\)\s*-->(?:\s*|\n)*<!--\s*PROMPT:\s*(.*?)\s*-->`

   **自动修复规则：**
   - 缺少 `(ratio)` → 补 `(16:9)` 作为默认比例
   - 缺少 `<!-- PROMPT: -->` 行 → 根据 description 自动生成英文 PROMPT，格式为 `[visual_prefix]. [description translated to English]`
   - PROMPT 不是英文 → 翻译为英文
   - 两行之间有空行 → 删除空行使其紧邻

3. **Check C（命令可执行性）** — 验证文章中出现的命令是否正确可执行。这是唯一 review 不做的语义验证,属于 write 的责任。详见下方 "Check C 详解"。

**自动修复流程：**
```
保存文件
  ↓
inline Grep/Bash 检查 3 项 handoff 契约
  ↓
Check A 失败? → 转换为标准占位符格式 → 重新保存
  ↓
Check B 失败? → 补全 ratio/PROMPT/翻译 → 重新保存
  ↓
Check C 失败? → 标记 [需要验证] 或 Edit 修正 → 重新保存
  ↓
再次 grep 确认修复
  ↓
输出验证结果
```

**验证通过后输出：**
```
✅ Handoff Contract Validation PASSED
   Check A (占位符格式): 0 问题
   Check B (IMAGE 占位符双行格式): N 个，合规 ✅
   Check C (命令正确性): N/N ✅

   Content quality checks (red-flag words, anti-AI structure, chapter depth,
   closing cadence) are deferred to the review skill.
```

#### Check C: 命令验证详解

从文章中提取所有命令并验证正确性：

```bash
# 1. 提取所有代码块中的命令
python3 -c "
import re, sys
content = open(sys.argv[1]).read()
# 提取 bash/python/code 命令
commands = re.findall(r'\`\`\`(?:bash|python|sh)\n(.+?)\`\`\`', content, re.DOTALL)
for cmd in commands:
    print(cmd.strip())
" article.md
```

```bash
# 2. 验证每个命令（单独执行，不链接）
# 验证 install 命令
command -v gsd && gsd --version  # 验证 gsd 命令

# 验证 run 命令
command -v uv && uv --version  # 验证 uv 命令
```

**验证策略**：
1. 每个代码块单独验证（不链多个命令）
2. 验证命令存在性：`command -v TOOL` 或 `which TOOL`
3. 验证帮助信息：`TOOL --help` 或 `TOOL --version`
4. 记录验证失败的命令并修复文章

**失败处理**：
- 命令不存在 → 标记为 `[需要验证]`
- 命令参数错误 → 修正为正确格式
- 建议删除无法验证的命令

---

## Outputs

| Output | Description |
|---|---|
| `article.md` | Complete Markdown article saved to disk |
| **Printed path** | Absolute file path displayed in chat for the next skill |

---

## Hand-off

After writing and post-write validation are complete, hand-off depends on the pipeline mode:

**Standard / quick modes (orchestrated)**: the orchestrator handles the hand-off automatically — write just returns the article path, and the next stage runs.

**Draft mode** (`--draft`): do **NOT** auto-run images. Draft mode's contract is "content only, user decides when to resume." After saving, print this completion message:

```
✅ Draft saved: /ABSOLUTE/PATH/article.md
   Words: ~NNNN  |  Placeholders: N IMAGE, N SCREENSHOT

To resume and finish the article, run:
  /article-craft --upgrade /ABSOLUTE/PATH/article.md

This will detect what's missing (images, screenshots, review, publish)
and run only the stages that still need to run. You can safely edit
the article by hand between draft and upgrade.
```

**Standalone mode** (invoked via `/article-craft:write` outside orchestrator): also auto-run images after save (same logic as standard mode), unless the user explicitly said "no images" or "article only":

1. **检查是否有 IMAGE 占位符**：`grep -c '<!-- IMAGE:' /path/to/article.md`
2. **如果有占位符（count > 0）**，立即执行图片生成：
   ```bash
   # 探测可用模型
   BEST_MODEL=$(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_and_upload_images.py \
     --probe 2>&1 | grep "BEST_MODEL:" | cut -d: -f2)

   # 生成并上传图片
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_and_upload_images.py \
     --process-file /ABSOLUTE/PATH/article.md \
     --model $BEST_MODEL --continue-on-error --parallel
   ```
3. **如果探测失败**（所有模型不可用），保留占位符并告知用户
4. **如果用户明确说** "no images" 或 "article only"，跳过图片生成

---

## Standalone Mode Behavior

When invoked directly (not via orchestrator):

1. Use AskQuestion to collect topic, audience, and length if not provided.
2. Skip the requirements skill — go straight to writing.
3. After saving, **自动执行图片生成**（按 Hand-off 流程），不需要用户手动触发。
4. Provide a completion summary:

```
| Item | Value |
|---|---|
| File | /absolute/path/to/article.md |
| Words | ~NNNN characters |
| Images | N placeholders (cover + N-1 rhythm) |
| Status | draft — run article-craft:review for quality check |
```

---

## Style Guide Quick Reference

> The full style guide is at `skills/write/style-guide.md`. This section extracts the most critical rules.

### Title Formula

**按选定风格生成标题。** 各风格的标题模式见 `references/writing-styles.md`。

| 风格 | 标题模式 | 长度 | 示例 |
|------|---------|------|------|
| A 教程 | [量化]+[动作]+[技术词]+[收益] | 15-25字 | "5分钟用 Docker 部署你的第一个 Web 应用" |
| B 分享 | [分享/推荐]+[数字]+[好奇心] | 20-35字 | "分享10个你可能不知道的Claude Code隐藏命令" |
| C 深度 | [技术词]+[具体结果] | 15-30字 | "Go GC 调优：从 200ms 停顿降到 5ms" |
| D 评测 | [A] vs [B] — [维度] | 15-30字 | "Bun vs Deno vs Node.js 运行时终极对比" |
| E 资讯 | [产品]+[版本]+[N个亮点] | 15-30字 | "Claude Code 3.0：5个最值得关注的新功能" |
| F 复盘 | [我们如何]+[从X到Y] | 20-35字 | "我们如何将 API 响应时间从 2s 降到 50ms" |
| G 观点 | [为什么/不再]+[争议性结论] | 15-25字 | "为什么我不再推荐 TypeScript" |

### Readability Rhythm

- Paragraphs: max 150 characters, split if longer
- Between code blocks: at least 2-3 sentences of explanation (never two consecutive code blocks with no text between)
- Long sentences: max 60 characters, break if longer
- Insert a rhythm image every 400-600 words

### Forbidden / Allowed Content

**所有风格禁止：**
- "赋能" "颠覆" "极致" "一站式"
- "在当今快速发展的..." "综上所述..." "让我们一起探索..."
- "效率提升 300%" "彻底改变你的工作方式" "从入门到精通"
- 标题和章节标题中使用 emoji

**风格特定规则详见 `references/writing-styles.md` 最末"通用规则"部分。**

---

## Article Template Reference

A complete article template with all sections and placeholder patterns is at:

```
${CLAUDE_PLUGIN_ROOT}/skills/write/templates/article.md
```

Use it as a structural reference. Adapt sections to fit the specific article — not every section applies to every topic.

---

**Ported from:** article-generator v3.3 (Phase B + style guide + self-check rules)
