---
name: article-craft:write
version: 1.10.0
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

### Fact source contract (v1.6.15+, MANDATORY)

When `<article_dir>/_extracted_facts.md` exists (produced by the
verify skill's Step 1.5), **that file is the primary fact source**.
Specifically:

1. **Cite figures, quotes, prices, and benchmark scores ONLY from
   `_extracted_facts.md`**. Do not pull these from WebSearch
   snippets, requirements skill summaries, or your own memory.
2. **If a "headline" figure (e.g., `"289 tokens/sec"`) is not in
   `_extracted_facts.md`, either omit it or hedge explicitly**
   (`"按 X 来源收集到的数据为 ..."`). Don't restate snippet-only
   facts as if they were authoritative.
3. The sidecar's "NOT present" markers (`Pricing: NOT listed in
   official blog`) are also signal — they tell you not to claim
   that figure is officially-disclosed.
4. WebSearch results may still inform narrative shape and section
   selection, but **specific quantitative claims must trace to a
   bullet in `_extracted_facts.md`**.

If `_extracted_facts.md` is missing (verify was skipped, or it's a
draft/quick mode run that bypasses verify), fall back to WebSearch
snippets with appropriate hedging — and **note in the article's
description frontmatter that facts were not vetted against official
sources**. This is intentional friction so unverified facts get
flagged at write time, not after publish.

The historical motivation: a v1.6.13 e2e test article shipped two
facts (`"289 tokens/sec"`, specific pricing) that didn't appear in
**any** T0 source when audited post-write. The cause: write was
citing from WebSearch snippets, and verify only did URL HEAD
checks. The sidecar contract closes that gap.

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

### Step 1.5: Generate 3 Title Candidates (v1.7+, variant A/B for WeChat)

After determining style + topic, **generate 3 title candidates** representing different hook types, then use `AskUserQuestion` to let the user pick. This is a variant A/B testing mechanism — WeChat 公众平台 doesn't support native A/B testing, so we surface hook diversity at write time.

**Each candidate must命中 a different hook type** from Rule 19:

| Candidate | Hook Type | Example |
|---|---|---|
| **A** | 数字钩子 + 工具名 | `5 分钟用 Docker 部署你的第一个 Web 应用` |
| **B** | 反差/悬念钩子 | `为什么我不再用 docker-compose（实测后的反思）` |
| **C** | 痛点/故事钩子 | `踩了 3 次坑后，我用 Docker 重写了部署流程` |

**所有候选标题必须满足**：
- 长度 ≤ 28 字（推荐）/ ≤ 64 字（硬上限）
- 不含黑名单词（震惊/重磅/解密 等）
- 至少 1 个钩子类型命中（数字/反差/痛点/故事/悬念）

**AskUserQuestion 格式**：

```
Question: "选择文章标题（3 个候选，分别走不同钩子路径）"
Options:
  - A: <数字钩子标题>  — 适合教程/工具清单（CTR 稳定）
  - B: <反差钩子标题>  — 适合观点/经验（点击率高但筛选读者）
  - C: <痛点钩子标题>  — 适合避坑/故事型（情绪驱动）
  - Other: 用户手工输入
```

将用户选中的标题写入 frontmatter `title:` 字段。

**例外**：
- 当 `body_form: long-form`（含 legacy `wechat_target: false` 别名）时，跳过此步骤，直接用单一标题
- 当 requirements 由 orchestrator 预解析、或在非交互场景运行（autonomous / scheduled / `--series` 批量）时，**跳过 AskUserQuestion**，直接选用推荐的数字钩子标题（A 候选）写入 `title:`——中途交互会打断自动化运行（见 orchestrator 的 no-interactive-prompt 原则）
- Style H (爆料自媒体) 必须命中 H 的戏剧化标题公式（"刚刚"/"突袭"/"硬刚"），3 候选都走戏剧化变体即可

### Step 2: Determine Save Path

1. If a `save_path` was provided by the requirements skill, use that directly. **Skip the rest of this step.**
2. Check if the working directory contains an Obsidian knowledge base (look for `02-技术/` directory).
3. **Before guessing a subdirectory, list what actually exists** — don't fabricate paths:
   ```bash
   ls "02-技术/" 2>&1 | sort
   # And for AI-related articles, drill one level deeper:
   ls "02-技术/AI-生态/" "02-技术/AI工具/" 2>&1 | sort
   ```
   This catches the common failure of asking the user "save to `02-技术/AI 应用/`?" when that
   directory doesn't exist and the real home is `02-技术/AI-生态/Claude-Code/`. When presenting
   path options to the user via AskUserQuestion, **every option must be a path that returned
   from `ls`** (or one you'll create with `mkdir -p` and explicitly say so).
4. Auto-match a subdirectory using `references/knowledge-base-rules.md` (the canonical mapping
   table — Claude Code → `02-技术/AI-生态/Claude-Code/`, RAG → `02-技术/AI-生态/RAG/`, etc.).
5. If no exact match in the table, pick the closest existing parent and `mkdir -p` the new
   subdir (announce the new directory creation in chat).
6. If no knowledge base detected at all, save to the user's current working directory.

See `references/knowledge-base-rules.md` for the full directory mapping.

### Step 3: Generate Article Content

Write the full article using the `Write` tool — **NEVER just display content in chat**. The article must follow this structure:

#### 3a. YAML Frontmatter (required)

Every article must begin with complete YAML frontmatter:

```yaml
---
title: "文章标题（15-25 字，含核心技术关键词和读者收益）"
date: YYYY-MM-DD
author: 作者名
tags:
  - 中文标签1     # ≥3 个 tags 且 ≥3 个中文 tag (Rule 4 硬约束)
  - 中文标签2     # 每个中文 tag 至少含 2 个中文字符
  - 中文标签3     # 示例: [Kubernetes, Docker, 容器运维, AI工具, 实战教程]
category: 分类名称
status: draft
aliases:
  - 别名1
description: "120 字以内摘要，用作微信文章摘要。必须是有意义的概括，不能照搬标题。"
---
```

**Rule 4 tags 硬约束（v1.7.4+，基于 4 篇实测全失败的补救）**：

| 要求 | 检测 | 不达标后果 |
|---|---|---|
| `tags` 至少 3 个 | `len(tags) >= 3` | 看一看 NLP 标签匹配长尾推荐池命中率拉低 |
| 中文 tag 至少 3 个 | 每个 tag 含 ≥ 2 个中文字符的数量 ≥ 3 | 公众号读者 99% 中文用户，全英文 tags（如 `[MCP, AI, DevOps]`）让 NLP 算法无法匹配中文兴趣画像 |

**禁用模式**：

- ❌ `tags: [MCP, AI, DevOps]` — 全英文，中文 tag = 0
- ❌ `tags: [Kubernetes, Docker]` — 仅 2 个 tag
- ❌ `tags: [AI, K8s, Go]` — 短到无 NLP 信号

**推荐模式**（中英混合 + 长尾）：

- ✅ `tags: [Kubernetes, Docker, 容器运维, AI工具, 实战教程]`
- ✅ `tags: [LLM, Claude Code, AI写作, article-craft, 调研做法]`
- ✅ `tags: [Python, uv, 包管理, 工具链迁移, 实战]`

4 篇实测全部因 tags=2、中文 tag=1 命中 Rule 4 失败——这条硬约束在 write 阶段就要满足，不要等 publish 自检后回补。

**Resolving `author`:** at write time, fill the field from
`config.author_name()` — that resolves env.json `user_name` first, then
`git config user.name`, then `"Anonymous"`. One-liner:

```bash
AUTHOR=$(python3 -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts'); from config import author_name; print(author_name())")
```

Without `author` in frontmatter, downstream skills (e.g. share_card)
auto-skip because they detect "missing required field".

**Required fields**: title, date, author, tags, category, status, description.
**Optional fields**: aliases.
**WeChat fields** (v1.7+, optional but recommended for WeChat-targeted articles):
```yaml
wechat_action: heart  # CTA primary action: heart|share|collect|comment
                      # heart    — 点♡/在看（默认；干货分享类）
                      # share    — 转发到群/朋友圈（评测/资讯）
                      # collect  — 收藏（清单/工具/命令大全）
                      # comment  — 留言互动（观点/复盘）
```
inherits from requirements skill's Layer 4.5 inference, or user-specified.
**Series fields** (auto-injected when writing as part of a series):
```yaml
series: "系列名称"
series_order: 2
series_total: 5
```

The `description` field is critical — it serves as the WeChat article summary and must be a standalone abstract (max 120 Chinese characters).

#### 3a.5: Tone-aware prompt augmentation

After loading the base style guide, read `tone:` from frontmatter (it was set in requirements). Then **append** the matching section from `style-guide.md`:

- `tone: neutral`     → append `## Tone: neutral` section
- `tone: casual`      → append `## Tone: casual` section
- `tone: opinionated` → append `## Tone: opinionated` section + `### Style G + opinionated 加强模板` section (v1.7.3+)

If no `tone:` in frontmatter, default to `neutral`.

Each tone section contains: register guidance, sample paragraphs at the chosen tier, and replacement-map examples. The writer should follow the sample register, not just consume the rules verbatim.

**同时注入 Body Form 形态规则**：从 `style-guide.md` 读取 `## Body Form: wechat-native`
段，按已解析的 `body_form` 字段应用对应列的规则到正文写作上下文：
- `wechat-native`（默认）：短段（≤~200 字）、强冷开场、**禁用 Obsidian callout**（改 bold 引导句 / 单行 `>` 引用）、标题 ≤2 级、章节少而利落、每 ~600 字一个视觉物、单主线。
- `long-form`：今天的行为（callout 允许、深章节），用于 KB/博客副本。
`body_form` 缺失时按 `wechat-native` 处理。

**v1.7.3+ Style G + opinionated 加强约束**：当 `tone: opinionated`（Style G/H 的默认值）时，**额外加载**`style-guide.md` 的 `### Style G + opinionated 加强模板` 章节——这是基于 4 篇实测文章 100% 失败 Rule 17/22 的针对性补救，包含：

- **个人经历句式表**（≥ 2 处）：时间锚 / 项目锚 / 失败锚 / 选择锚 / 数字锚
- **主观判断句式表**（≥ 1 处）：我推荐 X 因为 Y / 我不用 Y 因为 Z 等
- **强观点句式表**（≥ 1 处）：我赌 / 我敢断言 / 别学 / 这玩意儿就是 等（命中 `STRONG_OPINION_PATTERNS`）
- **具体锚点句式**（每章节 ≥ 1 处）：命令 / 数字 / 路径 / 报错码

写作时把这些表打开作为填空模板，每章节 / 整篇至少命中 1 次相应表。如果 review 阶段 Rule 17/22 仍报 0，**说明加强模板没被实际消费**——回到 Step 3 重写，不是修小。

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

> **形态条件**：上面的 `> [!info]` callout **仅在 `body_form: long-form` 下使用**。
> 在 `body_form: wechat-native`（默认）下公众号不渲染 Obsidian callout，改用纯文本：
> ```markdown
> **📚 系列导航**：本文是《系列名称》第 X/Y 篇。上一篇：[标题](./f.md) ｜ 下一篇：[标题](./f.md)
> ```

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

> **形态条件**：以下 callout（`> [!abstract]` 等）规则**仅在 `body_form: long-form` 下生效**。
> 在 `body_form: wechat-native`（默认）下，公众号不渲染 Obsidian callout —— 改写成
> **bold 引导句**（`**一句话重点**`）或单行 `>` 普通引用，不要用 `> [!type]` 语法。

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
##### 【XX 媒体导读】太疯狂了！Anthropic 刚刚发布 XX 新版，上线神秘功能 YY……直接变身「云端员工」。更刺激的是，Opus 4.7 即将本周闪电发布。
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

写作**前**读菜单（v1.4.11+，替代凭记忆猜 idx）：

**优先**读同目录的 `_harvest_menu.md`（evidence.py 自 v1.4.12 起自动生成）：

```bash
cat /ABSOLUTE/PATH/_harvest_menu.md
```

**如果菜单文件缺失**（兼容旧版或手动生成 evidence 的情况），回落到命令行生成：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/screenshot_tool.py harvest-menu \
  --evidence /ABSOLUTE/PATH/_evidence.json
```

菜单会列出每个源的 **cover 是否可用**、每张 filter 后图片的 `(idx, 尺寸, 格式,
alt 片段)` 表格、付费墙源的 cite-only 清单、本地截图的 SCREENSHOT 占位符示例。
**picking idx 必须照菜单，不要靠记忆数源页。** 菜单里的 `idx` 和
`expand-harvest --dry-run --strict` 验的 idx 是**同一个序号**。

典型消费方式：

- 给文章取 cover → 若菜单说 "cover: available ✅"，直接抄样例
- 挑"Claude Code 并行界面"这种主图 → 扫菜单的 `dim` 列找最大的 png/jpg
- 想配动图 → 筛菜单的 `fmt=gif` 行
- 注意：WeChat 源的 `alt` 基本都是"图片"，**不要**用 `alt="..."` 匹配，用 `idx=`

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

> **body_form 优先级高于风格模板的 callout。** `references/writing-styles.md` 里各
> 风格的章节模板会内嵌 Obsidian callout（如 Style A 的 `> [!info]`、Style D 的
> `> [!tip]`、Style F 的 `> [!warning]`）。在默认的 `body_form: wechat-native` 下，
> 上面第 286 行的「禁用 Obsidian callout」对**所有**这些章节 callout 同样生效——一律
> 改写成 bold 引导句 / 单行 `>` 引用，不只是摘要 callout。仅在 `body_form: long-form`
> 下才保留原样的 callout。下表「图表」列里的「Callouts」同理受此约束。

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

**核心规则 — 设计 Token 一致性 (v1.4.19 — 锁感觉,不锁画面):**
1. 根据文章风格从 9 种视觉风格(S1-S9)中选择一种；**逻辑/关系/结构图（流程图、框架图、关系图、思维导图、架构图）统一用 S2 手绘信息图海报**；**讲"它怎么运作"（how-it-works / Agent 系统 / 数据流转 / 拟人叙事）用 S9 卡通讲解漫画（须 `--model gemini-2.5-flash-image`）**
2. 封面图的 PROMPT 确定**风格约束前缀**(色调 + 风格 + 背景)
3. 所有后续节奏图的 PROMPT **必须复用相同的风格约束前缀**(全篇感觉一致)
4. **不要手动加 `Camera:` / `Composition:`** — `scripts/generate_and_upload_images.py`
   的 `vary_prompt_for_position()` 按图片位置自动注入不同镜头和构图,
   4 张图自然拉开画面差异。详见 `skills/images/image-guide.md` § 镜头/构图轮转表
5. PROMPT 用英文写,结构:`[风格约束], [背景]. [主体内容], [细节]`

**Format**:
```markdown
<!-- IMAGE: name - description (ratio) -->
<!-- PROMPT: [style prefix from cover], [specific content for this image] -->
```

**⛔ 硬禁止：PROMPT 里绝对不能要求 Gemini 渲染任何可读文字**

> **唯一例外 = S2 手绘信息图海报**：逻辑/关系/结构图用 S2 时，信息图本质是**带标签**的，
> 允许**英文短标签**（1–3 个英文词，如 `Input`/`Parser`/`Cache`），`check_rule_16` 按 S2 风格签名豁免英文标签告警。
> 四条底线：① **英文 only，不写中文**——CJK 对 S2 也照拦（中文任何模型都糊）；② 只放短标签，绝不渲染整句；③ **带标签的 S2 图用 `--model gemini-2.5-flash-image`**——默认 minimax 文字保真度随密度反相关，面板多 + 箭头注文就糊（2026-06-04 dogfood 实证），gemini 即便密集也渲清；箭头只连线不写字；④ 版本号/品牌名/精确数字这类错不起的文字仍走截图或表格。详见 `image-guide.md` S2 段「📝 文字例外」。**以下禁文字规则适用于 S2 以外的所有风格。**

Gemini 的图像模型**无法稳定渲染中文汉字**（会变形、缺笔、拼错），英文短标签也不可靠。这是一条**必须在写 prompt 阶段就生效**的硬约束，否则图生成之后你必须重跑一遍。

- ❌ `PROMPT: ... 顶部大字 "2026 年报告" ...`
- ❌ `PROMPT: ... menu showing "招牌菜 ¥68 / 小炒肉 ¥48" ...`
- ❌ `PROMPT: ... calligraphy scroll with characters "静" ...`
- ❌ `PROMPT: ... magazine cover with title "VOL.08 慢生活" ...`
- ❌ `PROMPT: ... poster with Chinese headline "越界" ...`
- ✅ `PROMPT: ... silhouette of a menu showing price-column layout lines and food-icon shapes. No text, no letters, no numbers, no labels ...`

**每条 PROMPT 末尾都应该加这一行硬约束**（如果风格允许）：

```
No readable text anywhere, no letters, no numbers, no labels, no captions, no logos.
```

**"自证悖论"特别警告**：当文章讨论"某模型的文字渲染能力"（例如 GPT-Image-2、nano-banana、Imagen 的文字准确率）时，**绝对不能**用 `<!-- IMAGE: -->` + Gemini 生成示意图去"展示"那个模型的文字效果——你是在用一个不擅长渲染文字的模型证明另一个模型擅长渲染文字，视觉上自相矛盾。这类场景必须：
1. 用 `<!-- SCREENSHOT: -->` 截取真实模型的输出页
2. 或让作者人工插入真实截图 URL（`![](https://your-cdn.example.com/img/xxx.png)`，把 `your-cdn.example.com` 换成你自己的 CDN，并确保它在 `~/.claude/env.json` 的 `verify_cdn_whitelist` 里）
3. 或用 Markdown 表格替代（`| 旧版 | 新版 |`）
4. 或写纯抽象示意图（剪影、色块、图标组合，无可读字符）

完整规则见 `skills/images/image-guide.md` 的 "Prompt 写作规则" 第 5-6 条。

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

**何时发射 SCREENSHOT 占位符（emission triggers — 必读）**

写作过程中**只要命中下列任一信号**，就必须在相应位置发射一个 `<!-- SCREENSHOT: url -->` 占位符，**选择器能选尽选**（见下面推荐选择器表）。不发射 = screenshot stage 沉默跳过 = 文章少了关键证据。

| 触发信号 | 发射位置 | 示例 |
|---------|---------|------|
| **外链引用 + 内容型页面**（文章 inline 引用了一个 README / 文档 / 推文 / SO 回答 / npm 页 / 产品界面） | 引用句所在段落**紧随其后** | `[ripgrep README](https://github.com/BurntSushi/ripgrep)` 引用后追一个 `<!-- SCREENSHOT: https://github.com/BurntSushi/ripgrep #readme -->` |
| **社交平台帖子**（Twitter/X、小红书、微博、Threads、Reddit、HN 评论） | 引用句下一行 | `<!-- SCREENSHOT: https://x.com/user/status/123 [data-testid="tweet"] -->` |
| **工具/框架介绍**（整篇或某节主角是一个开源项目、CLI、SaaS 产品） | 首次介绍段之后 | GitHub 仓库首页、官网首屏 |
| **教程中的真实运行结果**（文章描述"跑了某命令出了这个界面"/"后台仪表盘显示…"/产品 UI 流程） | 描述那一段之后 | 终端截图、仪表盘截图、UI 流程截图（URL 必须真实可达） |
| **评测/对比**（Style D 引用的 benchmark 页、跑分页、排行榜、第三方评测文章） | 引用句之后 | 官方性能报告页、基准测试仓库 README |

**反向规则（何时不要发射）：**
- ❌ **已经有 HARVEST 占位符覆盖同一 URL**（Style H 专用）——HARVEST 是源图再用，不要再叠 SCREENSHOT
- ❌ **付费墙 / 登录墙 / 需认证的页面**（Medium 付费文、LinkedIn 内页、私有 Slack 链接等）——screenshot skill 只能抓公开可达页
- ❌ **"提了一下"类的弱引用**（比如"React 生态很成熟"这种带过 `https://react.dev` 的句子）——只有当 URL 是信息核心时才截
- ❌ **装饰性截图**（"放张图感觉漂亮点"）——规则在本文件更下方 "截图原则" 那条已明确

**自检口诀**：每写完一段就问自己 "这段引用了外部 URL 吗？是内容型页面吗？" 答 yes+yes 时必须有对应的 SCREENSHOT 占位符紧随引用。

完整的按风格发射建议，见 `references/writing-styles.md` 各风格小节（指针而非复述）。

---

**Screenshot placeholders 语法**（for referencing external content）:
```markdown
<!-- SCREENSHOT: https://example.com -->
<!-- SCREENSHOT: https://example.com #selector -->
<!-- SCREENSHOT: https://example.com WAIT:3 WIDTH:800 -->
<!-- SCREENSHOT: https://example.com ANCHOR:keyword1,keyword2 -->
<!-- SCREENSHOT: https://example.com FOLD -->
```
支持的选项：`#selector`（CSS 选择器）、`WAIT:N`（等待秒数）、`WIDTH:N`（视口宽度）、`ANCHOR:k1,k2`（**v1.5.3+** 关键词锚点：scroll 到第一处出现 k1/k2 的元素再截）、`FOLD`（**v1.5.3+** 仅截首屏 ~800px）、`MAX_HEIGHT:N`（**v1.5.3+** 自定义高度上限，默认 900）。

**默认带 `ANCHOR:` 是强烈推荐做法（v1.5.3+）** — 一个 SCREENSHOT 占位符通常是为了证明前后段落里讲的某件事。把那段在讲的核心词当 ANCHOR 写进去，截图就会从相关段落开始而不是页面顶部。例：

> 我自己觉得这是 Hindsight 工程上最有意思的一块。TEMPR 用四路并行检索…
> <!-- SCREENSHOT: https://github.com/vectorize-io/hindsight ANCHOR:TEMPR -->

如果一段引用本来就在讲整个项目（"我们看一下 X 项目的 README"），不带 ANCHOR 也合理（默认从顶部截）。但只要段落主题更细，**第一选择是写 ANCHOR**，第二选择才是 `#selector`，最次才是裸 URL。

**常见 URL 的推荐选择器（不写则退为视口截图，写了则精准裁剪）：**

| URL 类型 | 推荐选择器 | 效果 |
|---------|-----------|------|
| GitHub 仓库首页 (`github.com/user/repo`) | `#readme` | 只截 README，不含侧边栏 |
| GitHub 文件/代码 (`/blob/`) | `.highlight` | 代码高亮区域 |
| GitHub Issue/PR | `#repo-content-pjax-container` | 正文 + 评论 |
| 文档站主页 (`docs.*` / `*/docs/` / `official.`) | `article, main` | 主内容区，去掉导航栏 |
| Twitter/X 推文 | `[data-testid="tweet"]` | 单条推文卡片 |
| Stack Overflow 问题 | `#question` | 题目 + 最佳答案 |
| npm 包页面 | `.npm__container` | 包信息主体 |

**原则**：写截图占位符时**优先加选择器**，确保截到关键区域而不是整页滚动视图。没有合适选择器时，脚本默认截视口高度内容（不滚动），相当于"首屏截图"。

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
- **B 分享**："写在最后" + 情绪升华
- **C 深度**：总结要点 + 延伸阅读
- **D 评测**：场景化推荐表格 + 个人选择
- **E 资讯**：值不值得升级 + 官方链接
- **F 复盘**：做对了/做错了/重来会怎么做
- **G 观点**：重申立场 + 承认局限

**末段固定结构（v1.7+，所有风格通用）：**

```markdown
[一句话总结 / 金句 — 复述文章核心价值，1 行]

[CTA — 按 frontmatter `wechat_action` 从 references/writing-styles.md § Closing Templates 选模板，1-2 行]

[下一步 / 系列预告 / 延伸阅读 — 1-2 行]

---

> 本文由 AI 辅助创作，关键数据与事实请以原始来源为准。  ← AIGC 显式标识（Rule 18，必加）
```

> **诚实标识原则**：默认标识**只声明 AI 参与**，不要自动写「人工核实改写」——
> 那是在替作者声称一次并不一定发生的人工核对。只有当作者**确实逐条核对过**
> 数据与事实时，才把标识改成「本文 AI 辅助起稿 + 人工核实改写」。对纯转述来源的
> 文章（如视频/论文总结），更诚实的措辞是「数据与观点以原始来源为准，未逐条二次核实」。

**CTA 模板选择**：读 frontmatter `wechat_action` 字段，到 `references/writing-styles.md` § Closing Templates 找对应模板：
- `heart` → 点♡/在看话术
- `share` → 转发话术
- `collect` → 收藏话术
- `comment` → 留言话术

**一篇只主推 1-2 个动作**——"一键三连"读者会全部忽略（Rule 3 修订版强制）。

**禁用结尾（Rule 3 修订版强制）**：
- ❌ "希望本文对你有帮助" / "如果有问题欢迎留言"
- ❌ "点赞、转发、在看、收藏一键三连"
- ❌ "你的点赞是我最大的动力"
- ❌ 完全无 CTA（4/4 实测都没引导 = 主动放弃算法权重）

**系列文章结尾结构**（仅当 series context 存在时）：

CTA 必须在系列预告之上（视觉首位），按以下顺序：

```markdown
[一句话总结]

[CTA 1-2 行] ← 视觉首位，永远优先

---

> [!tip] 📚 下一篇预告
> 《下一篇标题》— 下一篇的核心内容简介（1-2 句）。

[系列导航 1 行]

---

> 本文 AI 辅助起稿 + 人工核实改写。
```

- 最后一篇：预告改为系列回顾 + 合集链接
- 详见 `skills/series/SKILL.md` § 末段排版规则（P1-19 强制）

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
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ascii_gate.py /ABSOLUTE/PATH/article.md
```

该脚本只扫描**代码块内部**且**非可执行语言**（```text / ```ascii / ```diagram 等）的 ASCII 框/箭头字符，避免对正文里的 `→`（"导致 / 推出"）误报。

- 退出码 `0` = 干净，直接进入下一步。
- 退出码 `1` = 命中违规，stderr 打印 `file:line` 列表 — **必须转换**为 `<!-- IMAGE: --> ` 占位符后再跑一次。

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

**Hard anti-template rules**:
- Do not write roadmap filler like "本文将从 A、B、C 三个方面展开" / "接下来我们逐一来看" / "下面分别介绍".
- Do not stack abstract judgement phrases like "可以看到" / "不难发现" / "本质上" / "从这个角度看".
- Do not use "首先 / 其次 / 最后" as the default section cadence unless you are literally documenting a 3-step operational procedure.
- Every article must contain at least:
  - 2 first-person anchors (`我在...`, `我会...`, `我踩过...`, `本机实测...`)
  - 2 concrete anchors (numbers, versions, command output, file paths, exact error text, benchmark data)
  - 1 explicit tradeoff paragraph (`适合什么 / 不适合什么 / 为什么我不用另一个方案`)
- If a paragraph contains a judgement ("好用" / "克制" / "优雅" / "麻烦"), follow it immediately with evidence or an example in the same paragraph.

### Step 5: Run Self-Check

Canonical source: **`${CLAUDE_PLUGIN_ROOT}/references/self-check-rules.md`**.

Read that file before saving. All rule bodies, canonical grep patterns, and
auto-fix mappings live there — do not re-type them here.

**Write's ownership (per the "Who enforces what" matrix in rules.md):**

- **Pre-save GATE (must pass before Step 6 can save)**: apply rules **1, 2, 6,
  13, 14, and 16** from `references/self-check-rules.md`. Step 6 calls
  `scripts/review_selfcheck.py --write-gate` which runs exactly these six —
  do not re-implement them via grep here. The constant
  `WRITE_GATE_RULES = (1, 2, 6, 13, 14, 16)` in `review_selfcheck.py` is the
  source of truth; if you think a rule should move in or out of the GATE,
  update both rules.md and that constant together. **Rule 14 (ASCII diagrams in
  code blocks) is the pre-images gate; Rule 11 (placeholder residue) is NOT a
  write gate — at write time `<!-- IMAGE: -->` placeholders are expected.**
- **Deferred to lint / review (do not duplicate here)**: rules **3, 4, 5, 7,
  7b, 8, 9, 10, 11, 12, 15, 17**. Those are lint's or review Phase 1's job
  (Rule 11 placeholder-residue fires at review, after the images stage).

For the quick convenience sweep before Step 6, use the single combined grep in
the appendix of rules.md.

Before saving, do one manual anti-AI pass:
- Delete any "本文将 / 接下来 / 下面分别" roadmap sentence unless it adds real information
- Replace any "可以看到 / 本质上 / 从这个角度看" sentence with a concrete claim
- Check whether the article contains 2 personal anchors, 2 concrete anchors, and 1 tradeoff paragraph

### Step 5.5: Word Count Self-Check (do not defer to the orchestrator)

**Why this step exists:** historical orchestrator runs found articles
written ~30% under target, then needed 3-5 rounds of orchestrator-driven
`Update` calls to expand to range. Doing the count + expansion in the
same skill is one round-trip instead of five.

**Compute the Chinese-character count** (excluding code blocks,
frontmatter, image/screenshot placeholder lines, callout markers):

```bash
ART=/ABSOLUTE/PATH/article.md
python3 -c "
import re, sys
src = open(sys.argv[1], encoding='utf-8').read()
# Strip frontmatter
src = re.sub(r'^---\n.*?\n---\n', '', src, count=1, flags=re.DOTALL)
# Strip fenced code blocks
src = re.sub(r'\`\`\`[\s\S]*?\`\`\`', '', src)
# Strip placeholder/comment lines
src = re.sub(r'<!--[\s\S]*?-->', '', src)
# Strip image markdown
src = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', src)
# Count Chinese chars (CJK Unified Ideographs)
n = len(re.findall(r'[一-鿿]', src))
print(n)
" "$ART"
```

**Compare against the target range from the Word Count Reference table
(line 46) using the requirements skill's `depth` value:**

| depth signal | Min characters | Max characters |
|---|---|---|
| `quick` (500-1000) | 500 | 1500 |
| `tutorial` (2000-3000) | 2000 | 3500 |
| `deep` (4000+) | 4000 | 6000 |

**If under min**: don't save yet. Pick 2-3 sections that have the
highest density of conceptual claims and expand each by 100-300
characters with **concrete additions** — a real example, a specific
number, a "我自己跑下来发现" personal observation, or a tradeoff
("但代价是…"). Do **not** pad with restated points or transition
sentences. Re-run the count; loop up to 2 times. If you still can't
reach min after 2 expansion rounds, save as-is and note in the handoff
output (Step 7) that word count fell short — the orchestrator can
decide whether to push back.

> **校准提示**：上面的计数只统计正文 CJK 字符（不含代码块、frontmatter、占位符），所以
> 代码密集的章节"看着长、实际短"。一轮扩写 2-3 节 × 每节 100-300 字 ≈ +300-900 字；
> 先用这个估算缺口要补几节，避免一轮补太少又触发第二轮 loop。

**If over max**: usually fine, but if >1.5× max, look for restated
points or filler ("总的来说" / "综上") and trim.

**If within [min, max]**: proceed to Step 6.

**Output (one line):**
```
WORD_COUNT_CHECK: <count> chars (target [<min>, <max>], depth=<depth>) → PASS|EXPAND|TRIM
```

### Step 6: Save Article (GATE CHECK REQUIRED)

**BEFORE saving**，执行 write pre-save GATE — 这是把 write 的"自检责任"机器化的入口，不再让 agent 用 grep 重新发明（rules 1/2/6/13/14/16）：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/review_selfcheck.py \
  /ABSOLUTE/PATH/article.md --write-gate --json
```

`--write-gate` 一次跑完 6 条 pre-save 阻断规则，源头是 `references/self-check-rules.md` 的 "Who enforces what" 矩阵中 write 列勾选的规则：

| Rule | 检查内容 | 失败处理 |
|------|---------|---------|
| 1 | 红旗词汇（无缝/赋能/链路/实际上/综上所述...） | 删词或改写,见 rules.md Rule 1 的 mapping 表 |
| 2 | Hook ≤100 字 + 禁止套路化开头 | 拆段或重写开头 |
| 6 | 每章 ≥ N 代码块（N 因 style 而异） | 补命令/配置/输出/对比代码片段 |
| 13 | 代码块裸开 ` ``` ` 没语言 tag | 补语言标识（bash/yaml/python/text 等） |
| 14 | 代码块内 ASCII 框线/箭头字符（│├└→ 等）残留 | 转 `<!-- IMAGE: -->` 占位符 |
| 16 | `<!-- PROMPT: -->` 含 CJK 或要 Gemini 渲染文字 | 改用 silhouette / 抽象描述 |

**Exit codes**:
- `0` — 全部 PASS，进入保存步骤。
- `1` — 至少一条 FAIL，stderr/stdout 给出 file:line 列表。**DO NOT SAVE YET**：按上表的失败处理列逐条修复，重新跑直到 `0`。
- `2` — 文件不存在，检查路径。

> `ascii_gate.py` 只跑 Rule 14（代码块内部的 ASCII 框/箭头字符），是 `--write-gate` 的真子集（Rule 14 已在 GATE 内）。保留给 Step 4a 这种"写作中途快速 ASCII 扫"的场景。Step 6 一律走 `--write-gate`，因为它额外覆盖 Rule 1/2/6/13/16。

Use the `Write` tool to save `article.md` to the determined path from Step 2 — **only after `--write-gate` 返回 0**。

Print the absolute file path after saving so subsequent skills can find it.

**Critical**: This GATE check is mandatory. If violations remain, the article cannot be saved. Inform the user and require fixing or conversion before saving.

### Step 7: Handoff Contract Validation (自动验证)

**文件保存后，立即运行自动化验证** — 这是交给 screenshot / images 前的 handoff 契约检查，确保下游 skill 能正确消费。

> **职责分工**:
> - write Step 6 **跑 pre-save GATE 的 6 条规则** (1/2/6/13/14/16) via `review_selfcheck.py --write-gate` —— 内容硬约束在保存前阻断。
> - write Step 7 **只检查下游 skill 的硬契约**(占位符格式、IMAGE/HARVEST 解析、SCREENSHOT/IMAGE 覆盖警告),这是给 screenshot / images 的入参验证。
> - **其余内容质量规则**(描述字段完整性、模板化句式、外链格式、Mermaid 残留、表格/孤儿 PROMPT、占位符残留、register naturalness 等)由 `review` skill 的 Phase 1 (23 条 self-check rules 全套)统一执行,write Step 7 不重复跑。
> - 不要在 Step 7 里再调一次 `${CLAUDE_PLUGIN_ROOT}/scripts/review_selfcheck.py` —— Step 6 已经跑过 GATE 子集,后续全套留给 review。

**必须检查的 3 项 handoff 契约（精简,只保留真正的下游阻断项）+ 1 项软警告：**

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

3. **Check C（HARVEST 占位符 preflight — Style H 专用）** ⭐ **CRITICAL** — 仅当本文是 Style H（爆料自媒体，目录下应存在 `_evidence.json`）时执行。用 `expand-harvest --dry-run --strict` 验证每个 `<!-- HARVEST: -->` 占位符能否在 `_evidence.json` 里找到对应图片。**不联网、不改文件**，只解析。

   ```bash
   # 检测是 Style H 的信号：同目录有 _evidence.json
   if [ -f "$(dirname /ABSOLUTE/PATH/article.md)/_evidence.json" ]; then
     python3 ${CLAUDE_PLUGIN_ROOT}/scripts/screenshot_tool.py expand-harvest \
       --article /ABSOLUTE/PATH/article.md --dry-run --strict
   fi
   ```

   退出码：
   - `0` = 全部 HARVEST 解析 OK（或文件里根本没有 HARVEST 占位符）→ 通过
   - `1` = 至少一条 `source_not_in_evidence` 或 `no_matching_image` → **不能进入 images 阶段**

   失败处理：读返回的 `trace[]`，找出 `status ≠ expanded` 的每一条，按失败原因修正：

   | status | 怎么修 |
   |--------|--------|
   | `source_not_in_evidence` | 占位符里的 src_url 不在 `_evidence.json.sources[]`，查 materials.md 是否漏登记源，或改成已登记的源 URL |
   | `no_matching_image` (has `idx=N`) | `idx` 越界，读 `_evidence.json.sources[i].images` 长度，改成有效下标 |
   | `no_matching_image` (has `alt="..."`) | alt 文本没命中任何 `images[i].alt`，换成命中的子串 |
   | `no_matching_image` (has `--cover`) | 源没抓到封面（og:image 缺失），换用具体 `idx=` 或去掉这张图 |

   修好后**重新保存 article.md**，再跑一次 `--dry-run --strict`，直到 exit=0。

4. **Check E（IMAGE 占位符数量对照 Rule 7b — 软警告 + 自补 cover）** — 按字数阈值检查 `<!-- IMAGE: -->` 占位符数：≤1500 字至少 1 张（cover）；1500–3000 字至少 2 张（cover + 1 节奏图）；>3000 字至少 3 张（cover + 2 节奏图）。**cover 缺失时自动补**（第一张图永远在 H1 下方，模板固定）；**节奏图缺失只警告不自动插**（写完之后再撒下去 LLM 选不对位置，留给作者人工或重跑 write）。

   ```bash
   # 统计当前 IMAGE 占位符数
   IMG_COUNT=$(grep -c '<!-- IMAGE:' /ABSOLUTE/PATH/article.md || echo 0)
   # 字数（用 Step 5.5 同样的算法）
   WORDS=$(python3 -c "
   import re,sys
   src=open(sys.argv[1]).read()
   src=re.sub(r'^---\n.*?\n---\n','',src,count=1,flags=re.DOTALL)
   src=re.sub(r'\`\`\`[\s\S]*?\`\`\`','',src)
   src=re.sub(r'<!--[\s\S]*?-->','',src)
   src=re.sub(r'!\[[^\]]*\]\([^)]+\)','',src)
   print(len(re.findall(r'[一-鿿]',src)))
   " /ABSOLUTE/PATH/article.md)
   # 阈值
   if   [ "$WORDS" -le 1500 ]; then MIN=1
   elif [ "$WORDS" -le 3000 ]; then MIN=2
   else                              MIN=3
   fi
   if [ "$IMG_COUNT" -lt "$MIN" ]; then
     echo "⚠️  IMAGE coverage: $IMG_COUNT placeholders for $WORDS chars (Rule 7b wants ≥$MIN)."
     echo "    → If cover is missing: add it directly under H1 (16:9, standard cover prompt)."
     echo "    → For rhythm images: edit the article to add <!-- IMAGE: --> + <!-- PROMPT: -->"
     echo "      between sections, then run /article-craft:images to render them."
   fi
   ```

5. **Check D（SCREENSHOT 覆盖软警告 — 非阻断）** — 统计正文引用的外部 URL 数和 `<!-- SCREENSHOT: -->` 占位符数；如果**引用了 ≥3 个外部 URL 但发射了 0 个 SCREENSHOT 占位符**，打印一条警告。**不阻断 handoff，不自动插入占位符**（Rule 7b 明文：写完之后再补占位符会被下游 skill 孤立，留到下次重写）。

   ```bash
   # 统计引用数 vs SCREENSHOT 数
   # 白名单从 config.VERIFY_CDN_WHITELIST 读（env.json `verify_cdn_whitelist` 可覆盖）
   WHITELIST_RE=$(python3 -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts'); from config import VERIFY_CDN_WHITELIST; print('|'.join(VERIFY_CDN_WHITELIST))")
   URL_COUNT=$(grep -oE '\]\(https?://[^)]+\)' /ABSOLUTE/PATH/article.md | grep -vE "$WHITELIST_RE" | wc -l)
   SHOT_COUNT=$(grep -c '<!-- SCREENSHOT:' /ABSOLUTE/PATH/article.md || echo 0)
   if [ "$URL_COUNT" -ge 3 ] && [ "$SHOT_COUNT" -eq 0 ]; then
     echo "⚠️  SCREENSHOT coverage warning: $URL_COUNT external URLs cited, 0 SCREENSHOT placeholders."
     echo "    Check §3f『何时发射 SCREENSHOT 占位符』— you likely missed emission triggers."
     echo "    (Non-blocking; handoff continues. If intentional, ignore.)"
   fi
   ```

   目的：**不治已病，治未病** — 在文章离开 write skill 前提醒作者"你可能漏发射了"，而不是让下游 screenshot skill 沉默 no-op。**付费墙 URL / HARVEST 覆盖 / 弱引用**等例外场景由写作者自行判断（见 §3f 反向规则）。

> **命令可执行性**（原 Check C，旧编号） 已移出。自 v1.4.5 起由独立的 `verify-claims` skill
> 在 post-write / pre-review 阶段统一执行，见 `skills/verify-claims/SKILL.md`。

**自动修复流程：**
```
保存文件
  ↓
inline Grep/Bash 检查 3 项 handoff 契约 + 2 项软警告
  ↓
Check A 失败? → 转换为标准占位符格式 → 重新保存
  ↓
Check B 失败? → 补全 ratio/PROMPT/翻译 → 重新保存
  ↓
Check C 失败 (Style H)? → 按 trace 修 HARVEST 占位符 → 重新保存 → 重跑 --dry-run --strict
  ↓
Check E? → cover 缺则自动补；节奏图不足只警告
  ↓
Check D? → 只打印警告，不修复（已写的文章不再事后插占位符）
  ↓
再次 grep 确认修复
  ↓
输出验证结果
```

**验证通过后输出：**
```
✅ Handoff Contract Validation PASSED
   Check A (占位符格式):           0 问题
   Check B (IMAGE 占位符双行格式): N 个，合规 ✅
   Check C (HARVEST preflight):    M 个占位符，全部可解析 ✅ (Style H only)
   Check E (IMAGE 数量 vs Rule 7b): N/最少 X 张 [⚠️ 若 N<X]
   Check D (SCREENSHOT 覆盖):      P 外链 / Q 占位符  [⚠️ 若 P≥3 且 Q=0]

   Command correctness is checked by /article-craft:verify-claims later in
   the pipeline (post-images, pre-review).
   Content quality checks (red-flag words, anti-AI structure, chapter depth,
   closing cadence) are deferred to the review skill.
```

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
   PROBE_OUTPUT=$(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_and_upload_images.py --probe 2>&1)
   BEST_MODEL=$(printf '%s\n' "$PROBE_OUTPUT" | grep '^BEST_MODEL:' | cut -d: -f2)

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
