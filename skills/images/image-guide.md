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

Only these exact sizes are accepted by the Gemini API:

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
| `--model` | no | Gemini model override | gemini-3-pro-image-preview |
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

## Screenshots (Independent of Gemini)

Screenshots use `shot-scraper` and always work:

```bash
# Manual single screenshot
shot-scraper https://example.com -o /tmp/screenshot.jpg --wait 3000
picgo upload /tmp/screenshot.jpg
```

When using `--process-file`, screenshots are handled automatically alongside AI images.

**Execution order:** Screenshots first (always available) -> AI images second (may fail) -> upload each to CDN.

**Placement rules:**
- Never place SCREENSHOT between Markdown list items -- put after the list block
- No images in reference sections (pure text lists)

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

### 风格一致性规则

同一篇文章的所有 PROMPT **必须共享以下设计 Token**：

1. **色彩方案** — 封面确定主色 + 辅色，后续图片复用
2. **视觉风格** — 扁平/等距/线描/渐变，全篇统一
3. **氛围关键词** — clean/modern/warm/bold，全篇一致
4. **背景处理** — 白底/深色/渐变，全篇统一

**写 PROMPT 时，先写风格约束，再写具体内容：**

```markdown
<!-- PROMPT: [风格约束], [具体内容描述] -->
```

例如：封面用了 `minimalist isometric, tech blue and coral palette, white background`，
后续节奏图也要带上这段风格前缀。

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

#### S2: 等距透视 (Isometric)

适用：A 教程、C 深度、F 复盘
特点：2.5D 视角，模块化组件，工程感强

```
风格约束: Isometric technical illustration, 2.5D perspective, modular components,
clean engineering aesthetic, [主色] and [辅色] palette, subtle grid lines
```

**封面示例：**
```
<!-- PROMPT: Isometric technical illustration, 2.5D perspective, soft blue and mint green palette, subtle grid background. A multi-layer architecture with API gateway on top, microservices in middle, database at bottom, connected by glowing data pipes -->
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

### 风格 × 文章类型推荐矩阵

| 文章风格 | 首选视觉 | 备选视觉 | 封面氛围 |
|---------|---------|---------|---------|
| A 教程 | S1 极简扁平 | S7 信息图 | 清晰、可信、专业 |
| B 分享 | S4 手绘线描 | S6 概念场景 | 亲切、轻松、真实 |
| C 深度 | S7 信息图 | S2 等距透视 | 严谨、深度、工程感 |
| D 评测 | S5 数据可视化 | S1 极简扁平 | 客观、对比、数据驱动 |
| E 资讯 | S1 极简扁平 | S2 等距透视 | 简洁、快速、信息密度 |
| F 复盘 | S5 数据可视化 | S4 手绘线描 | 反思、对比、before/after |
| G 观点 | S6 概念场景 | S3 渐变科技 | 有态度、引发思考 |

### Prompt 写作规则

1. **语言**: 用英文写 prompt（Gemini 对英文 prompt 理解更准确）
2. **结构**: `[风格约束], [背景描述]. [主体内容], [细节补充]`
3. **长度**: 30-80 词，太短缺细节，太长互相矛盾
4. **禁止**: 不要写 "高清" "4K" "超清"（由 `--resolution` 参数控制）
5. **禁止**: 不要写文字内容（AI 生成的文字通常是乱码）
6. **配色命名**: 用具体色名 (`soft blue`, `coral`, `mint green`)，不用 `漂亮的颜色`

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
