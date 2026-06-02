# article-craft

[![Plugin Layout Smoke](https://github.com/costa92/article-craft/actions/workflows/smoke.yml/badge.svg)](https://github.com/costa92/article-craft/actions/workflows/smoke.yml)
[![Screenshot E2E](https://github.com/costa92/article-craft/actions/workflows/screenshot-e2e.yml/badge.svg)](https://github.com/costa92/article-craft/actions/workflows/screenshot-e2e.yml)

Modular article generation plugin for Claude Code — 13 composable skills plus orchestrator for the full article lifecycle. **WeChat distribution-aware** (v1.7.x): built from 4 real published articles where 8 self-check rules failed 100% of the time, hardened with A/B-tier official-source evidence chain. **v1.8.x** adds an orthogonal `body_form` axis — `wechat-native` (mobile-shaped 公众号 body) is now the default — and attribution-as-voice (Rule 5/22 credit honest source attribution, not just first-person anecdotes).

## What it does

Start writing and article-craft orchestrates the complete pipeline: requirements gathering, source verification, evidence collection for Style H, article writing, screenshot capture with Playwright validation, AI image generation, post-write claim verification, quality review with image count checks, and knowledge base publishing.

**For WeChat 公众号 authors** (`wechat-native` is the default body form since v1.8.0): article-craft enforces 6 distribution-critical rules covering AIGC compliance (GB 45438-2025), recommendation-pool qualification (《微信公众号推荐运营规范》), Style G + opinionated tone substance, and tag NLP matching. See [WeChat 适配 (v1.7.x)](#wechat-适配-v17x) section below for empirical validation data.

## Installation

### Claude Code (via Plugin Marketplace)

Register the marketplace first:

```bash
/plugin marketplace add costa92/article-craft
```

Then install the plugin:

```bash
/plugin install article-craft@article-craft
```

After installing, run the dependency installer:

```bash
cd /.claude/plugins/marketplaces/article-craft
bash install.sh
```

This installs Python dependencies (Playwright, Pillow, requests), PicGo CLI, and prepares your Minimax-first image setup.

### Verify Installation

```bash
/article-craft 写一篇关于 Python 装饰器的技术文章
```

## Skills

| Skill | Description |
|-------|-------------|
| orchestrator | Pipeline coordinator |
| requirements | Smart inference + minimal questions |
| verify | Batch link and command verification |
| evidence | Style H source evidence collection |
| write | Generate articles with 7 writing styles |
| screenshot | Web screenshots (Playwright + URL validation) + share cards |
| images | Minimax-first image generation + CDN upload |
| verify-claims | Post-write shell command validation |
| review | Self-check + 7-dimension quality scoring |
| publish | Knowledge base auto-placement |
| lint | Style violation detection + auto-fix |
| series | Multi-part article management |
| youtube | Video transcript to article |
| share-card | Platform-optimized social share images (11 presets / 9 platforms, 7 colors) |

## Workflow Modes

| Mode | Command | Description |
|------|---------|-------------|
| standard | `/article-craft` | Full pipeline |
| quick | `/article-craft --quick` | Skip both verification stages, review, and publish |
| draft | `/article-craft --draft` | Content only, with Style H evidence collection if needed |
| series | `/article-craft --series FILE` | Multi-article series (or standalone `/article-craft:series`) |

## Standard Pipeline

```
requirements → verify → [evidence if Style H] → write → screenshot → share_card? → images → verify-claims → review → publish
```

## WeChat 适配 (v1.7.x)

5 incremental releases over 5 days, driven by **4 real WeChat articles** (CostaLong account, 2026-05-09 to 2026-05-21) that all underperformed in reach. Pulled them from `mp.weixin.qq.com`, ran them against `review_selfcheck.py`, found **8 rules with 100% failure rate**:

| Rule | Failure root cause |
|---|---|
| Rule 18 | No AIGC label → 平台主动加标识 → 流量限制 (GB 45438-2025) |
| Rule 3 | No CTA → 不进朋友推荐池 (2025-03 微信扩测) |
| Rule 4 | tags < 3 中文 → 看一看 NLP 匹配受限 |
| Rule 5 | Anti-AI structure fails → 连续 3 段缺锚点 |
| Rule 6 | Shallow chapters → 浅层章节缺代码块 |
| Rule 17 | opinionated 退化为中立技术教程 (强观点 0) |
| Rule 22 | Personal voice density → 主观判断 0 |
| Rule 24 | LLM fabricated numbers → 自信编造伪事实 |

### What v1.7.x ships

| Release | Adds | Anchors to |
|---|---|---|
| **v1.7.0** | Rule 18 (AIGC) + Rule 19 (title hook) + Rule 20 (paragraph dedup) + Rule 22 (personal voice) + CTA enforcement + double cover (`wechat-double`) | GB 45438-2025 (A 级) + 网信办《标识办法》(A 级) |
| **v1.7.1** | Rule 23 (anti-recommendation blacklist) + publish step 3.5 (6-item checklist) | 微信珊瑚安全 2025-08-31 公告 (B 级) + 《微信公众号推荐运营规范》(A 级) |
| **v1.7.2** | Rule 24 (fabricated-number detection, warning-only) + Rule 23 code-block exemption bugfix | Internal dogfooding (LAT.md 评论文章触发) |
| **v1.7.3** | `style-guide.md` Style G + opinionated 加强模板: 4 fill-in-the-blank tables (个人经历 / 主观判断 / 强观点 / 具体锚点) | Empirical 4-article 100% Rule 17/22 failure data |
| **v1.7.4** | Rule 4 enforcement (write step 3a hard constraint + publish step 3.5.0 auto-check) | Empirical 4-article 100% Rule 4 failure data |

### What v1.8.x adds

The v1.8.x line keeps the 23-rule count but reshapes *form* and fixes a fabrication-reward incentive surfaced by further dogfooding:

| Release | Adds | Why |
|---|---|---|
| **v1.8.0** | Orthogonal `body_form` axis: `wechat-native` (mobile-shaped 公众号 body — short paragraphs, no callouts, ≤ `##`/`###`, single throughline) is the **default**; `long-form` (blog/KB body with callouts + deep sections) is opt-in via `--long-form` / `body_form: long-form`. Independent of *style* (A–H) and *depth* (字数). Rule 6 threshold is body-form-aware (`wechat-native` −1); review adds a **soft** form-consistency signal (no new write gate). | A `wechat-native + deep` article should be long but mobile-shaped — depth and form are separate decisions. |
| **v1.8.1–v1.8.3** | Dogfood doc follow-ups (title-skip, word-count calibration, Rule 14 hint); screenshot CLI `scan` misread fix; warn (not silently swallow) on shared-uploader degradation. | Minor reliability + accuracy fixes. |
| **v1.8.4** | **Attribution-as-voice** (Rule 5/22): source attribution (据/根据/官方/原文/"视频里说") now counts as a valid concrete anchor; Rule 22 passes on `个人经历 ≥2 OR 来源归属 ≥2`; Rule 5 skips conclusion/intro sections. Plus an **honest default AIGC label** — no longer auto-claims "人工核实改写" that never happened. | Dogfooding caught the rules rewarding *fabricated* anecdotes while penalizing honest, fully-attributed source summaries. Addresses the open Rule 5/6 design debt. |

### Empirical validation (v1.7.4 dogfood)

| Article | Pass rate (v1.7.2 review) |
|---|---|
| A1 LLM Wiki | 14/23 (60.9%) |
| A2 金鱼脑 | 15/23 (65.2%) |
| A3 NotebookLM | 14/23 (60.9%) |
| A4 Hindsight | 15/23 (65.2%) |
| **Average** | **14.5/23 (63.0%)** |
| **v1.7.4 dogfood article** | **23/23 (100%)** |

**8/8 fail-on-all-4 rules flipped to PASS** in the dogfood article — the augmentation > gating design philosophy works on n=1. Field validation window: 4-6 weeks before deciding if v1.7.5 needs to add Rules 5/17/22 to `WRITE_GATE_RULES` as plan B.

### Design philosophy: augmentation > gating

Considered adding Rules 5/17/22 to `WRITE_GATE_RULES` but rejected for 3 reasons:
1. Violates write skill's existing separation of concerns
2. Rules 5/17/22 have 8-12% FP rate empirically — gating causes writing loops
3. LLM forced through gates "凑规则" rather than internalizing — Rule 17 might trigger but the writing remains hollow

Instead, the prompt augmentation in `skills/write/style-guide.md` `### Style G + opinionated 加强模板` feeds 句式表 directly into the LLM's writing context. This is the same principle as TypeScript types — the constraint shapes the work upstream, rather than gatekeeping at the end.

### Evidence chain convention

Every v1.7.x rule traces to an A-tier or B-tier official source. The full evidence chain lives in two research files:

- `.research/official-sources-verification.md` — round 1, 20 propositions classified A/B/C
- `.research/wechat-distribution-mechanism-2026.md` — round 2, 9 incremental propositions

When adding new rules: each rule → 1 commit → commit message links ≥1 first-party URL. See `references/self-check-rules.md` Rule 18-24 sections for individual rule definitions and the source chain for each.

## Architecture Overview

article-craft uses a two-layer architecture:

- **Skills / workflow layer** — defines pipeline stages, routing, decision rules, and user interaction
- **Scripts / execution layer** — performs the actual work: state tracking, evidence collection, screenshots, image generation, validation, and publishing support

### Module Relationship

```text
User commands
  ├─ /article-craft
  │    └─ commands/article-craft.md
  │         └─ skills/orchestrator/SKILL.md
  ├─ /article-craft:write
  ├─ /article-craft:verify
  ├─ /article-craft:evidence
  ├─ /article-craft:screenshot
  ├─ /article-craft:images
  ├─ /article-craft:verify-claims
  ├─ /article-craft:review
  ├─ /article-craft:publish
  ├─ /article-craft:lint
  ├─ /article-craft:series
  └─ /article-craft:youtube
```

```text
orchestrator
  ├─ requirements     → infer topic / style / audience / depth
  ├─ verify           → pre-writing link and command verification
  ├─ evidence         → scripts/evidence.py
  │                     └─ calls scripts/screenshot_tool.py harvest
  ├─ write            → generates article.md with placeholders
  ├─ screenshot       → scripts/screenshot_tool.py
  ├─ images           → scripts/generate_and_upload_images.py
  │                     ├─ uses scripts/nanobanana.py
  │                     └─ reads scripts/config.py
  ├─ verify-claims    → scripts/verify_claims.py
  ├─ review / lint    → applies references/self-check-rules.md
  └─ publish          → uses scripts/utils.py SmartDirectoryMatcher
```

### Responsibility by Directory

| Path | Responsibility |
|------|----------------|
| `commands/` | Slash-command entrypoints that route to skills |
| `skills/` | Workflow definitions for each stage in the article pipeline |
| `scripts/` | Executable support code for screenshots, evidence, images, state, and validation |
| `lib/` | Shared Node.js helpers for config and skill discovery |
| `references/` | Canonical writing rules, style references, and knowledge-base placement rules |
| `tests/` | Regression coverage for config loading, pipeline state, and claim verification |

### Key Runtime Components

- `scripts/pipeline_state.py` — stage state file management and `--upgrade` resume logic
- `scripts/evidence.py` — parses `materials.md` and builds `_evidence.json`
- `scripts/screenshot_tool.py` — URL preflight, Playwright rendering, screenshot capture, HARVEST expansion
- `scripts/generate_and_upload_images.py` — batch image generation, upload, replacement, and recovery
- `scripts/verify_claims.py` — scans shell code blocks and checks whether referenced tools exist on `PATH`
- `scripts/config.py` — shared config, timeouts, model fallback chain, and verification cache support
- `scripts/utils.py` — placeholder history and smart knowledge-base directory matching

### Summary

In practice, `skills/` decides **what should happen next**, while `scripts/` is responsible for **actually doing the work**.

### Pipeline Details

**requirements** — Smart inference of writing style, depth, audience from topic keywords. Only asks when genuinely ambiguous.

**verify** — Batch checks tool commands, links (HTTP HEAD), and features. Non-blocking. URL results cached to `~/.cache/article-craft/verify-cache.json` (TTL 1h) for reuse by screenshot.

**evidence** — Style H only. Collects source materials from `materials.md`, builds `_evidence.json`, and blocks the pipeline if the evidence package does not meet the minimum image threshold.

**write** — Generates article with YAML frontmatter, Obsidian callouts, and placeholders:

```markdown
<!-- IMAGE: name - description (16:9) -->
<!-- PROMPT: Gemini prompt for this image -->

<!-- SCREENSHOT: https://example.com #selector WAIT:3 -->
```

**screenshot** — Playwright-powered with smart validation:
- HEAD request pre-check (404/403/5xx detection)
- Real browser rendering (networkidle + JS wait)
- Auto-selectors for GitHub/Twitter/Stack Overflow
- Screenshot → Pillow compress → CDN upload

**share_card** — Optional. Generates platform-specific share images:
- 9 presets across 7 platforms: WeChat (cover+share), Xiaohongshu (tall+square), Twitter/X, LinkedIn, Facebook, Juejin, Zhihu (+ 2 aliases: wechat-share-square, twitter-card)
- 7 color presets: tech-blue, sunset, forest, midnight, ember, deep-blue, slate
- Reads from article frontmatter automatically

**images** — Gemini API batch generation with model fallback chain. Supports both `<!-- IMAGE: -->` (AI-generated) and `<!-- SCREENSHOT: -->` (web capture) placeholders.

**verify-claims** — Post-write shell-command validation. Scans code blocks in the completed article and checks the referenced tools exist on PATH before review.

**review** — Quality gate with **23 self-check rules + 8-dimension scoring** (≥63/80 to pass, v1.7+). Self-contained — no external scoring dependency. Includes image-count validation by word count. Rules 18-24 (v1.7.x) cover WeChat-specific compliance, recommendation-pool qualification, anti-LLM systematic failure modes (fabricated numbers, AIGC reverse declarations).

**publish** — Auto-detects Obsidian knowledge base, matches subdirectory. Step 3.5 prints a 7-item human checklist enforcing WeChat backend operations (创作来源 4 选 1 / 原创声明 / 允许推荐 / 不分组群发 / tag 自动检测 / AIGC compliance / no reverse declarations). Optionally runs WeChat SEO optimization.

## Standalone Commands

Every skill is independently invokable. All commands resolve as
`/article-craft:<name>` (single prefix — every command file lives at
`commands/<name>.md` top-level since v1.6.3).

```bash
/article-craft:requirements   # Smart inference + minimal questions
/article-craft:verify         # Pre-write source vetting (T0–T5 trust tiers)
/article-craft:evidence       # Collect Style H evidence
/article-craft:write          # Generate article
/article-craft:screenshot     # Web screenshots + share cards
/article-craft:images         # Generate images (Minimax → Gemini fallback)
/article-craft:verify-claims  # Validate shell commands in article body
/article-craft:review         # Quality gate (11 rules + 7-dim scoring)
/article-craft:publish        # KB auto-placement + sidecar copy
/article-craft:lint           # Style check + auto-fix
/article-craft:series         # Multi-part series management
/article-craft:youtube        # YouTube video → article
/article-craft:share-card     # Social share images (11 presets / 9 platforms, 7 colors)
/article-craft:doctor         # Runtime healthcheck (v1.6.0+)
/article-craft:upgrade /path  # Upgrade a draft/quick article to standard
```

## Updating

```bash
cd ~/.claude/plugins/article-craft
git pull
bash install.sh
```

## License

MIT
