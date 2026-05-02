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

This installs Python dependencies (Playwright, Pillow, requests), PicGo CLI, and configures your Gemini API key.

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
| images | Gemini API image generation + CDN upload |
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
| series | `/article-series` | Multi-article series |

## Standard Pipeline

```
requirements → verify → [evidence if Style H] → write → screenshot → share_card? → images → verify-claims → review → publish
```

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

**review** — Quality gate with 12 self-check rules + content-reviewer scoring (≥55/70 to pass). Includes image count validation by word count.

**publish** — Auto-detects Obsidian knowledge base, matches subdirectory, optionally runs WeChat SEO optimization.

## Standalone Commands

```bash
/article-craft:write        # Generate article
/article-craft:evidence     # Collect Style H evidence
/article-craft:images        # Generate images
/article-craft:verify-claims # Validate shell commands in article body
/article-craft:review        # Quality gate
/article-craft:lint          # Style check
/article-craft:screenshot    # Web screenshots + share cards
/article-craft:youtube      # Video to article
```

## Updating

```bash
cd ~/.claude/plugins/article-craft
git pull
bash install.sh
```

## License

MIT
