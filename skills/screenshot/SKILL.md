---
name: article-craft:screenshot
version: 1.1.0
description: "Take web page screenshots and generate social media sharing cards. Use when capturing web content for articles or creating platform-specific share images."
---

# Screenshot — 网页截图 & 社交平台分享卡片

两大功能：
1. **网页截图** — 截取网页/社交帖子嵌入文章
2. **社交分享卡片** — 为文章生成各平台分享图

---

## 功能一：网页截图

### 输入

- 文章中的截图占位符：`<!-- SCREENSHOT: URL -->`
- 或直接提供 URL

### 占位符格式

```markdown
<!-- SCREENSHOT: https://github.com/user/repo -->
<!-- SCREENSHOT: https://twitter.com/user/status/123 -->
<!-- SCREENSHOT: https://example.com #element-selector -->
<!-- SCREENSHOT: https://example.com WAIT:3 -->
```

**扩展语法：**
- `#selector` — 只截取页面中特定元素（CSS 选择器）
- `WAIT:N` — 等待 N 秒后截图（适合动态加载页面）
- `WIDTH:N` — 设置视口宽度（默认 1280）

### 处理流程

1. **扫描文章** 中的 `<!-- SCREENSHOT: ... -->` 占位符
2. **逐个截取**，使用 `shot-scraper`：

```bash
# 基础截图
shot-scraper "URL" -o /tmp/screenshot-{name}.png --width 1280

# 指定元素截图
shot-scraper "URL" -s "#element-selector" -o /tmp/screenshot-{name}.png

# 等待后截图
shot-scraper "URL" --wait 3000 -o /tmp/screenshot-{name}.png

# 指定宽度
shot-scraper "URL" --width 800 -o /tmp/screenshot-{name}.png
```

3. **上传到 CDN**：

```bash
# 使用 PicGo
picgo upload /tmp/screenshot-{name}.png

# 或使用 generate_and_upload_images.py 的上传功能
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_and_upload_images.py \
  --upload-only /tmp/screenshot-{name}.png
```

4. **替换占位符** 为 Markdown 图片：

```markdown
![screenshot-name](https://cdn.example.com/screenshot-name.png)
```

5. **验证** 无残留占位符：`grep "<!-- SCREENSHOT:" article.md`

### 常见截图场景

| 场景 | 命令示例 |
|------|---------|
| GitHub 仓库 | `shot-scraper "https://github.com/user/repo" -o repo.png --width 1280` |
| Twitter 帖子 | `shot-scraper "https://twitter.com/user/status/123" -s "article" -o tweet.png` |
| 代码片段 | `shot-scraper "https://carbon.now.sh/?code=..." -s ".export-container" -o code.png` |
| 终端输出 | 使用 `script` + `svg-term` 或直接代码块 |
| API 文档 | `shot-scraper "https://docs.example.com/api" -s ".content" -o api.png --wait 2000` |
| Grafana 面板 | `shot-scraper "URL" -s ".panel-container" -o dashboard.png --wait 5000` |

---

## 功能二：社交平台分享卡片

### 输入

- 文章标题、摘要、标签
- 文章文件路径（自动从 YAML frontmatter 提取）
- 目标平台（可多选）

### 支持平台 & 尺寸

```
┌───────────────┬────────────┬──────────┬──────────────────────┐
│ 平台          │ 尺寸(px)   │ 比例     │ 用途                 │
├───────────────┼────────────┼──────────┼──────────────────────┤
│ 微信封面      │ 900×383    │ 2.35:1   │ 公众号文章头图       │
│ 微信分享      │ 500×400    │ 5:4      │ 分享到聊天/朋友圈    │
│ 小红书        │ 1080×1440  │ 3:4      │ 笔记封面             │
│ 小红书方图    │ 1080×1080  │ 1:1      │ 笔记配图             │
│ Twitter/X     │ 1200×628   │ 1.91:1   │ Summary large image  │
│ LinkedIn      │ 1200×627   │ 1.91:1   │ 文章分享图           │
│ Facebook      │ 1200×630   │ 1.91:1   │ Open Graph image     │
│ 掘金/知乎     │ 1200×600   │ 2:1      │ 文章封面             │
└───────────────┴────────────┴──────────┴──────────────────────┘
```

### 处理流程

1. **提取文章信息**（从 YAML frontmatter 或 AskQuestion）：
   - 标题（title）
   - 摘要（description）
   - 标签（tags）
   - 作者（默认：月影）
   - 封面色调（可选）

2. **生成分享卡片 HTML**：

为每个目标平台生成一个自适应尺寸的 HTML 文件：

```bash
CARD_FILE="/tmp/article-craft-card-{platform}-$(date +%s).html"
```

卡片设计规范：
- **简洁专业** — 大标题 + 摘要 + 标签 + 品牌标识
- **技术风格** — 深色/渐变背景，等宽字体标签
- **无外部依赖** — 纯内联 CSS，系统字体
- **中文优先** — font-family: "PingFang SC", "Microsoft YaHei", sans-serif

HTML 模板结构：

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    width: {WIDTH}px;
    height: {HEIGHT}px;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif;
    color: #fff;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 60px;
    overflow: hidden;
  }
  .title {
    font-size: {TITLE_SIZE}px;
    font-weight: 700;
    line-height: 1.3;
    margin-bottom: 24px;
  }
  .description {
    font-size: {DESC_SIZE}px;
    color: rgba(255,255,255,0.75);
    line-height: 1.6;
    margin-bottom: 32px;
  }
  .tags {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
  }
  .tag {
    background: rgba(255,255,255,0.15);
    border: 1px solid rgba(255,255,255,0.25);
    border-radius: 6px;
    padding: 6px 16px;
    font-size: 14px;
    font-family: "SF Mono", "Fira Code", monospace;
  }
  .author {
    position: absolute;
    bottom: 40px;
    right: 60px;
    font-size: 16px;
    color: rgba(255,255,255,0.5);
  }
</style>
</head>
<body>
  <div class="title">{TITLE}</div>
  <div class="description">{DESCRIPTION}</div>
  <div class="tags">
    {TAGS_HTML}
  </div>
  <div class="author">{AUTHOR}</div>
</body>
</html>
```

**各平台字体大小适配：**

| 平台 | WIDTH | HEIGHT | TITLE_SIZE | DESC_SIZE |
|------|-------|--------|------------|-----------|
| 微信封面 | 900 | 383 | 36 | 16 |
| 微信分享 | 500 | 400 | 28 | 14 |
| 小红书 | 1080 | 1440 | 48 | 20 |
| 小红书方图 | 1080 | 1080 | 44 | 18 |
| Twitter/X | 1200 | 628 | 42 | 18 |
| LinkedIn | 1200 | 627 | 42 | 18 |
| 掘金/知乎 | 1200 | 600 | 42 | 18 |

3. **截图生成 PNG**：

```bash
shot-scraper "$CARD_FILE" -o /tmp/card-{platform}.png --width {WIDTH} --height {HEIGHT}
```

4. **上传到 CDN**（可选）：

```bash
# PicGo 上传
picgo upload /tmp/card-{platform}.png

# 或手动使用
```

5. **输出结果**：

```
┌──────────────────────────────────────────────────────┐
│              社交分享卡片 — 生成完成                  │
├───────────────┬──────────────────────────────────────┤
│ 平台          │ 文件 / CDN URL                       │
├───────────────┼──────────────────────────────────────┤
│ 微信封面      │ /tmp/card-wechat-cover.png           │
│ 小红书        │ /tmp/card-xiaohongshu.png            │
│ Twitter/X     │ /tmp/card-twitter.png                │
└───────────────┴──────────────────────────────────────┘
```

---

## 独立使用模式

### 截取网页

```
/article-craft:screenshot https://github.com/user/repo
/article-craft:screenshot https://twitter.com/user/status/123 #article
```

如果没有提供 URL，使用 AskQuestion 询问：
- 要截取的 URL
- 是否截取特定元素（CSS 选择器）
- 输出文件路径

### 生成分享卡片

```
/article-craft:screenshot --card /path/to/article.md
/article-craft:screenshot --card --platform wechat,xiaohongshu
```

如果没有提供文件路径，使用 AskQuestion 询问：
- 文章路径或手动输入标题/摘要
- 目标平台（多选）
- 是否上传到 CDN

---

## 编排模式

在 orchestrator 中，screenshot 在 write 之后、images 之前执行：

```
requirements → verify → write → screenshot → images → review → publish
```

- 处理文章中的 `<!-- SCREENSHOT: ... -->` 占位符
- 与 images 技能互补：images 处理 Gemini 生成图，screenshot 处理网页截图

---

## 错误处理

| 场景 | 处理 |
|------|------|
| URL 无法访问 | 警告，保留占位符，继续处理其他截图 |
| shot-scraper 未安装 | `pip install shot-scraper && shot-scraper install` |
| 元素选择器未找到 | 回退到全页截图，警告用户 |
| CDN 上传失败 | 保留本地路径，提示手动上传 |
| 动态页面加载超时 | 增加 WAIT 时间到 10s 重试一次 |

## 依赖

- `shot-scraper` (已在 article-craft requirements.txt 中)
- Playwright 浏览器 (shot-scraper 自动管理)
- PicGo 或 S3 上传（可选，用于 CDN）
