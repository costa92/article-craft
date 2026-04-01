---
name: article-craft
version: 1.3.0
description: "Enhanced full article generation pipeline — orchestrated with intelligent inference, source trust detection, and structure validation. Uses multi-layer requirements, T0-T5 verification focus, and section depth enforcement."
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - AskUserQuestion
  - WebSearch
  - Glob
  - Grep
  - Agent
---

# Article Craft — Orchestrator

Composes 7 skills into a complete article generation pipeline. Each skill can also
be used independently via `/article-craft:<skill-name>`.

## Workflow Modes

Three modes, selected at invocation:

| Mode | Skills Executed | Use Case |
|------|----------------|----------|
| **standard** (default) | requirements → verify → write → screenshot → images → review → publish | Full article with quality gate |
| **quick** (`--quick`) | requirements → write → screenshot → images | Fast output, skip verification and review |
| **draft** (`--draft`) | requirements → write | Content only, no images or review |
| **series** (`--series FILE`) | Read series.md → requirements (pre-filled) → standard pipeline | Write the next article in a series |

## Inputs

- **Topic** (optional): If provided as argument, skip requirements skill
- **Mode flag**: `--quick` or `--draft` (default: standard)
- **File path** (optional): If an existing article.md is provided, skip to the next unfinished stage
- **Upgrade flag**: `--upgrade` with a file path — upgrade a draft/quick article to standard
- **Series flag**: `--series SERIES_FILE` — write the next planned article in the series (reads topic, audience, depth, visual style from series.md)

## Upgrade Mode

When invoked with `--upgrade /path/to/article.md`, determine what's already done and run only the missing stages:

```
Detection logic:
  1. Has CDN image URLs?  → images already done, skip images
  2. Has <!-- IMAGE: --> placeholders?  → images NOT done, run images
  3. Has <!-- SCREENSHOT: --> placeholders?  → screenshots NOT done, run screenshots
  4. File is in 02-技术/ KB directory?  → publish already done, skip publish
  5. Ask user: "生成分享卡片？" → 用户确认后才运行 share_card

Upgrade paths:
  draft → standard:  run verify → screenshot → share_card → images → review → publish
  draft → quick:     run screenshot → share_card → images
  quick → standard:  run verify → review → publish
```

Skip stages that have already been completed. Show the upgrade plan before executing:

```
Upgrading: /path/to/article.md
  verify:     will run (not done)
  screenshot: will run (2 placeholders found)
  images:     will run (3 placeholders found)
  review:     will run (not done)
  publish:    will run (not in KB)
  Proceed? [Y/n]
```

## Pipeline Execution

### Step 1: Determine Mode

Parse the invocation arguments:
- No flags → standard mode (all 7 skills)
- `--quick` → quick mode (requirements + write + screenshot + images)
- `--draft` → draft mode (requirements + write only)
- If a file path to an existing `.md` file is provided → skip requirements/verify/write,
  start from images skill

### Step 2: Initialize Status Tracker

Track each skill's status throughout the pipeline:

```
Pipeline Status:
  requirements: pending
    └─ multi-layer inference (5 layers)
    └─ trusted sources: T0-T5 classification
  verify:       pending
    └─ focus: T3-T5 sources, skip T0-T1 links
  write:        pending
    └─ section depth check: ≥2 code blocks per ##
  screenshot:   pending
  share_card:   pending   # 可选，标准模式询问用户
```
  images:       pending
  review:       pending
  publish:      pending
```

Update status as each skill runs: `pending → running → success | failed | skipped`

### Step 3: Execute Skills Sequentially

Execute each skill in order, passing context between them.

#### 3.1 Requirements (all modes)

Invoke `article-craft:requirements` skill logic:
- **Multi-layer inference**: Intent Detection → Keyword Signals → Context Awareness → Ambiguity Resolution → Source Trust Detection
- **Smart inference first**: Analyze the topic for writing style, depth, audience, and format signals
- **Source trust detection**: Automatically find official docs/repo/blog, classify into T0-T5 tiers
- If topic was provided as argument, pre-fill and skip the topic question
- Show inferred values as a single confirmation question (not 5-7 separate questions)
- **Mode-aware**: In draft mode, skip image-related questions entirely
- **Output trusted sources**: Pass `_trusted_sources` to verify skill
- Store gathered context in memory for downstream skills

**On failure:** Retry (user input errors are unlikely)
**Status:** Mark `success` when requirements are confirmed

#### 3.2 Verify (standard mode only)

Invoke `article-craft:verify` skill logic:
- **Source trust focus**: Prioritize verification of T3-T5 sources, skip T0-T1 link checks
- Extract tool names and URLs from the topic/context
- **Use requirements' trusted sources**: T0-T1 sources from requirements are pre-verified
- Run batch verification (links, commands, feature discovery)
- Use Standard verification mode by default
- **前台阻塞执行**（不用 `run_in_background`），确保结果在 write 之前可用
- 如果验证超时（>60s），降级为跳过，write 使用自身 WebSearch 结果
- **缓存验证结果**：工具版本号、链接有效性等，传递给 Step 3.3
- **URL 缓存**：verify skill 会将 URL 状态写入 `~/.cache/article-craft/verify-cache.json`，screenshot_tool.py 会优先读取此缓存（TTL 1h）

**On failure:** Report failures but continue — verification is non-blocking
**Status:** Mark `success` (even with individual link/command failures)

> [!note]
> Skipped in quick and draft modes. Mark as `skipped`.

#### 3.3 Write (all modes)

Invoke `article-craft:write` skill logic:
- Pass requirements context from Step 3.1
- **Pass verification results**（如果 verify 返回了工具版本号，写作时应引用这些精确版本号而非自行搜索）
- **Pass trusted sources**: Use official docs URLs for accuracy
- Generate article with YAML frontmatter, Obsidian callouts, image placeholders
- **Apply section depth rules**: Each technical section must have ≥2 code blocks
- **Auto-check during writing**: Run section depth check for each ## before moving on
- Apply self-check rules from `references/self-check-rules.md`
- Save article.md to disk
- **Capture the absolute file path** — this is passed to all subsequent skills

**On failure:** FATAL — pipeline stops. Report what completed so far.
**Status:** Mark `success` when article.md is saved

#### 3.4 Screenshot (standard and quick modes)

Invoke `article-craft:screenshot` skill logic:
- Pass the article.md absolute file path from Step 3.3
- Scan for `<!-- SCREENSHOT: URL [options] -->` placeholders in the article
- Take screenshots via `${CLAUDE_PLUGIN_ROOT}/scripts/screenshot_tool.py` (Playwright 渲染 + URL 验证 + 智能选择器)
- **验证流程**: HEAD 请求预检 → Playwright 渲染 → 空页面检测 → 截图 → 压缩 → CDN 上传
- Upload to CDN and replace placeholders in-place
- If no `<!-- SCREENSHOT: -->` placeholders found, skip silently

**On failure:** Non-fatal — keep placeholders, warn user, continue
**Status:** Mark `success` if all screenshots captured, `skipped` if no placeholders

> [!note]
> Skipped in draft mode. Mark as `skipped`.

#### 3.4.5 Share Card (standard mode, 询问后执行)

After screenshot step, ask user whether to generate share cards:
```
Question: "生成分享卡片？"
Options:
  - Yes — generate share cards (recommended)
  - No — skip
```

If user declines, mark `share_card: skipped`.

If yes:
- Run `${CLAUDE_PLUGIN_ROOT}/scripts/share_card.py`:
  ```bash
  python3 ${CLAUDE_PLUGIN_ROOT}/scripts/share_card.py \
    -f /ABSOLUTE/PATH/article.md \
    -p wechat-cover,twitter,xiaohongshu-sq \
    --upload
  ```
- 如果文章有完整 frontmatter（title, description, tags, author），直接传 `-f` 即可
- 可选配色：tech-blue / sunset / forest / midnight / ember / deep-blue / slate（默认 tech-blue）
- 平台默认：wechat-cover, twitter, xiaohongshu-sq

**On failure:** Non-fatal — warn user, continue
**Status:** Mark `success` if cards generated, `skipped` if user declined or no frontmatter

#### 3.5 Images (standard and quick modes)

Invoke `article-craft:images` skill logic:
- Pass the article.md absolute file path from Step 3.3 (screenshot placeholders already resolved)
- Run Gemini probe test
- Batch process image placeholders with heartbeat monitoring enabled
- Update article.md in-place with CDN URLs
- **脚本路径**: `${CLAUDE_PLUGIN_ROOT}/scripts/generate_and_upload_images.py`（不要用 `~/.claude/scripts/` 旧路径）

```bash
# 标准调用方式
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_and_upload_images.py \
  --process-file /ABSOLUTE/PATH/article.md
```

**On failure:** Graceful degradation — keep unresolved placeholders, log which
images failed, continue to review. Do NOT stop the pipeline.
**Status:** Mark `success` if any images generated, `failed` if all failed

> [!note]
> Skipped in draft mode. Mark as `skipped`.

#### 3.6 Review (standard mode only)

直接调用 `/article-craft:review`（review skill 内部已包含 Phase 1 self-check + Phase 2 content-reviewer，不需要独立运行 self-check 脚本）：
- Pass the article.md absolute file path
- review skill 自动执行：self-check（15 条规则）→ content-reviewer（7 维评分）
- **不要单独调用 `review_selfcheck.py`**——review skill 内部会调用它

**Review retry loop:**
1. If score ≥ 55/70 → PASS, continue to publish
2. If score < 55/70 and rounds ≤ 3:
   - Auto-modify the article based on reviewer feedback
   - Re-run review
   - Increment round counter
3. If score < 55/70 and rounds > 3:
   - Use AskQuestion: "Article scored {score}/70 after 3 rounds. Proceed anyway or abort?"
   - If proceed → continue to publish
   - If abort → stop pipeline, report status

**On failure (content-reviewer unavailable):** Warn user, proceed with self-check only
**Status:** Mark `success` when score ≥ 55 or user approves

> [!note]
> Skipped in quick and draft modes. Mark as `skipped`.

#### 3.7 Publish (standard mode only)

Invoke `article-craft:publish` skill logic:
- Pass the article.md absolute file path
- Auto-detect knowledge base (02-技术/ directory)
- Match subdirectory via SmartDirectoryMatcher
- Move article to final KB location
- Optionally invoke /wechat-seo-optimizer

**On failure:** Retry once, then report error with the current file path so user
can manually move it
**Status:** Mark `success` when article is in final location

> [!note]
> Skipped in quick and draft modes. Mark as `skipped`.

### Step 4: Completion Summary

After all skills complete (or pipeline stops on fatal error), print a summary table:

```
┌─────────────────────────────────────────────────────────┐
│            Article Craft v1.3.0 — Summary                 │
├──────────────┬──────────┬───────────────────────────────┤
│ Skill        │ Status   │ Notes                         │
├──────────────┼──────────┼───────────────────────────────┤
│ requirements │ success  │ Topic: {topic}                │
│              │          │ 5-layer inference ✅          │
│              │          │ Trusted sources: N found        │
│ verify       │ success  │ T3-T5 focused, N verified   │
│ write        │ success  │ Saved: {absolute_path}        │
│              │          │ Section depth: N/N ✅         │
│ screenshot   │ success  │ 2/2 captured                  │
│ share_card   │ success  │ 3 cards generated             │
│ images       │ success  │ 4/5 uploaded, 1 placeholder   │
│ review       │ success  │ Score: 58/70 (round 1)        │
│ publish      │ success  │ KB: {final_path}              │
├──────────────┼──────────┼───────────────────────────────┤
│ Mode: standard │ Duration: ~2 min                       │
└─────────────────────────────────────────────────────────┘
```

## Error Recovery

If the pipeline stops due to a fatal error (write skill failure):

```
┌─────────────────────────────────────────────────────────┐
│            Article Craft — PIPELINE STOPPED              │
├──────────────┬──────────┬───────────────────────────────┤
│ requirements │ success  │ Topic: {topic}                │
│ verify       │ success  │ All OK                        │
│ write        │ FAILED   │ Error: {error_message}        │
│ screenshot   │ skipped  │ (blocked by write failure)    │
│ share_card   │ skipped  │ (blocked by write failure)    │
│ images       │ skipped  │ (blocked by write failure)    │
│ review       │ skipped  │ (blocked by write failure)    │
│ publish      │ skipped  │ (blocked by write failure)    │
└─────────────────────────────────────────────────────────┘
```

## Standalone Skill Usage

Each skill can be used independently without the orchestrator:

```
/article-craft:requirements   # Just gather requirements
/article-craft:verify         # Just verify links/commands
/article-craft:write          # Just write an article
/article-craft:screenshot     # Just take screenshots / generate share cards
/article-craft:images         # Just generate images for existing article
/article-craft:review         # Just review an existing article
/article-craft:publish        # Just publish to knowledge base
```

When used standalone, each skill handles its own input gathering via AskQuestion
if no arguments are provided.

## Integration

- **content-pipeline agent**: Already updated to use `article-craft` as the writing skill
- **content-reviewer**: Delegated to by the review skill (dependency declared in plugin.json)
- **wechat-seo-optimizer**: Called by publish skill for WeChat optimization
