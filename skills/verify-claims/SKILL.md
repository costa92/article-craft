---
name: article-craft:verify-claims
version: 1.4.12
description: "Post-write claim verification — scan article body for shell commands and check they exist on PATH. Runs after images, before review. Companion to the pre-write verify stage (source vetting)."
allowed-tools:
  - Read
  - Edit
  - Bash
  - AskUserQuestion
---

# verify-claims — Post-Write Claim Verification

Scan the article body for shell commands and verify every tool named in a
bash / sh / shell / zsh code block is actually installed on PATH. This is
the post-write counterpart to the pre-write `verify` stage.

## Role split (since v1.4.5)

article-craft has two verification stages with non-overlapping scopes:

| Stage | When | What it vets |
|-------|------|--------------|
| `verify` (a.k.a. source-vet) | pre-write | The **sources** the writer will cite — URL reachability, T0–T5 trust tiering, feature / version claims made in source docs |
| `verify-claims` | post-write, pre-review | The **article body** the writer produced — shell commands, tool names, wiring that survives into the final output |

Before v1.4.5 this role was a grep-level approximation inside `write` Step 7
Check C. That check is now removed — write emits the article, and this skill
runs as a dedicated stage.

## Scope (MVP)

- Shell code blocks only (language fenced as `bash`, `sh`, `shell`, or `zsh`).
- First-token extraction per logical command (respects `|`, `&&`, `;`, `$()`).
- Strips `sudo` / `env` prefixes.
- Skips shell built-ins (`cd`, `echo`, `test`, `exec`, ...) and ubiquitous
  utilities (`ls`, `grep`, `awk`, `curl`, `python`, ...).
- Checks presence via `shutil.which`, no execution of the commands themselves.

Explicitly **out of scope for MVP** (each is a future enhancement, not a bug):

- Flag-level validation (`uv pip install --reinstall` → does `--reinstall` exist?).
- API-endpoint reachability.
- Version-string claims in prose.
- Python / JS imports inside code blocks.

## Invocation

```
/article-craft:verify-claims              # prompt for the article path
/article-craft:verify-claims /abs/path    # direct
```

Orchestrated invocations pass the path via the state write protocol in the
orchestrator's Step 3.6.5.

## Process

### Step 1: Run the scan

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify_claims.py scan \
  --article /ABSOLUTE/PATH/article.md --json
```

Output is JSON:

```json
{
  "article": "/abs/path/article.md",
  "total_tools": 5,
  "checked": [
    {"tool": "uv", "present": true, "fragment": "uv pip install..."},
    {"tool": "gsd", "present": false, "fragment": "gsd --version"}
  ],
  "skipped_ubiquitous": ["cat", "grep"],
  "skipped_placeholder": [],
  "missing": ["gsd"]
}
```

Exit code: `0` if no missing tools, `1` if at least one tool not on PATH, `2`
for invalid usage.

### Step 2: Report + act

If `missing` is empty → mark stage success, done.

If `missing` is non-empty, surface via `AskUserQuestion`:

```
Question: "verify-claims found N tool(s) not on PATH: {comma list}.
           For each, this could be: (a) a real binary not installed locally —
           fine, article can still ship, (b) a typo / wrong name that needs
           fixing, or (c) an article talking about a tool that doesn't exist
           at all (hallucination). How to proceed?"
Options:
  - Proceed (accept) — tools may not be on this machine but the article is still valid
  - Mark [需要验证] inline — Edit the article to tag each unknown command, ship with visible uncertainty
  - Abort — stop pipeline, hand article back to user for manual fix
```

Track user choice in the state file `result` payload so `--upgrade` can
reason about it.

### Step 3: Hand off

Return one of:

- `PASS` — all tools found, or user accepted with `Proceed`
- `PASS_WITH_MARKS` — user chose `Mark [需要验证]`, article was edited
- `ABORT` — user chose to stop

The orchestrator maps these to its standard stage status (`success` / `failed`).

## Invariants

- Never touches handoff-contract comments or CDN URLs.
- Never executes commands from the article (just `shutil.which`).
- Always safe to run standalone, at any time, against any article state.

## Standalone mode

1. If no article path provided, `AskQuestion` for it.
2. Run the scan.
3. Emit the human-readable report (drop `--json`).
4. If any missing, prompt for the 3 options above.
