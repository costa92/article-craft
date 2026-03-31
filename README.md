# article-craft

Modular article generation plugin for Claude Code — 11 composable skills for the full article lifecycle.

## What it does

Start writing and article-craft orchestrates the complete pipeline: requirements gathering, link verification, article writing, screenshot capture, AI image generation, quality review, and knowledge base publishing.

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
cd ~/.claude/plugins/article-craft
bash install.sh
```

This installs Python dependencies, shot-scraper, PicGo CLI, and configures your Gemini API key.

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
| write | Generate articles with 7 writing styles |
| screenshot | Web page capture + social cards |
| images | Gemini API image generation + CDN upload |
| review | Self-check + 7-dimension quality scoring |
| publish | Knowledge base auto-placement |
| lint | Style violation detection + auto-fix |
| series | Multi-part article management |
| youtube | Video transcript to article |

## Workflow Modes

| Mode | Command | Description |
|------|---------|-------------|
| standard | `/article-craft` | Full pipeline |
| quick | `/article-craft --quick` | Skip verification and review |
| draft | `/article-craft --draft` | Content only, no images |
| series | `/article-series` | Multi-article series |

## Standalone Commands

```bash
/article-write        # Generate article
/article-images       # Generate images
/article-review       # Quality gate
/article-lint         # Style check
/article-screenshot   # Web screenshots
/article-youtube     # Video to article
```

## Updating

```bash
cd ~/.claude/plugins/article-craft
git pull
bash install.sh
```

## License

MIT
