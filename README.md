# article-craft

Modular article generation plugin for Claude Code — 12 composable skills plus orchestrator for the full article lifecycle.

## What it does

Start writing and article-craft orchestrates the complete pipeline: requirements gathering, source verification, evidence collection for Style H, article writing, screenshot capture with Playwright validation, AI image generation, post-write claim verification, quality review with image count checks, and knowledge base publishing.

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
- 9 platforms: WeChat, Xiaohongshu, Twitter/X, LinkedIn, Facebook, Juejin, Zhihu
- 7 color presets: tech-blue, sunset, forest, midnight, ember, deep-blue, slate
- Reads from article frontmatter automatically

**images** — Gemini API batch generation with model fallback chain. Supports both `<!-- IMAGE: -->` (AI-generated) and `<!-- SCREENSHOT: -->` (web capture) placeholders.

**verify-claims** — Post-write shell-command validation. Scans code blocks in the completed article and checks the referenced tools exist on PATH before review.

**review** — Quality gate with 12 self-check rules + 7-dimension scoring (≥55/70 to pass). Self-contained — no external scoring dependency. Includes image count validation by word count.

**publish** — Auto-detects Obsidian knowledge base, matches subdirectory, optionally runs WeChat SEO optimization.

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
