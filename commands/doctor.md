---
description: Run the article-craft runtime healthcheck (dependency preflight)
argument-hint: "[--json] [--network]"
---

Run the article-craft dependency healthcheck and report the result:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py check $ARGUMENTS
```

`doctor.py check` is the same preflight the orchestrator runs as its
"Step 0". It verifies:

- `plugin_root` — `CLAUDE_PLUGIN_ROOT` env var resolves to a real directory
- `env_json` — `~/.claude/env.json` parses as valid JSON (a typo there
  would otherwise silently degrade every downstream check)
- Python packages, Gemini / Minimax API keys, Playwright + Chromium,
  PicGo, yt-dlp, NotebookLM CLI, `gh`, Docker

Exit codes:

| Code | Meaning |
|------|---------|
| 0 | All checks pass |
| 1 | One or more warnings (non-blocking) |
| 2 | One or more blocking failures |

Flags:

- `--json` — machine-readable payload instead of the human summary
- `--network` — also probe Minimax + Gemini host reachability (HEAD with
  3 s timeout each; only probes hosts whose API key is configured).
  Skipped by default to keep the preflight fast (~1 s).

Present the summary to the user. If any check is `WARN` or `BLOCK`, surface
the remediation hint from the script output so the user knows how to fix it.

This command has no matching skill — it is a thin wrapper around
`scripts/doctor.py`. Like every other article-craft command (since v1.6.3),
it lives at the top level of `commands/` so it resolves as the single-prefix
`/article-craft:doctor`.

ARGUMENTS: $ARGUMENTS
