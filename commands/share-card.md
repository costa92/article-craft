---
description: Generate platform-optimized social share cards from article frontmatter
argument-hint: "[path/to/article.md] [--platforms ...] [--color ...] [--upload]"
---

Read and follow the skill at `${CLAUDE_PLUGIN_ROOT}/skills/share-card/SKILL.md`.

Engine: `${CLAUDE_PLUGIN_ROOT}/scripts/share_card.py` — supports
`--from-file ARTICLE.md` (reads YAML frontmatter for title/description/
tags/author) or explicit `--title` / `--description` / `--tags` / `--author`
flags. See the SKILL.md for the 11 platform presets (9 + 2 aliases) and 7 color schemes.

ARGUMENTS: $ARGUMENTS
