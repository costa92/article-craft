---
name: article-craft:screenshot
version: 1.4.6
description: "Take web page screenshots with intelligent validation + generate social share cards. Uses Playwright for real browser rendering, validates URLs before capture, detects 404/empty pages, optimizes image size. Supports WeChat, Xiaohongshu, Twitter/X, LinkedIn, and more."
allowed-tools:
  - Read
  - Edit
  - Bash
  - Grep
  - AskUserQuestion
---

# Screenshot — 智能网页截图 & 分享卡片

本 skill 包含两大功能：
1. **网页截图** — Playwright 渲染 + URL 验证 + 智能选择器
2. **分享卡片** — 各平台分享图批量生成（Playwright 渲染 HTML → PNG）

核心原则：**真实内容、适度大小、按需截取**。

三大保障（网页截图）：
1. **截图前验证** — HEAD 请求检查 URL 可用性，追踪重定向链，检测 404/403/5xx
2. **渲染后检测** — Playwright 渲染后再次检查页面内容，过滤空页面和 404 页面
3. **按需截图** — 只截取与文章真正相关的页面，避免堆砌无意义截图

---

## 占位符扫描优先级

scan article.md 时同时识别两种占位符：

| 占位符 | 处理方式 |
|--------|----------|
| `<!-- SCREENSHOT: url [opts] -->` | 走下面的"核心流程（截图处理）"完整管线 |
| `<!-- HARVEST: url idx= \| alt= [caption=] -->` | 读 `_evidence.json` 就地替换为 `![caption](远端 url)`，**不截图不压缩不上 CDN** |

HARVEST 扩展示例处理（含 v1.4.6 rehost）：

```python
# 伪代码
with open(article_dir / "_evidence.json") as f:
    evidence = json.load(f)

for match in re.finditer(r"<!-- HARVEST: (\S+)(.*?)-->", article_md):
    src_url, opts = match.group(1), match.group(2)
    source = find_source_by_url(evidence["sources"], src_url)
    if not source:
        warn(f"HARVEST: source {src_url} not in _evidence.json")
        continue
    img = pick_image(source["images"], opts)  # 按 idx / alt
    if not img:
        warn(f"HARVEST: no matching image for {opts}")
        continue
    caption = parse_caption(opts) or img.get("alt") or ""
    # v1.4.6: rehost step — auto-detect hotlink-blocked CDNs (mmbiz, sinaimg,
    # zhimg) and re-upload to our own CDN. Non-whitelist URLs pass through.
    # Per-placeholder override `rehost=never|always` in opts beats the default.
    rehost_mode = parse_rehost(opts) or "auto"
    final_url = img["url"]
    if rehost_mode != "never":
        result = subprocess.run([
            "python3", f"{CLAUDE_PLUGIN_ROOT}/scripts/screenshot_tool.py",
            "rehost", "--url", img["url"], "--mode", rehost_mode,
        ], capture_output=True, text=True)
        payload = json.loads(result.stdout)
        if payload["ok"] and payload["rehosted"]:
            final_url = payload["final_url"]
        # else: graceful degradation — keep original img["url"] (warn in log)
    replace(match, f"![{caption}]({final_url})")
```

若 `_evidence.json` 不存在 → 保留 HARVEST 占位符，提示用户先跑 `/article-craft:evidence`。

---

## 核心流程（截图处理）

```
用户提供 URL
    │
    ▼
┌─────────────────────┐
│ 1. HEAD 请求验证    │  ← 检测 404/403/5xx，重定向链
└────────┬────────────┘
         │ ❌ 404/5xx → 警告，跳过，不截图
         ▼
┌─────────────────────┐
│ 2. Playwright 渲染  │  ← 等待网络空闲，等待 JS 执行
└────────┬────────────┘
         │
         ▼
┌─────────────────────────────┐
│ 3. 内容真实性检测            │  ← body 高度检查 + 404 文本特征检测
│    - 内容高度 < 100px → 空页面 │
│    - 包含 404 文本 → 404 页面 │
└────────────┬────────────────┘
             │ ❌ 空页面/404 → 警告，跳过
             ▼
┌─────────────────────────────┐
│ 4. 智能选择器推荐            │  ← 根据 URL 自动推荐 CSS 选择器
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ 5. 截图（指定元素或全页）     │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ 6. 压缩 + 裁剪空白           │  ← Pillow 压缩，>500KB 则缩放
└────────────┬────────────────┘
             │
             ▼
         输出 PNG → 可选 CDN 上传
```

---

## 占位符格式

```markdown
<!-- SCREENSHOT: https://example.com -->
<!-- SCREENSHOT: https://example.com #element-selector -->
<!-- SCREENSHOT: https://example.com WAIT:3 -->
<!-- SCREENSHOT: https://example.com WIDTH:800 -->
```

**扩展语法：**
| 语法 | 说明 |
|------|------|
| `#selector` | CSS 选择器，只截取该元素 |
| `WAIT:N` | 额外等待 N 秒（SPA 页面） |
| `WIDTH:N` | 视口宽度（默认 1280） |

### HARVEST 占位符（Style H 爆料自媒体专用）

和 `SCREENSHOT` 不同，`HARVEST` **不重截图**，而是从源文章直引远端图片 URL：

```markdown
<!-- HARVEST: https://mp.weixin.qq.com/s/xxx idx=3 -->
<!-- HARVEST: https://mp.weixin.qq.com/s/xxx alt="Claude Code 并行界面" -->
<!-- HARVEST: https://mp.weixin.qq.com/s/xxx idx=5 caption="KAIROS 代号泄露" -->
<!-- HARVEST: https://mp.weixin.qq.com/s/xxx idx=3 rehost=never -->
```

**解析语法：**
| 字段 | 说明 |
|------|------|
| `idx=N` | `_evidence.json` 中该源的 `images[N]`（0-indexed） |
| `alt="…"` | 按 alt 文本模糊匹配图片（优先级低于 idx） |
| `caption="…"` | 最终输出到 markdown 的图注文字 |
| `rehost=auto\|always\|never` | 覆盖默认 rehost 策略（默认 `auto`） |

**展开规则（v1.4.6+）：**

1. 必须先跑 `evidence` skill 生成 `_evidence.json`（同目录）
2. 根据 `rehost` 模式决定是否改写 URL：
   - `auto`（默认）：URL 命中白名单 CDN（`mmbiz.qpic.cn` / `mmbiz.qlogo.cn` / `*.sinaimg.cn` / `pic*.zhimg.com`）→ 下载（带正确 Referer）→ 上传我方 CDN → 用新 URL。其他 URL 保持远端。
   - `always`：每张图都 rehost（不推荐，违背 v1.4.0 "远端 CDN 保持真源"哲学）
   - `never`：跳过 rehost，永远用远端 URL（写作者明确知道目标平台能直接加载时用）
3. HARVEST 展开为 markdown 图片引用：
   ```markdown
   ![caption](最终 URL)
   ```
4. rehost 任一步失败 → **降级保留远端 URL + 警告**（不阻断 pipeline）。

**GIF 保留：** 源图若为 GIF（URL 含 `wx_fmt=gif` 或 `.gif` 后缀），rehost 直传原 bytes，不走 Pillow 压缩通道，动图不变静图。

**为什么需要 rehost：** 微信 `mmbiz.qpic.cn` 对非 `mp.weixin.qq.com` 的 Referer **静默**返回 ~2KB 占位 JPEG（HTTP 200！没法看状态码判断）。文章发布到非公众号平台（Obsidian / 博客 / 知乎）时，读者浏览器 Referer 不匹配 → 图变糊占位符。rehost 把图挪到自家 CDN，彻底摆脱源站 Referer 检查。经验证：同 URL 用 `mp.weixin.qq.com` Referer 返回 96KB 原图，用 `google.com` Referer 返回 2086B 占位图。

**与 SCREENSHOT 的选择：**

| 场景 | 用哪个 |
|------|--------|
| 引用源文章里已有的图 | `HARVEST`（直引，若源站 hotlink 友好则省带宽；否则 auto rehost） |
| 截一个还没有图的页面（GitHub 仓库、文档） | `SCREENSHOT`（自己截、自己上 CDN） |
| 登录墙 / 付费墙的图 | 都不行，用 manual 本地路径 + `SCREENSHOT: /abs/path` |

**占位符处理阶段：**

screenshot skill 在扫描 `<!-- SCREENSHOT: -->` 的同时扫 `<!-- HARVEST: -->`：
- 读同目录 `_evidence.json`
- 按 `url + idx / alt` 查出目标图片 URL
- 原地替换为 `![caption](远端 url)`
- 查不到 → 警告 + 保留占位符

---

## 使用截图工具脚本

### 单个截图

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/screenshot_tool.py screenshot "https://github.com/user/repo"
```

**完整参数：**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/screenshot_tool.py screenshot "URL" \
  -o /tmp/output.png \        # 输出路径（默认 /tmp/）
  -s ".markdown-body" \       # CSS 选择器
  -w 2 \                      # 额外等待秒数
  --width 1280 \              # 视口宽度
  --no-upload \               # 跳过 CDN 上传
  --keywords AI Python        # 文章关键词（用于相关性判断）
```

### 批量截图

```bash
# JSONL 格式（每行一个 URL）
echo '{"url": "https://github.com/user/repo"}' > /tmp/batch.jsonl
echo '{"url": "https://npmjs.com/package/react", "wait": 2}' >> /tmp/batch.jsonl

python3 ${CLAUDE_PLUGIN_ROOT}/scripts/screenshot_tool.py batch /tmp/batch.jsonl -o /tmp/screenshots/
```

### 只验证 URL（不截图）

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/screenshot_tool.py check "https://github.com/user/repo"
```

### Harvest：从源文章抓图片清单（Style H 专用）

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/screenshot_tool.py harvest \
  "https://mp.weixin.qq.com/s/xxx" \
  -o /tmp/harvest.json \
  -w 2 \
  --min-width 200
```

- **Playwright 优先**：快、可 JS 渲染
- **baoyu-fetch 兜底**：遇 CAPTCHA / 登录墙 / 付费墙自动切换（需 `bun` + `baoyu-skills` 插件）
- 输出 JSON：`{source_url, title, method, images: [{idx, url, alt, context, width, height}], warnings, error}`
- `--no-fallback`：禁用兜底（纯 Playwright）
- 批量跑建议用 `evidence` skill 的 `evidence.py collect`，它会对 materials.md 里每条 URL 自动调用此命令

### Rehost：给带 hotlink 保护的远端图换托管（v1.4.6+）

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/screenshot_tool.py rehost \
  --url "https://mmbiz.qpic.cn/xxx?wx_fmt=jpeg" \
  --mode auto
```

- `--mode auto`（默认）：仅白名单 CDN（`mmbiz.qpic.cn` / `mmbiz.qlogo.cn` / `*.sinaimg.cn` / `pic*.zhimg.com`）才 rehost
- `--mode always`：每张图都 rehost
- `--mode never`：直接返回原 URL（占位符 `rehost=never` 的内部实现路径）
- 输出 JSON：`{ok, rehosted, original_url, final_url, reason, is_animated}`
- **exit code**：`0` = ok（含 rehosted=false 的跳过情况），`1` = 失败（final_url 回退到 original_url）
- 带正确 Referer 下载原图 → 自动识别扩展名（`wx_fmt` 查询参数 / URL 后缀 / Content-Type）→ 传给 `upload_image()` 上传到项目已配置的 CDN（PicGo 或 S3）
- **GIF 保留**：扩展名为 `.gif` 时，bytes 原样上传，S3 `Content-Type` 正确标为 `image/gif`，不走 Pillow 压缩通道
- **防静默占位符**：内容 < 4KB 视为 hotlink 挡回来的占位图，fail 且 final_url 回退

---

## Playwright 渲染策略

| 策略 | 说明 |
|------|------|
| 等待 networkidle | 等待网络空闲 + 3 秒 |
| 额外等待 | `WAIT:N` 参数，SPA / JS 渲染页面 |
| 拦截无效资源 | 自动拦截字体、websocket 请求，加速加载 |
| User-Agent | 模拟真实浏览器（Chrome on macOS） |
| 视口宽度 | 默认 1280px，可通过 `# WIDTH:N` 自定义 |

---

## 智能选择器推荐

脚本根据 URL 自动推荐最佳截图区域：

| URL 类型 | 推荐选择器 |
|---------|-----------|
| GitHub 仓库首页 | `#repo-content-pjax-container` |
| GitHub README | `.markdown-body` |
| GitHub Issue/PR | `.Timeline-Message` |
| Twitter 帖子 | `[data-testid="tweet"]` |
| Stack Overflow | `#question` |
| npm 包页面 | `.npm__container` |
| 文档类页面 | `article, main, .content` |

未指定选择器时：
1. 脚本根据 URL 推荐
2. 推荐后验证元素是否存在
3. 存在则使用，不存在则回退到全页截图

---

## 404 / 空页面检测

双重保障：

**Step 1 — HTTP HEAD 请求：**
- 状态码 404 → 直接跳过，不渲染
- 状态码 403/5xx → 警告，跳过
- 重定向链显示（用于调试）

**Step 2 — Playwright 渲染后：**
- `body.scrollHeight < 100px` → 空页面警告
- 页面文本匹配 404 特征 → 404 页面警告
- GitHub/Twitter 特有 404 文本模式识别

---

## 图片优化

| 优化项 | 说明 |
|-------|------|
| 大小上限 | >500KB 时自动按比例缩放 |
| 底部空白裁剪 | 空白超过 20% 时自动裁剪 |
| 格式 | PNG（保持清晰度） |
| 压缩质量 | 内部使用 LANCZOS 重采样 |

---

## 截图相关性原则

> **截图必须是真实内容，只在必要时才截。**

判断标准：
- 文章正文中直接引用或讨论的页面
- 用于说明某个具体功能、界面、数据的页面
- 不是装饰性截图或为了"看起来丰富"而堆砌

**避免的场景：**
- 截一个简单的命令文档（直接写命令更清晰）
- 截一个随手搜到的无关页面
- 截一个需要登录才能看到内容的页面（会截到登录页）
- 同一个工具的多个页面重复截图

---

## 常见场景处理

| 场景 | 建议 |
|------|------|
| GitHub 仓库 | 推荐 README 或关键代码文件，不用截整个仓库页面 |
| 代码演示 | 用代码块代替截图，代码更精确可复制 |
| API 文档 | 截取关键端点即可，不用截完整文档 |
| 终端输出 | 用代码块 + 语法高亮，不用截图 |
| 动态图表 | 截取静态图或用 Mermaid 代替 |
| 需要登录的页面 | 跳过，或使用 Cookie 导入（`setup-browser-cookies` skill） |
| 视频页面 | 截视频封面即可，不用截整个播放器 |

---

## 错误处理

| 场景 | 处理 |
|------|------|
| URL 返回 404 | 警告，保留占位符，提示修改 |
| 渲染后 404 | 警告，跳过截图 |
| 空页面 | 警告，建议增加 `WAIT:N` 或确认 URL |
| 连接超时 | 警告，增加超时重试 |
| 选择器不存在 | 回退到全页截图，警告用户 |
| CDN 上传失败 | 保留本地文件，提示手动上传 |

---

## 功能二：社交分享卡片

### 平台支持 & 尺寸

```
┌─────────────────┬──────────┬───────────┬──────────────────┐
│ 平台            │ 宽×高    │ 比例     │ 用途              │
├─────────────────┼──────────┼───────────┼──────────────────┤
│ wechat-cover    │ 900×383  │ 2.35:1   │ 公众号文章封面    │
│ wechat-share    │ 500×400  │ 5:4      │ 微信分享          │
│ xiaohongshu     │ 1080×1440│ 3:4      │ 小红书竖图封面    │
│ xiaohongshu-sq  │ 1080×1080│ 1:1      │ 小红书方图        │
│ twitter         │ 1200×628 │ 1.91:1   │ Twitter/X 分享   │
│ linkedin        │ 1200×627 │ 1.91:1   │ LinkedIn 文章    │
│ facebook        │ 1200×630 │ 1.91:1   │ Facebook OG 图   │
│ juejin          │ 1200×600 │ 2:1      │ 掘金文章封面      │
│ zhihu           │ 1200×600 │ 2:1      │ 知乎文章封面      │
└─────────────────┴──────────┴───────────┴──────────────────┘
```

### 配色方案

| 名称 | 渐变风格 | 强调色 |
|------|---------|--------|
| `tech-blue` | 深青 → 蓝绿 | 青色 #00d4ff |
| `sunset` | 紫 → 蓝 → 粉 | 粉色 #ff6b95 |
| `forest` | 深青 → 翠绿 | 绿色 #34e89e |
| `midnight` | 黑 → 深蓝 | 金色 #ffd700 |
| `ember` | 黑棕 → 橙 → 金 | 金色 #eaaf0b |
| `deep-blue` | 深蓝 → 浅蓝 | 白色 |
| `slate` | 深灰 → 中灰 | 翠绿 #10b981 |

### 使用方法

```bash
# 完整参数
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/share_card.py \
  -t "文章标题" \
  -d "文章摘要描述" \
  --tags AI 编程 Claude \
  --author 月影 \
  --platforms wechat-cover,twitter,xiaohongshu-sq \
  --color tech-blue \
  -o /tmp/cards

# 从 Markdown 文件自动读取 frontmatter
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/share_card.py -f /path/to/article.md -p wechat-cover,twitter
```

### 从文章 frontmatter 自动读取

```yaml
---
title: "Claude Code 完全指南"
description: "从安装到高级技巧，全面掌握使用方法"
tags: [AI, Claude, 编程]
author: 月影
---
```

### 上传到 CDN

```bash
# 生成后自动上传（需安装 picgo）
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/share_card.py -t "标题" -p wechat-cover,twitter --upload
```

### 卡片设计规范

- **深色渐变背景** — 7 种预设配色，无外部图片依赖
- **技术风格** — 等宽字体标签，圆角徽章
- **中文优先** — PingFang SC / Microsoft YaHei / Noto Sans SC
- **装饰元素** — 顶部强调色线，背景柔光圆，底部作者栏
- **无外部依赖** — 纯内联 CSS，系统字体，离线可用

---

## 依赖

```bash
pip install playwright requests Pillow
playwright install chromium
```

或运行：
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/setup_dependencies.py
```
