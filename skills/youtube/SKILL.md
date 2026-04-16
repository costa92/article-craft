---
name: article-craft:youtube
version: 1.4.10
description: "Transform YouTube video content into structured technical articles. Extracts transcript, analyzes content, and generates polished articles. Use when converting video to article."
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - WebFetch
  - AskUserQuestion
---

# YouTube 视频转文章

将 YouTube 视频内容整理为结构化技术文章。

---

## 输入

- YouTube URL（必须）
- 文章语言偏好（可选，默认与视频语言一致）
- 输出格式偏好（可选，默认 standard）

### 独立模式

如果没有提供 URL，使用 AskQuestion 询问：
1. YouTube 视频链接
2. 目标语言（中文/英文/保持原文）
3. 文章类型（教程/总结/深度分析）

---

## 处理流程

### Step 1: 提取视频信息

使用 `yt-dlp` 获取视频元数据：

```bash
# 获取视频标题、描述、时长、频道
yt-dlp --cookies-from-browser=chrome --dump-json "VIDEO_URL" 2>/dev/null | \
  python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f\"TITLE: {d.get('title', '')}\" )
print(f\"CHANNEL: {d.get('channel', '')}\" )
print(f\"DURATION: {d.get('duration_string', '')}\" )
print(f\"UPLOAD_DATE: {d.get('upload_date', '')}\" )
print(f\"DESCRIPTION: {d.get('description', '')[:500]}\" )
print(f\"TAGS: {','.join(d.get('tags', [])[:10])}\" )
"
```

如果 `yt-dlp` 不可用，使用 WebFetch 获取页面标题和描述。

### Step 2: 提取字幕/转录稿

**优先级：**

1. **yt-dlp 下载字幕**（最快）：

```bash
# 下载字幕文件（优先中文，回退英文）
yt-dlp --cookies-from-browser=chrome \
  --write-auto-sub --write-sub \
  --sub-lang zh-Hans,zh-Hant,zh,en \
  --sub-format vtt \
  --skip-download \
  --output "/tmp/yt-transcript-%(id)s.%(ext)s" \
  "VIDEO_URL"
```

2. **回退方案**：如果 yt-dlp 失败，提示用户安装 yt-dlp 或使用其他字幕获取方法

3. **解析字幕文件**：

```bash
# VTT 转纯文本（去除时间戳和重复行）
python3 -c "
import re, sys
content = open(sys.argv[1]).read()
# 去除 VTT 头部和时间戳行
lines = []
seen = set()
for line in content.split('\n'):
    line = line.strip()
    if not line or line.startswith('WEBVTT') or line.startswith('Kind:') or line.startswith('Language:'):
        continue
    if re.match(r'^\d{2}:\d{2}', line) or re.match(r'^\d+$', line):
        continue
    # 去除 HTML 标签
    clean = re.sub(r'<[^>]+>', '', line)
    if clean and clean not in seen:
        seen.add(clean)
        lines.append(clean)
print('\n'.join(lines))
" /tmp/yt-transcript-*.vtt > /tmp/yt-transcript-clean.txt
```

### Step 3: 内容分析与结构化

读取清理后的转录文本，分析并结构化：

**分析要点：**

1. **识别核心主题** — 视频主要讲什么
2. **提取关键章节** — 按内容转折点分段（通常 3-7 个章节）
3. **识别关键观点** — 每个章节的核心论点
4. **提取代码/命令** — 视频中展示的代码片段或命令
5. **识别引用数据** — 统计数据、对比数据、基准测试结果
6. **标记关键时间点** — 重要内容对应的视频时间戳

**结构化输出模板：**

```
主题: {核心主题}
类型: {教程|分享|评测|访谈|会议演讲}
章节:
  1. {章节标题} (00:00 - 05:30)
     - 关键点 1
     - 关键点 2
  2. {章节标题} (05:30 - 12:00)
     ...
代码片段:
  - {描述}: {代码}
关键数据:
  - {数据点}
```

### Step 4: 生成文章

基于结构化内容，调用 `article-craft:write` 的写作规范生成文章。

**文章特殊规范：**

1. **YAML frontmatter** 增加来源信息：

```yaml
---
title: "{文章标题}"
date: {today}
tags: [{从视频标签提取}]
category: "{分类}"
status: draft
source:
  type: youtube
  url: "{VIDEO_URL}"
  title: "{原始视频标题}"
  channel: "{频道名}"
  duration: "{时长}"
  upload_date: "{上传日期}"
description: "{120字以内摘要}"
---
```

2. **开头注明来源**：

```markdown
> [!info] 本文整理自视频
> **{视频标题}** — {频道名}
> 视频链接：[YouTube]({VIDEO_URL}) | 时长：{时长}
```

3. **章节结构** — 按视频内容章节组织，每章节标注时间范围
4. **代码块** — 视频中出现的代码完整还原
5. **个人评论** — 至少 2 处加入作者视角的补充说明（标记为 > [!tip] 编者注）
6. **关键截图** — 为重要画面添加截图占位符：

```markdown
<!-- SCREENSHOT: {VIDEO_URL}&t={SECONDS} -->
```

7. **总结段** — 提炼视频核心价值 + 延伸阅读建议

**写作质量要求：**
- 遵循 `references/self-check-rules.md` 全部 11 条规则
- 不是简单的逐句翻译，而是**重新组织为易读的文章结构**
- 合并重复内容，删除口语化的填充词
- 补充必要的背景知识和上下文

### Step 5: 可选 — 翻译/双语

如果视频语言与目标语言不同：

- 使用 AskQuestion 确认：
  - A) 翻译为中文（保留关键术语英文）
  - B) 保持原文
  - C) 中英双语对照

翻译规则：
- 技术术语保留英文（如 Kubernetes, Docker, API）
- 人名/产品名保留原文
- 代码块不翻译

### Step 6: 保存文章

```bash
# 保存到当前目录或知识库
ARTICLE_PATH="{sanitized-title}.md"
```

输出完成摘要：

```
┌─────────────────────────────────────────────────┐
│         YouTube → Article — 完成                │
├───────────────┬─────────────────────────────────┤
│ 视频          │ {视频标题}                      │
│ 频道          │ {频道名}                        │
│ 时长          │ {时长}                          │
│ 字幕语言      │ {语言}                          │
│ 文章章节      │ {N} 个                          │
│ 代码片段      │ {N} 个                          │
│ 文件路径      │ {绝对路径}                      │
│ 字数          │ {word_count}                    │
└───────────────┴─────────────────────────────────┘
```

---

## Hand-off

生成文章后，可以继续使用 article-craft 管道的后续技能：

- `/article-craft:screenshot` — 截取视频关键画面
- `/article-craft:images` — 生成配图
- `/article-craft:review` — 质量审查
- `/article-craft:publish` — 发布到知识库

---

## 错误处理

| 场景 | 处理 |
|------|------|
| 视频无字幕 | 提示用户，建议使用 Whisper 本地转录或等待自动字幕生成 |
| yt-dlp 未安装 | `brew install yt-dlp` 或 `pip install yt-dlp` |
| Cookie 浏览器错误 | AskQuestion 让用户选择浏览器 (chrome/firefox/safari/edge) |
| 字幕语言不匹配 | 列出可用语言，让用户选择 |
| 视频过长 (>2h) | 警告可能超出上下文限制，建议分段处理 |
| 年龄限制/地区限制 | 提示需要 VPN 或登录 cookie |

## 依赖

- `yt-dlp`（字幕下载，`brew install yt-dlp` 或 `pip install yt-dlp`）
- `article-craft:write` 写作规范（引用 style-guide 和 self-check-rules）
