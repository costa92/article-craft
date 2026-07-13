---
name: article-craft:share-card
version: 1.9.11
description: "Generate platform-optimized social share cards (cover/feed/post images) from article frontmatter. 11 platform presets (9 + 2 aliases), 7 color schemes."
allowed-tools:
  - Read
  - Bash
  - AskUserQuestion
---

# Share Card — 社交分享卡片生成

Generate platform-optimized share images directly from an article's
frontmatter (title, description, tags, author). Wraps
`scripts/share_card.py` — same engine the orchestrator's optional
Step 3.4.5 calls; this skill exposes it as a standalone entry point so
authors can regenerate cards on demand without rerunning the whole
pipeline.

**Invoke**: `/article-craft:share-card`

---

## When to use

- After publishing — you want a different platform's card without
  regenerating the article
- Color tweak — same content, swap palette to match a series theme
- Bulk — regenerate cards for multiple existing articles after a
  brand refresh

For first-time generation inside the full pipeline, the orchestrator
already calls share-card automatically (Step 3.4.5). Use this skill
standalone when you're operating on an already-published article.

---

## Inputs

Two ways to feed the generator:

**(A) From article file** — reads `title`, `description`, `tags`,
`author` from YAML frontmatter:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/share_card.py \
    --from-file /ABSOLUTE/PATH/article.md \
    --platforms wechat-cover,xiaohongshu-sq,twitter \
    --color tech-blue \
    --upload
```

**(B) Explicit args** — useful when there's no article file yet:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/share_card.py \
    --title "Claude Code Skills 实战" \
    --description "从零到上线的 12 个 skill 编排器" \
    --tags AI Claude 工具 \
    --author costa \
    --platforms twitter,linkedin \
    --color sunset
```

If invoked standalone without arguments, ask the user via AskQuestion:

```
Question: "Which article file should I generate share cards for?"
(free-form: absolute path to .md file, or "from scratch" to enter
fields manually)
```

---

## Platforms (10 supported)

| Preset | Dimensions | Use |
|--------|-----------|-----|
| `wechat-cover` | 900 × 383 | 公众号封面 |
| `wechat-share` | 500 × 400 | 公众号分享缩略 |
| `xiaohongshu` | 1080 × 1440 | 小红书竖版 |
| `xiaohongshu-sq` | 1080 × 1080 | 小红书正方形 |
| `twitter` | 1200 × 675 | Twitter / X feed (16:9) |
| `twitter-card` | 1200 × 628 | Twitter summary_large_image meta card |
| `linkedin` | 1200 × 627 | LinkedIn post |
| `facebook` | 1200 × 630 | Facebook OG |
| `juejin` | 1200 × 675 | 掘金封面 |
| `zhihu` | 1200 × 800 | 知乎封面 |

Pick any subset via `--platforms a,b,c` (comma-separated). Default is
all 10 if omitted.

---

## Color presets (7 supported)

| Preset | Vibe |
|--------|------|
| `tech-blue` | 默认。深蓝渐变,科技感 |
| `sunset` | 暖橙→深红,创作向 |
| `forest` | 墨绿,沉稳深度长文 |
| `midnight` | 深紫→黑,夜读 |
| `ember` | 火橙,热度感(发布即火型) |
| `deep-blue` | 深蓝,纯色商务 |
| `slate` | 灰蓝中性,通用 |

Override via `--color NAME`. Default `tech-blue` if omitted.

---

## Output

PNG files written under `--output DIR` (defaults to article's directory
when `--from-file` is used, else CWD). Filenames are
`<article-slug>__<platform>.png`.

`--upload` additionally uploads each PNG via the same CDN path
`screenshot_tool.upload_to_cdn` uses (PicGo or S3 depending on env.json
configuration), returning CDN URLs in the output summary.

---

## Auto-skip conditions

The script auto-skips silently when:

- `--from-file` is used and the article has no `author` field
  (frontmatter requirement — set `user_name` in `~/.claude/env.json`
  to populate this automatically at write time via
  `config.author_name()`)
- No platform list resolves to any valid preset
- Output directory is unwritable

Each skip prints a one-line reason; pipeline continues.

---

## Relationship to the orchestrator pipeline

The orchestrator's optional Step 3.4.5 invokes the same script
(`scripts/share_card.py`) on a fresh article. This skill is the
**standalone** entry point — exact same engine, just invokable
post-publish or against any article on disk.

Skip this skill in the orchestrator when:

- You're running `--draft` or `--quick` mode (orchestrator already
  skips share cards in those modes)
- The article has no `author` frontmatter field

---

## Reference

- Implementation: `${CLAUDE_PLUGIN_ROOT}/scripts/share_card.py` (553 LOC)
- Upload backend: shared with `screenshot_tool.upload_to_cdn`
- Tests: `tests/test_share_card_upload.py`
