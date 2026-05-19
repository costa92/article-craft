---
description: Run the article-craft runtime healthcheck (dependency preflight)
argument-hint: [--json]
---

Run the article-craft dependency healthcheck and report the result:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py check $ARGUMENTS
```

`doctor.py check` is the same preflight the orchestrator runs as its
"Step 0" — it verifies the runtime environment (Python packages, Gemini /
Minimax API keys, Playwright + Chromium, PicGo, yt-dlp, NotebookLM CLI,
`gh`, Docker) and prints a per-check `PASS` / `WARN` / `BLOCK` summary.

Exit codes:

| Code | Meaning |
|------|---------|
| 0 | All checks pass |
| 1 | One or more warnings (non-blocking) |
| 2 | One or more blocking failures |

Pass `--json` for a machine-readable payload instead of the human summary.

Present the summary to the user. If any check is `WARN` or `BLOCK`, surface
the remediation hint from the script output so the user knows how to fix it.

This command has no matching skill — it is a thin wrapper around
`scripts/doctor.py`. It deliberately lives at `commands/doctor.md` (the
top level of `commands/`, **not** under `commands/article-craft/`) so it
resolves as `/article-craft:doctor`. A file under `commands/article-craft/`
would register as the nested `/article-craft:article-craft:doctor` instead.

ARGUMENTS: $ARGUMENTS
