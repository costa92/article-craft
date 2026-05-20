---
description: Place article in knowledge base and optimize for distribution
argument-hint: [path/to/article.md]
---

Read and follow the skill at `${CLAUDE_PLUGIN_ROOT}/skills/publish/SKILL.md`.

Directory matching, collision detection, and Style H sidecar handling are
implemented in `scripts/publish_plan.py` — a single command, previewed with
`--dry-run` then re-run without it to execute:
- `--article FILE [--output-dir DIR | --kb-root DIR] --dry-run` — preview only
- `--article FILE [--output-dir DIR | --kb-root DIR]` — execute the move

ARGUMENTS: $ARGUMENTS
