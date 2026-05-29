---
description: Full article generation pipeline with enhanced inference and source trust detection
argument-hint: "[topic or --quick or --draft or --upgrade or --series or --tone or --body-form]"
---

Read and follow the skill at `${CLAUDE_PLUGIN_ROOT}/skills/orchestrator/SKILL.md`.

Pass the user's arguments (topic, --quick, --draft, --upgrade, --series, --tone, --body-form) to the orchestrator skill.

## Flags

- `--tone={neutral,casual,opinionated}` — Override tone tier (otherwise
  resolved from frontmatter or writing-style default). Invalid values
  abort with an error.
- `--body-form={wechat-native,long-form}` (or `--long-form`) — 正文形态。默认 `wechat-native`（公众号原生短文体）；`long-form` 产出博客/KB 长文体。
- `--series SERIES_FILE` — Write the next planned article by reading the series file as the source of truth.

ARGUMENTS: $ARGUMENTS
