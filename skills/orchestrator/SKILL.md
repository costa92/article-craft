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

Five modes, selected at invocation:

| Mode | Skills Executed | Use Case |
|------|----------------|----------|
| **standard** (default) | requirements → verify → write → screenshot → images → review → publish | Full article with quality gate |
| **quick** (`--quick`) | requirements → write → screenshot → images | Fast output, skip verification and review |
| **draft** (`--draft`) | requirements → write | Content only, no images or review |
| **series** (`--series FILE`) | Read series.md → requirements (pre-filled) → standard pipeline | Write the next article in a series |
| **upgrade** (`--upgrade PATH`) | Detect existing state → run only missing stages | Upgrade a draft/quick article to full standard output |

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
  5. share_card: apply 3.4.5 auto-inference (frontmatter completeness + --share-cards flag)

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

### Step 0: Preflight Dependency Check

Before running any skill, verify that the tools downstream stages depend on are actually available. Fail fast with a specific error naming the missing piece — do **not** let the user sit through `requirements → verify → write → screenshot` only to have `images` explode because `GEMINI_API_KEY` was never configured.

Run these checks in parallel via Bash:

```bash
# 1. Gemini API key — required by images + nanobanana.py
python3 -c "import json, os; e=json.load(open(os.path.expanduser('~/.claude/env.json'))); assert e.get('gemini_api_key'), 'GEMINI_API_KEY missing'" 2>&1

# 2. Playwright chromium — required by screenshot_tool.py
python3 -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); p.chromium.executable_path; p.stop()" 2>&1

# 3. PicGo (optional — only fail if the user has configured PicGo as upload mode)
command -v picgo 2>&1 || echo "picgo not on PATH (only needed if upload_mode=picgo in env.json)"
```

**Skip rules**:
- **draft mode** (`--draft`): skip all three — draft produces a markdown file only, no images or screenshots are needed
- **quick mode** (`--quick`): skip PicGo check if `upload_mode=s3`
- **upgrade mode** (`--upgrade`): run only the checks relevant to the stages that will actually run after state detection

**On failure**: report the specific missing dependency and point to `ENV.md` / `install.sh` for remediation. Do not continue the pipeline.

Example failure output:
```
❌ Preflight failed: GEMINI_API_KEY missing from ~/.claude/env.json
   → Fix: add `"gemini_api_key": "..."` to ~/.claude/env.json
   → See: ENV.md
```

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

#### 3.4.5 Share Card (standard mode, auto-inferred)

**Do NOT ask the user mid-pipeline.** Share card generation is inferred from frontmatter completeness and an optional CLI flag, so autonomous runs never block on interactive prompts.

**Decision logic**:

```
share_cards_flag = parse "--share-cards=yes|no|auto" (default: auto)

if share_cards_flag == "no":
    mark share_card: skipped
    done

if share_cards_flag == "yes":
    run share_card.py (force)

if share_cards_flag == "auto":
    required_frontmatter = {title, description, tags, author}
    if article_frontmatter has all of required_frontmatter:
        run share_card.py
    else:
        mark share_card: skipped (reason: "incomplete frontmatter for auto mode")
```

Example `auto` skip reasons printed in the summary:
- `share_card: skipped (auto — missing: description, author)`
- `share_card: skipped (auto — missing: tags)`
- `share_card: skipped (--share-cards=no)`

**Execution** (when the decision is to run):
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/share_card.py \
  -f /ABSOLUTE/PATH/article.md \
  -p wechat-cover,twitter,xiaohongshu-sq \
  --upload
```

- `-f` 会自动从 frontmatter 读 title/description/tags/author
- 可选配色：tech-blue / sunset / forest / midnight / ember / deep-blue / slate（默认 tech-blue）
- 平台默认：wechat-cover, twitter, xiaohongshu-sq

**On failure:** Non-fatal — warn user, continue
**Status:** Mark `success` if cards generated, `skipped` with a reason string as shown above

> **Why no interactive prompt**: Mid-pipeline `AskQuestion` calls break autonomous / scheduled runs, CI integration, and `--series` batch mode. Inference from frontmatter is deterministic and pre-answerable. If you want explicit control, use `--share-cards=yes|no`.

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

直接调用 `/article-craft:review`（review skill 是 self-contained：内部已包含 Phase 1 self-check + Phase 2 embedded 7 维评分 + 最多 3 轮自动修订循环）：
- Pass the article.md absolute file path
- review skill 自动执行：self-check（11 条规则）→ embedded scoring（7 维）→ 若得分 < 55/70 自动最多重试 3 轮，仍不过则用 AskQuestion 询问用户
- **不要单独调用 `review_selfcheck.py`**——review skill 内部会调用它
- orchestrator 不要再嵌套一层重试循环，信任 review skill 的返回结果即可

**Outcome:**
- Review skill returns `PASS` (score ≥ 55 或用户选择 proceed) → continue to publish
- Review skill returns `ABORT` (用户选择 abort) → stop pipeline, report status

**Status:** Mark `success` on PASS, `failed` on ABORT

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

**Quick mode — unverified citation warning**: if the run used `--quick` (verify was skipped) **and** the article cites any T3-T5 community sources, append this warning block to the summary:

```
⚠️  UNVERIFIED CITATIONS
   This run used --quick mode, so verify stage was skipped.
   The article cites {N} T3-T5 community sources (tutorials, blog posts,
   Medium articles) that were NOT link-checked or fact-vetted.

   Trusted tiers cited:
     T3 (Technical blog):    {n3} sources
     T4 (Medium/Dev.to):     {n4} sources
     T5 (Unverified):        {n5} sources

   → To vet them, run: /article-craft:verify {article_path}
```

Omit the warning if write only cited T0-T2 (official docs, tool source, standards).

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
- **review skill**: Self-contained — embeds the 11 self-check rules plus 7-dim scoring inline. No external `content-reviewer` dependency in `plugin.json`.
- **wechat-seo-optimizer**: Called by publish skill for WeChat optimization
