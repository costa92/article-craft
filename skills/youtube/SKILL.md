---
name: article-craft:youtube
version: 1.9.8
description: "Transform YouTube video content into structured technical articles. Extracts transcript, analyzes content, and generates polished articles. Use when converting video to article."
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - WebFetch
  - AskUserQuestion
  - Skill
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

### Step 1 + 2: 提取元数据 + 字幕（一次到位）

> [!warning] 不要用 `yt-dlp --dump-json` 拉元数据
> 2026 年起 YouTube 的 n-challenge JavaScript 反爬会让 `yt-dlp` 在不带 cookies
> 时直接报 `Requested format is not available`，连元数据都拉不到。
> **优先走 InnerTube API** 路径（下面 Method A），它走视频内嵌 API 不走 web 解析。

#### Method A（推荐）：调用 `baoyu-skills:baoyu-youtube-transcript` skill

如果 vault 里装了 `baoyu-skills` 插件（最常见情况），**优先用 Skill 工具按名字调用**——
不要 shell out 到具体文件路径，因为插件 cache 的目录结构是
`~/.claude/plugins/cache/baoyu-skills/baoyu-skills/<hash>/...`，hash
会随版本变。Skill 工具会处理路径解析。

```
Skill(skill="baoyu-skills:baoyu-youtube-transcript",
      args="<VIDEO_URL>")
```

baoyu skill 内部实现了 InnerTube 直连 + 多 client 轮换 + yt-dlp 兜底 +
cookie 自动尝试，是 article-craft 目前测过最稳的字幕入口。它会按需提示
你设 `YOUTUBE_TRANSCRIPT_COOKIES_FROM_BROWSER=chrome`（首次跑撞 bot
detection 时用）。

如果你**确实需要从 Bash 直接调脚本**（例如 Skill 工具在当前上下文不可用），
正确的 glob 是带两层 `baoyu-skills/baoyu-skills/<hash>/`，且要先校验
`main.ts` 实际存在：

```bash
# 校验路径并执行
BAOYU_TS=$(ls ~/.claude/plugins/cache/baoyu-skills/baoyu-skills/*/skills/baoyu-youtube-transcript/scripts/main.ts 2>/dev/null | tail -1)
if [ -z "$BAOYU_TS" ]; then
  echo "baoyu-youtube-transcript not found, fall back to Method B"
else
  YOUTUBE_TRANSCRIPT_COOKIES_FROM_BROWSER=chrome bun "$BAOYU_TS" '<VIDEO_URL>' --list
  # 选定语言后：
  YOUTUBE_TRANSCRIPT_COOKIES_FROM_BROWSER=chrome bun "$BAOYU_TS" '<VIDEO_URL>' --languages en --chapters
fi
```

**URL 必须单引号**——zsh 把 `?` 当 glob，不引号会报 "no matches found"。

产出（缓存在 `youtube-transcript/<channel-slug>/<title-slug>/`）：
- `meta.json` — 标题、频道、时长、上传日、描述、章节列表、封面路径
- `transcript.md` — 章节分段的可读 markdown
- `transcript-raw.json` — 原始 snippet 数据
- `transcript-sentences.json` — 句子级分段（用于跨段引用）
- `imgs/cover.jpg` — 视频封面

#### Method B：自带 `yt-dlp`，cookies 上来就给

只有在 baoyu 不可用、且系统 `yt-dlp` ≥ 2024.x 时才走这条。**关键是 cookies
从一开始就要带上**——`--dump-json` 在没 cookies 时几乎必失败。

```bash
# Step 1: 元数据 — 用 --print 绕过 dump-json 的 format check
yt-dlp --cookies-from-browser=chrome --skip-download --no-warnings \
  --print "%(title)s|||%(channel)s|||%(duration_string)s|||%(upload_date)s|||%(description)s" \
  '<VIDEO_URL>'

# Step 2: 字幕
yt-dlp --cookies-from-browser=chrome \
  --write-auto-sub --write-sub \
  --sub-lang zh-Hans,zh-Hant,zh,en \
  --sub-format vtt \
  --skip-download \
  --output "/tmp/yt-transcript-%(id)s.%(ext)s" \
  '<VIDEO_URL>'
```

如果 `--cookies-from-browser=chrome` 拿不到 cookies（用户没开过 Chrome 看 YouTube），
依次试 `firefox`、`safari`、`edge`。

#### Method C（彻底兜底）：WebFetch

仅在 A/B 都失败时使用——拿不到字幕，只能用页面的 transcript 面板或描述：

```
WebFetch(url, "提取标题、频道、时长、上传日和完整字幕（如果可见）")
```

WebFetch 拿不到自动生成字幕，**视频如果只有 auto-caption 就要告诉用户跳过这条**。

#### Bot detection 处理

任意一种方法报 "bot detected" / "Sign in to confirm you're not a bot"，
按下列顺序处理：

1. 已经在用 `--cookies-from-browser`？换浏览器（chrome → firefox → safari）
2. 还没用 cookies？立刻加 `--cookies-from-browser=chrome`（或 baoyu 的 env var）
3. 仍然失败 → 转 Method C，并在文章 frontmatter 标 `transcript_source: webfetch_partial`

### Step 3: 内容分析与结构化

读取清理后的转录文本，分析并结构化：

**分析要点：**

1. **识别核心主题** — 视频主要讲什么
2. **提取关键章节** — 优先用 `meta.json` 里的 `chapters` 字段（YouTube 描述区已有时间码时直接拿到）；缺失则按内容转折点分段（3-7 个章节）
3. **识别关键观点** — 每个章节的核心论点
4. **提取代码/命令** — 视频中展示的代码片段或命令
5. **识别引用数据** — 统计数据、对比数据、基准测试结果
6. **标记关键时间点** — 重要内容对应的视频时间戳
7. **核对外部资料** — 视频描述里通常有 GitHub repo / 产品站链接，**写文章前先 `gh repo view` 或 WebFetch 一次**，拉回真实的 README / release notes —— 视频是营销口径，repo 是工程事实，前者可能漏说或夸大

**结构化输出模板**（保存为 `outline.json` 或直接传给 write）：

```json
{
  "topic": "<核心主题，10-20 字>",
  "type": "tutorial | walkthrough | review | interview | conference",
  "audience": "intermediate | advanced",
  "depth": "tutorial | deep",
  "sections": [
    {"title": "...", "start": "00:00", "end": "05:30", "key_points": ["..."]},
    ...
  ],
  "code_snippets": [{"desc": "...", "code": "..."}],
  "facts_to_verify": ["真实仓库地址", "版本号", "基准数据"]
}
```

### Step 4: 生成文章 — handoff 到 `article-craft:write`

> [!important] 调用约定
> youtube skill **不亲自写正文**——它产出结构化大纲，然后调用 `article-craft:write`
> 走完 GATE 流程（rules 1/2/6/13/14/16 检查）。如果跳过这步直接 inline 写文章，
> write 的 pre-save GATE 完全不会运行，导致红旗词 / 章节深度 / ASCII 字符 /
> 代码块语言 tag 这些违规漏到 review 阶段才被发现。**别这么干。**

调用方式（agent 在主对话里通过 Skill 工具调用）：

```
Skill(skill="article-craft:write", args="<JSON 字符串>")
```

`args` 内容（基于 Step 3 的 outline.json + 视频元数据）：

```json
{
  "topic": "<outline.topic>",
  "audience": "<outline.audience>",
  "depth": "<outline.depth>",
  "writing_style": "B",
  "key_points": "<outline.sections 拍平>",
  "save_path": "<由 write Step 2 自动决定，或由用户指定>",
  "source": {
    "type": "youtube",
    "url": "<VIDEO_URL>",
    "title": "<meta.json.title>",
    "channel": "<meta.json.channel>",
    "duration": "<meta.json.duration>",
    "upload_date": "<meta.json.publishDate>"
  },
  "transcript_path": "<meta.json 同目录的 transcript.md>"
}
```

**writing_style 默认为 B（经验分享）**——YouTube 视频转文章天然适合 B 风格的
口语化 + 高频截图节奏；如果视频本身是会议演讲 / 源码拆解，可以改 C（深度）。
详见 `references/writing-styles.md`。

**write skill 会自动处理：**

- YAML frontmatter（含 `source.*` 嵌套字段）
- 文章顶部的 `> [!info] 本文整理自视频` callout
- 章节结构 + 时间戳
- 至少 2 处编者注（`> [!tip] 编者注`）
- 截图占位符（每章一个 `<!-- SCREENSHOT: VIDEO_URL&t=SECONDS -->`）
- Rule 7b 要求的最少 AI 图片数量（cover + 节奏图）
- pre-save GATE 检查（Step 6 调用 `review_selfcheck.py --write-gate`）

如果你（agent）不能在当前会话用 Skill 工具调用 write（例如已经在 write
skill 的子会话里），那就**严格遵守 `skills/write/SKILL.md` Step 1-7 的全部
流程**，包括 Step 6 的 `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/review_selfcheck.py
--write-gate` GATE 检查——不可省略。

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

### Step 6: 保存 + 写 pipeline state

article.md 由 write skill 保存。回到 youtube skill 后做两件事：

1. **写 pipeline_state**（让 `--upgrade` 模式能识别这篇文章的 stage 进度）：

```bash
# write 已经存在 article.md 后
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/pipeline_state.py init \
  --article /ABSOLUTE/PATH/article.md \
  --mode standard \
  --writing-style B

python3 ${CLAUDE_PLUGIN_ROOT}/scripts/pipeline_state.py complete \
  --article /ABSOLUTE/PATH/article.md \
  --stage requirements \
  --result "$(cat <<'EOF'
{"topic": "<outline.topic>", "audience": "<outline.audience>", "depth": "<outline.depth>",
 "writing_style": "B", "trusted_sources_count": 1, "source_type": "youtube"}
EOF
)"

python3 ${CLAUDE_PLUGIN_ROOT}/scripts/pipeline_state.py complete \
  --article /ABSOLUTE/PATH/article.md \
  --stage write \
  --result "$(cat <<'EOF'
{"article_path": "...", "word_count": NNNN, "section_count": N,
 "image_placeholders": M, "screenshot_placeholders": K, "harvest_placeholders": 0}
EOF
)"
```

如果 verify 阶段在 youtube 这条分支里被跳过（视频本身就是 T2 一手来源），
显式 skip 而不是不写：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/pipeline_state.py skip \
  --article /ABSOLUTE/PATH/article.md \
  --stage verify \
  --reason "source is single T2 video transcript; URL-vetting not applicable"
```

2. **输出完成摘要：**

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
│ pipeline state│ initialized (write completed)   │
└───────────────┴─────────────────────────────────┘
```

---

## Hand-off

写完 article.md + 写完 pipeline state 后，剩下的阶段由 orchestrator 或用户接管：

- `/article-craft:screenshot` — 展开 `<!-- SCREENSHOT: -->` 占位符（含视频帧）
- `/article-craft:images` — 生成 `<!-- IMAGE: -->` 配图
- `/article-craft:review` — 23 条 self-check + 8 维度评分
- `/article-craft:publish` — 发布到知识库

如果用户后续想接着跑，`/article-craft --upgrade /path/to/article.md` 会自动
检测 pipeline state 走只缺的 stage。

---

## 错误处理

| 场景 | 处理 |
|------|------|
| 视频无字幕 | 提示用户，建议 Whisper 本地转录或等待自动字幕生成 |
| yt-dlp 报 "Requested format is not available" | YouTube n-challenge 阻断，切到 Method A 或加 `--cookies-from-browser` |
| yt-dlp / baoyu 报 "bot detected" / "Sign in to confirm" | 按 §Step 1+2 的 "Bot detection 处理" 顺序试 |
| Cookie 浏览器错误 | AskQuestion 让用户选择浏览器 (chrome/firefox/safari/edge)，或要求用户登录一次目标浏览器 |
| 字幕语言不匹配 | `--list` 列出可用语言，让用户选择 |
| 视频过长 (>2h) | 警告可能超出上下文限制，建议分段处理（按 chapters 切片喂给 write） |
| 年龄限制/地区限制 | 提示需要登录 cookie，或 VPN |
| 视频描述里有 GitHub repo | **不要只信视频**，跑一次 `gh repo view <repo>` + 读 release notes，把官方口径写进 outline.facts_to_verify |

## 依赖

- **首选**：`baoyu-skills:baoyu-youtube-transcript`（bun runtime + InnerTube API，最稳）
- **兜底**：`yt-dlp` ≥ 2024.x（`brew install yt-dlp` 或 `pip install yt-dlp`），且需要本机有登录过的浏览器 cookies
- **必需**：`article-craft:write`（Step 4 的 handoff 目标）
- **必需**：`scripts/pipeline_state.py`（Step 6 的 state 写入）
