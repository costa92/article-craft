# Image Guide -- Practical Reference

> Part of article-craft plugin
> Extracted for article-craft plugin -- focuses on practical usage patterns.

---

## Absolute Paths Are Required

All image scripts require absolute file paths. Relative paths cause misleading errors.

```bash
# Get the absolute path after saving with Write tool
realpath article.md

# Then use the absolute path
--process-file /absolute/path/to/article.md
```

## Placeholder Syntax

### AI Image Placeholders

```markdown
<!-- IMAGE: cover - Article cover illustration (16:9) -->
<!-- PROMPT: Modern software development workflow, minimalist flat illustration, blue and teal color scheme -->
```

### Screenshot Placeholders

```markdown
<!-- SCREENSHOT: tool-name-ui - Tool Name Interface -->
<!-- URL: https://example.com -->
<!-- WAIT: 3000 -->
```

Optional extras (local/controlled sites only for SELECTOR):
```markdown
<!-- SELECTOR: .main-content -->
<!-- JS: document.querySelector('.cookie-banner')?.remove() -->
```

## Supported Aspect Ratios

These exact sizes are accepted by the current image providers:

| Ratio | Size | Typical Use |
|-------|------|-------------|
| `16:9` | 1344x768 | Cover image (crop to 900x383 for WeChat) |
| `3:2` | 1248x832 | Body rhythm image -- most common |
| `5:4` | 1152x896 | Architecture / flow diagrams |
| `1:1` | 1024x1024 | Square product images |
| `9:16` | 768x1344 | Mobile vertical |
| `21:9` | 1536x672 | Ultra-wide / panorama |
| `2:3` | 832x1248 | Portrait / mobile screenshots |
| `4:3` | 1184x864 | - |
| `3:4` | 864x1184 | - |
| `4:5` | 896x1152 | - |

## Batch Processing (Primary Method)

Process an entire article's image placeholders in one command:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_and_upload_images.py \
  --process-file /absolute/path/to/article.md \
  --resolution 2K
```

This parses placeholders, generates images, uploads to CDN, and replaces placeholders in-place.

### With Model Override (After Fallback)

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_and_upload_images.py \
  --process-file /absolute/path/to/article.md \
  --model gemini-2.5-flash-image \
  --resolution 2K --continue-on-error
```

Default first choice is `minimax-image-01`. Gemini models remain available as explicit overrides or fallback.

### Parallel Mode

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_and_upload_images.py \
  --process-file /absolute/path/to/article.md \
  --parallel --resolution 2K
```

- 2 workers: ~1.87x faster (93.5% efficiency)
- 4 workers: ~2.5-3x faster (may trigger API rate limits)
- Recommended: 2 workers for stability

### Dry-Run Preview

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_and_upload_images.py \
  --config images_config.json --dry-run --resolution 2K
```

## Single Image Generation (Probes and Manual)

```bash
# Probe test
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nanobanana.py \
  --prompt "test" --size 1024x1024 --output /tmp/gemini_probe.jpg

# Single image with specific size
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nanobanana.py \
  --prompt "Detailed image description" \
  --size 1344x768 \
  --resolution 2K \
  --output /path/to/images/cover.jpg
```

**nanobanana.py does NOT auto-create directories** -- always `mkdir -p` first.

### nanobanana.py Parameters

| Parameter | Required | Description | Default |
|-----------|----------|-------------|---------|
| `--prompt` | yes | Image description (Chinese or English) | - |
| `--size` | no | Image dimensions (see ratio table) | 768x1344 |
| `--output` | no | Output file path | nanobanana-UUID.png |
| `--model` | no | Image model override | minimax-image-01 |
| `--resolution` | no | Quality (1K/2K/4K) | 1K |

## ASCII Diagram Replacement

Replace ASCII art architecture diagrams (box-drawing characters) with AI-generated illustrations.

**Targets:** Code blocks containing `\u250c \u2500 \u2502 \u2514 \u2518 \u25bc \u25b6 \u251c` characters. Do NOT replace executable code blocks (bash/python/etc.).

**Prompt template for architecture diagrams:**

```
A clean, modern technical architecture diagram on white background.
[Layer description]: Top layer shows [components]. Middle layer shows [components].
Bottom layer shows [components]. Arrows connecting [from] to [to].
Color scheme: [A] in soft blue, [B] in light green, [C] in warm orange.
Flat design, no shadows, engineering blueprint aesthetic with subtle grid lines.
Clear sans-serif labels.
```

**Rules:**
- One ASCII block = one AI image
- If an ASCII block is followed by a redundant rhythm image, merge into one replacement
- Alt text should describe the architecture (e.g., "Gateway: multi-channel -> Gateway -> Agent")
- Recommended size: 3:2 (1248x832)

## Screenshots (Independent of Image Provider)

Screenshots use `screenshot_tool.py` (Playwright) and always work regardless of Minimax/Gemini availability:

```bash
# Manual single screenshot
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/screenshot_tool.py screenshot "https://example.com" \
  -o /tmp/screenshot.png -w 3
# 默认走 screenshot_tool 内置 CDN 上传（复用项目统一上传器）
```

**Automated flow** (`--process-file`):
1. HEAD 预检 URL（404/403/5xx 检测）
2. Playwright 渲染（等待网络空闲）
3. 空页面 / 404 文本检测
4. 智能选择器推荐
5. 截图 → Pillow 压缩 → CDN 上传

**Execution order:** Screenshots first (always available) -> AI images second (may fail) -> upload each to CDN.

**Placement rules:**
- Never place SCREENSHOT between Markdown list items -- put after the list block
- No images in reference sections (pure text lists)
- 截图必须是文章直接引用的真实内容，避免装饰性截图

## Retry Strategy

On transient failure (network, SSL, rate-limit):

1. Wait 2 seconds, retry
2. Wait 3 seconds, retry
3. After 3 total failures, report and ask whether to continue

## Image Placement Guidelines

- **Cover:** 16:9, top of article
- **Rhythm:** 3:2, every 400-600 words
- **Count:** 1 cover + 4-6 rhythm images per 3000-word article
- **No duplicates** in the same section
- Use unique filenames per article (e.g., `docker_cover.jpg`, `docker_workflow.jpg`)

---

## Visual Style Guide

> 核心原则：**概念图先行，Token 一致**。封面图锁定整篇文章的视觉语言（色调、风格、氛围），
> 后续所有节奏图沿着这条审美轨道跑，不跑飞。

### 风格一致性规则 (v1.4.19 更新 — "锁感觉,不锁画面")

> **核心原则**:同篇 4 张图应让读者**感觉**是一套(同色同调同氛围),但**画面**
> 不应雷同(不同镜头、不同构图、不同主体框选)。两件事解耦 — 锁调色板 + 风格,
> 放开镜头 + 构图。

**全篇建议统一 (不是死锁):**

1. **视觉风格 preset** — 先按内容类型选一个主风格,再允许相邻图做轻微变化
2. **色彩家族** — 同一小节内尽量一致,跨小节可切换
3. **材质表现** — flat / layered / line-art / gradient / paper-cut,按图像职责选择
4. **氛围关键词** — clean/modern/warm/bold,按图像职责选择
5. **光线 / 尺度** — soft daylight / studio light, macro / wide / mixed-scale,可在系列内做受控切换
6. **背景处理** — 白底/深色/渐变,可在系列内做受控切换

**鼓励变化 (脚本自动按位置注入,作者不必手写):**

1. **镜头角度** (`Camera: ...`) — establishing wide / 3/4 perspective /
   top-down / close-up / side elevation / isometric corner
2. **构图取向** (`Composition: ...`) — centered / rule-of-thirds /
   scattered / hierarchical / asymmetric / grid-aligned
3. **主体框选** — 单体特写 / 群组 / 上下文场景 (内容描述层自然变化)
4. **视觉密度** — 极简 / 中等 / 满铺 (内容描述层自然变化)

**写 PROMPT 时,只写风格约束 + 内容,不用手动加 Camera/Composition:**

```markdown
<!-- PROMPT: [风格约束 + 色彩 + 背景], [具体内容] -->
```

例:逻辑/关系/结构图（流程图、框架图、关系图、架构图）优先
`hand-drawn infographic poster`，对比图优先
`clean data visualization style`，观点图优先 `conceptual metaphor illustration`。
脚本(`generate_and_upload_images.py` 里的 `select_visual_style_from_prompt()` /
`vary_prompt_for_position()`) 会先按内容选 preset，再按位置注入不同的
`Camera:` / `Composition:` / `Visual treatment:` / `Palette:` / `Material:` / `Lighting:` / `Scale:`，
同一篇文章自然拉开画面差异。

### 镜头/构图轮转表 (脚本自动注入,作者了解即可)

| 图片位置 | 自动注入的 Camera | 自动注入的 Composition | 自动注入的 Visual treatment |
|---------|------------------|----------------------|-----------------------------|
| 封面 (idx 0) | establishing wide shot | centered subject with breathing room | minimal and airy with large whitespace |
| 节奏图 1 (idx 1) | three-quarter perspective view | rule-of-thirds with off-center focus | slightly denser with more components in frame |
| 节奏图 2 (idx 2) | top-down overhead view | scattered multi-focal composition | diagrammatic with stronger visual hierarchy |
| 节奏图 3 (idx 3) | close-up detail focus | hierarchical layered composition | editorial and narrative with one dominant focal object |
| 节奏图 4 (idx 4) | side elevation flat view | asymmetric weight balance | bold contrast with crisp outlines and accent blocks |
| 节奏图 5 (idx 5) | isometric corner perspective | grid-aligned modular composition | soft atmospheric with subtle gradients and shadows |
| (位置 6+ 取模轮转) | | |

**作者覆盖**:如果你在 PROMPT 里**手动写了** Camera/Composition/Visual treatment
(比如 `top-down view of...`、`centered composition...` 或 `Visual treatment: ...`),
脚本检测到后会跳过对应轴的注入,你的写法生效。要完全关闭注入用
`--no-vary-prompts` flag。

**验证 (2026-05-08 实测)**:6 张同基础 PROMPT,只换 Camera + Composition
指令,Gemini 输出的画面**显著不同**(等距 / 俯视 / 横向阶梯 / 信息密集
dashboard / 3D 透视),但调色板和风格 preset 锁定生效。Layer C 收益验证通过。

### 6 种视觉风格

根据文章类型选择风格，写入所有 PROMPT 的风格约束部分：

#### S1: 极简扁平 (Minimal Flat)

适用：A 教程、E 资讯
特点：纯色块 + 线条图标，无阴影无渐变，留白充足

```
风格约束: Minimalist flat illustration, solid color blocks, thin line icons,
no shadows no gradients, generous white space, [主色] and [辅色] palette
```

**封面示例：**
```
<!-- PROMPT: Minimalist flat illustration, solid blue and teal blocks, thin line icons, no shadows, white background. A developer laptop with Docker containers floating above it as colorful rectangles, connected by thin lines -->
```

#### S2: 手绘信息图海报 (Hand-drawn Infographic Poster)

适用：**所有逻辑/关系/结构图**（流程图、框架图、关系图、思维导图、架构图）
特点：奶油色纸张底 + 黑色线描 + 柔和马克笔上色 + 可爱商务卡通角色，模块化信息面板用箭头连成知识地图，SaaS 创业风
触发：脚本里 `flow / architecture / pipeline / system / relationship / framework / mind map / concept map / knowledge map / logic / hierarchy / topology / structure` 任一命中即自动套用（`DESIGN_LOGIC_RULES` "explain structure or relationship"，已**取代旧的 S2 等距透视**）。

> ⚠️ **每张图的 PROMPT 必须以完整 S2 风格 stem 开头**（同 S8 经验）：脚本会把签名 token
> 注入到 prompt **末尾**（`Background:`），但末尾注意力权重低，rhythm 图容易脱锚。把完整 stem
> 抄到每条 PROMPT 开头最稳。**可直接 copy 的 stem**：
>
> ```
> hand-drawn infographic poster, whiteboard doodle illustration, sketchnote style
> knowledge map, warm cream paper background, clean black line art with soft marker
> coloring, cute friendly business cartoon characters, modular information panels with
> arrows and flow connections, rich doodle icons (rockets, light bulbs, gears,
> documents, team and workflow symbols), friendly corporate cartoon style, minimalist
> vector illustration, mind-map composition, modern SaaS startup aesthetic.
> ```
>
> 然后接本图具体内容（带标签）。

> 📝 **文字例外（S2 专属，与全局 Rule 5 禁文字相反）**：信息图/知识地图的核心就是**带标签**，
> 所以 S2 **允许英文短标签**（面板名、节点名、箭头说明）。`check_rule_16` 检测到 S2 风格签名
> （`hand-drawn infographic poster`/`sketchnote`/`knowledge map`/`whiteboard doodle`）会豁免"渲染英文文字"告警——
> 不必写 `No readable text`。三条底线：
>
> 1. **英文 only，不放中文**。中文（CJK）在任何模型上都不稳（变形/缺笔/糊），所以 S2 标签一律用英文
>    （`Input` / `Parser` / `Cache` / `API`）。`check_rule_16` 对 S2 也照拦 CJK——这是强制执行，不是建议。
>    中文正文 + 英文图标签是中文技术写作的常规搭配，专业不违和。
> 2. **只放短标签**（1–3 个英文词），如 `Input`、`Parse Request`、`Cache Layer`。
>    **绝不**让它渲染整句话、长标题、段落——长文本任何模型都会糊。
> 3. **关键准确文字宁可不画**：版本号、品牌名、精确数字这类"错一个就出事"的，用截图/表格，别交给图像模型。
>
> 英文短标签在所有模型（含默认 minimax）上都能稳定渲染，**无需 `--model` 覆盖、无需人工核对**。

```
风格约束: hand-drawn infographic poster, whiteboard doodle illustration, sketchnote
style knowledge map, warm cream paper background, clean black line art with soft marker
coloring, cute friendly business cartoon characters, modular information panels with
short English text labels, arrows and flow connections, rich doodle icons (rockets,
light bulbs, gears, documents, team symbols), minimalist vector illustration, mind-map
composition, high readability, modern SaaS startup aesthetic
```

**封面示例（英文标签）：**
```
<!-- PROMPT: hand-drawn infographic poster, whiteboard doodle illustration, sketchnote style knowledge map, warm cream paper background, clean black line art with soft marker coloring, cute friendly business cartoon characters, modular information panels with arrows and flow connections, rich doodle icons. A central workflow framework: three connected rounded panels laid out left to right, panel one labeled Input with a document icon, panel two labeled Parser with a gears icon, panel three labeled Output with a rocket icon, thin hand-drawn arrows linking the panels into a flow, mind-map composition, high readability, modern SaaS startup aesthetic. Short English labels only, no long sentences, no Chinese characters -->
```

#### S3: 渐变科技 (Gradient Tech)

适用：C 深度、G 观点
特点：深色背景 + 霓虹渐变，未来感，适合前沿技术话题

```
风格约束: Dark background with neon gradient accents, futuristic tech aesthetic,
glowing edges, [主渐变色] to [辅渐变色] gradient, clean sans-serif labels
```

**封面示例：**
```
<!-- PROMPT: Dark navy background with purple-to-cyan neon gradient accents, futuristic aesthetic, glowing edges. A neural network visualization with interconnected nodes pulsing with gradient light, data flowing as luminous particles -->
```

#### S4: 手绘线描 (Hand-drawn Line Art)

适用：B 分享、F 复盘
特点：素描风格线条，轻松亲切，适合经验分享类

```
风格约束: Hand-drawn sketch style, black ink lines on white, casual and friendly,
slight imperfections, notebook paper feel, [accent color] highlights
```

**封面示例：**
```
<!-- PROMPT: Hand-drawn sketch style, black ink lines on white background, casual and approachable. A developer desk scene with coffee cup, terminal window, and scattered sticky notes with Git commands, orange highlight accents -->
```

#### S5: 数据可视化 (Data Viz)

适用：D 评测、F 复盘
特点：图表感，数据驱动，对比鲜明

```
风格约束: Clean data visualization style, chart-inspired layout, contrasting colors
for comparison, minimal decoration, [A色] vs [B色] for before/after or comparison
```

**封面示例：**
```
<!-- PROMPT: Clean data visualization style, white background, chart-inspired layout. Side-by-side bar chart comparing Bun vs Node.js vs Deno performance, blue for Bun (tallest), gray for Node, green for Deno, clean sans-serif labels -->
```

#### S6: 概念场景 (Concept Scene)

适用：G 观点、B 分享
特点：隐喻性场景，用具象画面表达抽象概念

```
风格约束: Conceptual metaphor illustration, storytelling scene, warm and relatable,
[主色调] tones, soft lighting, minimal text
```

**封面示例：**
```
<!-- PROMPT: Conceptual metaphor illustration, warm amber and blue tones, soft lighting. A crossroads scene where one path leads to a complex tangled city (over-engineering) and the other to a simple clean bridge (simplicity), a developer standing at the fork -->
```

#### S7: 信息图 (Infographic)

适用：A 教程、C 深度、系列文章
特点：白底 + 卡通角色 + 矢量连线 + 多色图标，适合流程图和架构图

```
风格约束: Modern clean infographic style, soft white background,
cartoon-style characters with vector connectors, professional icon-based layout.
Soft [blue] [purple] [yellow] [green] accents
```

**封面示例：**
```
<!-- PROMPT: Modern clean infographic style, soft white background, cartoon-style characters with vector connectors, professional icon-based layout. Soft blue purple yellow green accents. A central cartoon AI brain character with multiple extending arms, each arm connected by dotted vector lines to a different colored icon: blue database, purple cloud API, green file folder, orange terminal, yellow web browser -->
```

#### S8: AI 教程封面 (AI Tutorial Cover)

适用：A 教程（AI/LLM 主题）、C 深度（模型原理 / Transformer / RAG / Agent）、AI 知识博主向
特点：黑底科技网格 + 悬浮白色知识卡片，高对比黑白配色 + 单一强调色，
Notion 页面 / Figma 演示排版氛围，B 站科技教程封面感

> ⚠️ **避坑（v1.7.6 实测，4 张图 dogfood）**
>
> 1. **不要用文字暗示词**：`notebook annotations` / `handwritten notes` / `sticky notes` 会让
>    模型在 "no text" 硬约束下硬塞 gibberish letters。用 `hand-drawn doodle marks` /
>    `arrow scribbles` / `geometric shape sketches` 替代——保留涂鸦质感，去掉文字暗示。
>
> 2. **rhythm 图必须用结构化措辞，禁止叙事化措辞**。模型在 editorial treatment 注入下，
>    叙事化 prompt 会脱锚成赛博朋克场景。
>
>    | ❌ 叙事化（会脱锚） | ✅ 结构化（保留 S8 卡片结构） |
>    |---|---|
>    | "input arrow splits into 8 parallel attention heads" | "8 small white cards arranged in a horizontal row, each card showing a different small dot-grid pattern" |
>    | "Q matrix multiplied with K then V" | "three vertically stacked white cards labeled with abstract column-shape icons (no letters), connected by thin arrows" |
>    | "data flows through encoder-decoder transformation" | "stacked white cards in two columns, dotted lines connecting left column to right column" |
>
>    **公式**：先说几张卡 / 怎么排列 / 卡上是什么图形，再说概念是什么。
>
> 3. **模型选择**：本地实测 minimax-image-01 在多卡场景下假文字漏出概率 ~30%。
>    对假文字零容忍的封面用 `--model gemini-2.5-flash-image` 更稳；rhythm 图可
>    继续 minimax（成本低、构图更大胆）。
>
> 4. **palette 已 article-wide 锁 cyan**（v1.7.6 preset 改单变体）。想用 yellow 等其他
>    accent，作者需在 base prompt 显式写 `Palette: high-contrast black and white with [color] accent`，
>    脚本检测到 `Palette:` 字面会跳过注入。
>
> 5. **每张图的 PROMPT 必须以完整 S8 风格 stem 开头**（v1.7.6 端到端实测发现，必备保护）。
>    脚本会自动在 prompt 末尾注入 `Background:` 锁感觉，但末尾位置注意力权重低 —
>    实测 cover（结构锚点强）通常能扛住，rhythm 图（空间布局相对弱）经常脱锚成
>    teal 雾气 / 白底高亮 / 渐变科技。**对照实验**：
>
>    | 场景 | base prompt 写法 | 4 图 S8 成功率 |
>    |---|---|---|
>    | v5 实测 | 每图开头都抄完整 S8 stem | 4/4 ✅ |
>    | v7 实测 | naive 内容描述（零 stem） | 4/4 黑底 cyan 最低线，但卡片结构 2/4 |
>    | v1.7.6 端到端 | base 含 "white diagram cards" 关键词无完整 stem | 1/3 强 S8，2/3 漂移 |
>
>    **可直接 copy 到每个 PROMPT 开头的 stem**（粘贴后接本图具体内容）：
>
>    ```
>    AI tutorial cover style, dark black background with subtle tech grid,
>    multiple floating white diagram cards with rounded corners and soft shadows
>    as the dominant visual structure, high-contrast black and white palette
>    with single cyan accent only, no other accent colors.
>    ```
>
>    然后写本图具体内容：`[X 张卡片排成 Y 模式], [每张卡上是什么图形],
>    [卡之间怎么连], [收尾 no text 硬约束]`。

```
风格约束: AI tutorial cover style, dark black background with subtle tech grid,
floating white diagram cards with rounded corners and soft shadows,
high-contrast black and white palette with single [accent color] only,
no other accent colors, Notion-page layout aesthetic, Figma-style presentation.
The cards contain only graphical icons and shape diagrams, never any letters or words.
```

**封面示例：**
```
<!-- PROMPT: AI tutorial cover style, dark black background with subtle tech grid pattern, floating white diagram cards with rounded corners and soft shadows, high-contrast black and white palette with single cyan accent only, no other accent colors. A central Transformer architecture diagram displayed inside a large white card showing encoder-decoder stacks with stacked blocks, surrounded by smaller satellite cards illustrating multi-head attention split into parallel heads, sinusoidal positional encoding wave shapes, and a feed-forward block, all connected by thin dotted lines and small hand-drawn doodle marks, arrow scribbles, and simple geometric shape sketches. The cards contain only graphical icons and shape diagrams, never any letters or words -->
```

### 风格 × 文章类型推荐矩阵

| 文章风格 | 首选视觉 | 备选视觉 | 封面氛围 |
|---------|---------|---------|---------|
| A 教程 | S1 极简扁平 | S7 信息图 / S8 AI 教程封面（AI 主题） | 清晰、可信、专业 |
| B 分享 | S4 手绘线描 | S6 概念场景 | 亲切、轻松、真实 |
| C 深度 | S7 信息图 | S2 手绘信息图海报 / S8 AI 教程封面（模型/算法主题） | 严谨、深度、工程感 |
| D 评测 | S5 数据可视化 | S1 极简扁平 | 客观、对比、数据驱动 |
| E 资讯 | S1 极简扁平 | S2 手绘信息图海报 | 简洁、快速、信息密度 |
| F 复盘 | S5 数据可视化 | S4 手绘线描 | 反思、对比、before/after |
| G 观点 | S6 概念场景 | S3 渐变科技 | 有态度、引发思考 |
| AI 知识博主向 | S8 AI 教程封面 | S7 信息图 | 黑底白卡、Notion 感、科普博主 |

### 设计逻辑

先判断这张图要解决什么问题，再选视觉语言：

| 目标 | 优先视觉 |
|------|---------|
| 解释结构 / 关系 / 逻辑（流程图、框架图、关系图、思维导图、架构图） | S2 / S7 |
| 展示对比 | S5 |
| 表达概念 | S6 / S3 |
| 讲流程 | S2 / S7 |
| 强调人味 | S4 |
| 讲 AI/LLM 概念（Transformer / 注意力 / RAG / Agent） | S8 |
| 泛用兜底 | S1 |

每张图最终都会再经过位置轮转，补上镜头、构图、配色、材质、光线和尺度变化。

### Prompt 写作规则

1. **语言**: 用英文写 prompt（Gemini 对英文 prompt 理解更准确）
2. **结构**: `[风格约束], [背景描述]. [主体内容], [细节补充]`
3. **长度**: 30-80 词，太短缺细节，太长互相矛盾
4. **禁止**: 不要写 "高清" "4K" "超清"（由 `--resolution` 参数控制）
5. **硬禁止——文字渲染**（重要，违反即重生成）：

   > **唯一例外 = S2 手绘信息图海报**：信息图/知识地图的本质是带标签，S2 允许**英文短标签**
   > （`check_rule_16` 按风格签名豁免英文标签告警，但 CJK 对 S2 也照拦——English-only）。详见上文 S2 段
   > 的「📝 文字例外」。本条以下的全局禁文字适用于 **S2 以外的所有风格**。

   Gemini 的图像模型**无法稳定渲染中文**（汉字变形/缺笔画/拼错），英文也只能勉强渲染短标签。凡是要求图里出现"可读文字"的提示词，产出几乎必然翻车。

   - **绝对禁止**在 prompt 里写任何要 Gemini 渲染的中文文字（标题、标签、引号内容、菜单项、报纸标题、书法内容……）
   - **不要**写 `"中文标题 'XXX'"`、`"菜单上写'招牌菜 ¥68'"`、`"左上角大字'2026 年报'"` 这类指令
   - **也不要**让它渲染中文人名、中文签名、中文印章文字

   **硬约束模板**（所有 prompt 建议 copy 这一行到末尾）：

   ```
   No readable text anywhere, no letters, no numbers, no labels, no captions, no logos.
   ```

   **需要传达"有文字"的概念时，用视觉替代**：

   | 想表达 | ❌ 错误写法 | ✅ 正确写法 |
   |--------|-----------|-----------|
   | 菜单 | `menu with items "招牌牛肉 ¥98..."` | `silhouette of a folded menu showing price-column layout lines and subtle food-icon shapes` |
   | 报纸 | `newspaper headline "XX 技术突破"` | `silhouette of a newspaper front page showing only masthead frame and column block patterns` |
   | 海报 | `poster with Chinese title "越界"` | `silhouette of a vehicle-launch poster with abstract light-streak and product-shape composition` |
   | 杂志封面 | `magazine cover titled "慢生活 VOL.08"` | `silhouette of a magazine cover showing only layout grid and cover-photo shape` |
   | 书法 | `calligraphy scroll saying "静"` | `calligraphy scroll showing only abstract brush-stroke marks, no characters` |

   **唯一允许出现的文字**：少量已知 Gemini 渲染准确的拉丁字母（如品牌 logo `Apple`、`Docker`、`React`、通用符号如 `→` `&` `+`）。哪怕这一类也建议全部去掉，用图标替代。

6. **禁止自证悖论**：如果文章本身讲的是"某模型的文字渲染能力"（比如 GPT-Image-2、nano-banana 的文字测试），**绝对不能用 Gemini 生成示意图去"展示"那个模型的文字效果**——这等于拿一个不擅长渲染文字的模型去证明另一个模型擅长渲染文字，视觉上自相矛盾。这种场景只能用：
   - 作者手工截图（`<!-- SCREENSHOT: -->` 占位符或直接插入真实截图 URL）
   - Markdown 表格对比
   - 纯抽象示意图（剪影、色块、图标）
7. **配色命名**: 用具体色名 (`soft blue`, `coral`, `mint green`)，不用 `漂亮的颜色`

### 封面图 → 节奏图一致性示例

```markdown
<!-- 封面：锁定视觉语言 -->
<!-- IMAGE: cover - Docker 多阶段构建教程封面 (16:9) -->
<!-- PROMPT: Minimalist isometric illustration, soft blue and orange palette, white background with subtle grid. A multi-stage Docker build pipeline shown as connected conveyor belts, raw code enters left, optimized container exits right, each stage a distinct colored module -->

<!-- 节奏图1：复用相同风格约束 -->
<!-- IMAGE: dockerfile-layers - Dockerfile 分层结构 (3:2) -->
<!-- PROMPT: Minimalist isometric illustration, soft blue and orange palette, white background with subtle grid. A vertical stack of translucent layers representing Docker image layers, base OS at bottom in blue, dependencies in middle in light orange, app code on top in coral, with size labels -->

<!-- 节奏图2：依然复用 -->
<!-- IMAGE: multi-stage-flow - 多阶段构建流程 (3:2) -->
<!-- PROMPT: Minimalist isometric illustration, soft blue and orange palette, white background with subtle grid. Two Docker containers side by side, left one large and cluttered (build stage), right one small and clean (production stage), an arrow showing the slim artifact transferring between them -->
```

注意三张图都以 `Minimalist isometric illustration, soft blue and orange palette, white background with subtle grid` 开头——这就是**设计 Token 一致性**。
