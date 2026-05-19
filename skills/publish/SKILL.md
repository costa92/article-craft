---
name: article-craft:publish
version: 1.5.6
description: "Place article in knowledge base and optimize for distribution. Use after review to save the article to its final location."
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - AskUserQuestion
---

# Publish

Place a reviewed article into the knowledge base at the correct category directory, and optionally optimize for WeChat distribution. This is the final step in the article-craft pipeline.

**Invoke**: `/article-craft:publish`

---

## Inputs

- **Article file path**: absolute path to the `.md` file to publish
- **Review score** (optional): passed from `article-craft:review` if run in pipeline
- **`--output DIR`** (optional): explicit output directory. If provided, **bypass KB auto-detection entirely** and save the article under `DIR`. Use this when:
  - You are inside an Obsidian KB but want a one-off scratch article saved elsewhere
  - You want to publish to a custom location that doesn't match the `02-技术/` convention
  - You are publishing programmatically and want deterministic output

If invoked standalone (file path not provided), use AskQuestion:
```
Question: "Which article file should I publish?"
(free-form input: provide the absolute path to the .md file)
```

---

## Execution Steps

### Step 0: Pre-publish placeholder gate (v1.4.20+)

Before any directory matching or file movement, refuse to publish if the
article still contains unresolved `<!-- IMAGE: -->`, `<!-- PROMPT: -->`,
`<!-- SCREENSHOT: -->`, or `<!-- HARVEST: -->` placeholders. This catches
the silent-failure case where image generation ran with `--no-upload` (or
upload itself failed), leaving an article that *looks* finished in stdout
but still has raw placeholders that downstream readers will see as broken
HTML comments.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/pipeline_state.py check-publish-ready \
    --article /ABSOLUTE/PATH/article.md
```

Exit codes:

| Code | Meaning | Action |
|------|---------|--------|
| 0 | Clean — all placeholders resolved | Continue to Step 1 |
| 1 | Unresolved placeholders detected | **BLOCK publish.** Print the structured report (placeholder counts per kind) to the user and exit. |
| 2 | Article path doesn't exist | Fail with a clear "file not found" error |

The script emits a JSON line on stdout (machine-readable) plus a
human-readable summary on stderr listing how many of each placeholder
kind remain. **Do not override this gate** — re-run image generation or
manually replace placeholders, then re-invoke publish.

### Step 1: Preview the Publish Move (`--dry-run`)

Directory matching, collision detection, and Style H sidecar collection are
all owned by `scripts/publish_plan.py`. It is a **single command**: run it
with `--dry-run` to preview the plan (no filesystem changes), review the
result, then run it again **with the same arguments minus `--dry-run`** to
execute. The KB top-level directory name is **not** hardcoded — the script
reads `config.kb_category_root()` (env.json `kb_category_root`, default
`02-技术`), so a fork with a differently-named KB works unchanged.

Two modes, selected by presence of `--output`:

**Mode A — Explicit output** (`--output DIR` passed):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/publish_plan.py --dry-run \
    --article /ABSOLUTE/PATH/article.md \
    --output-dir /ABSOLUTE/PATH/DIR
```

Skips KB detection and directory matching entirely. If `DIR` doesn't exist
the script exits 1 with `error_code: output_dir_not_found`.

**Mode B — Auto-detect KB** (no `--output`):

Check if the current working directory (or a known parent) is an Obsidian
knowledge base by looking for the category-root directory (default `02-技术/`,
or whatever `kb_category_root` is set to). Also check for `.obsidian/` or
sibling numbered directories (`01-工作/`, `03-创作/`).

- **KB detected** — pass its root so the script can match a subdirectory:
  ```bash
  python3 ${CLAUDE_PLUGIN_ROOT}/scripts/publish_plan.py --dry-run \
      --article /ABSOLUTE/PATH/article.md \
      --kb-root /ABSOLUTE/PATH/KB_ROOT
  ```
- **KB not detected** — omit `--kb-root`; the script falls back to the
  article's own directory as the auto target.

`--dry-run` prints a JSON plan payload on stdout and **creates nothing** on
disk:

| Field | Meaning |
|-------|---------|
| `target_dir` | Proposed destination directory |
| `target_file` | Proposed file path. For `collision.status: rename` this name carries a placeholder timestamp — the **exact** timestamp is finalized when the real run executes, so report it as "a timestamped name", not verbatim. |
| `collision.status` | `none` / `identical` (same content) / `rename` (differing content → timestamped) |
| `sidecars` | Style H sidecars (`_evidence.json`, `_harvest_menu.md`) found next to the article |
| `auto_meta.strategy` | How the directory was chosen — see Step 2 |

### Step 2: Review the Proposed Directory

In auto mode, inspect `auto_meta.strategy` from the plan:

- **`matcher`** — `SmartDirectoryMatcher` found a learned/keyword match. Trust it.
- **`directory_fallback`** — no match; the script picked the deepest existing
  subdirectory. Treat as a guess.
- **`fallback`** — nothing matched; the script will use
  `{kb_category_root}/{kb_uncategorized_dir}` (default `02-技术/未分类`).

For `directory_fallback` / `fallback`, do a semantic match yourself using the
table below, then use an explicit `--output-dir` in Step 3 so the article
lands in the right place (substitute your configured `kb_category_root` for
`02-技术`):

| Article Topic | Target Directory | Examples |
|---------------|-----------------|----------|
| AI tools/products | `02-技术/AI-生态/工具/` | Cursor, Windsurf review |
| AI model evaluation | `02-技术/AI-生态/模型评测/` | GPT-5, Claude 4 comparison |
| AI Agent | `02-技术/AI-生态/Agent/` | Agent architecture, MCP protocol |
| Claude Code | `02-技术/AI-生态/Claude-Code/` | Claude Code tips, skills, plugins |
| Ollama | `02-技术/AI-生态/Ollama/` | Local model deployment |
| RAG | `02-技术/AI-生态/RAG/` | Retrieval-augmented generation |
| Go language | `02-技术/基础设施/Go/` | Go tutorials, source analysis |
| Cloudflare | `02-技术/基础设施/Cloudflare/` | CDN, Workers, Pages |
| Docker/K8s etc. | `02-技术/基础设施/<tool>/` | Auto-create subdirectory |
| Obsidian | `02-技术/工作流/Obsidian/` | Obsidian plugins, workflows |
| n8n | `02-技术/工作流/n8n/` | Workflow automation |
| New topic | `02-技术/<new-dir>/` | Auto-create |

When the topic is genuinely ambiguous, ask the user before applying.

### Step 3: Execute the Publish Move

Once the target directory is confirmed, run the script **again without
`--dry-run`** — keep the explicit `--output-dir` you settled on (use it even
for an accepted auto match, so the executed run targets exactly the directory
you reviewed and does not re-resolve):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/publish_plan.py \
    --article /ABSOLUTE/PATH/article.md \
    --output-dir /ABSOLUTE/PATH/CONFIRMED_DIR
```

The executed run creates the directory (`mkdir -p` semantics), copies the
article to `target_file`, and copies any Style H sidecars. It returns the plan
plus a `copied_sidecars` list. Behaviour notes:

- **Collision** — when a differing file already exists, the script writes to a
  timestamped name (e.g. `article_20260322120000.md`); it never silently
  overwrites. When content is identical it re-copies in place (a harmless
  no-op). Surface `collision.status` to the user in the summary.
- **Style H sidecars** — `_evidence.json` / `_harvest_menu.md` next to the
  article are copied automatically so a future
  `/article-craft --upgrade` can resume HARVEST operations. Non-Style-H
  articles have no sidecars and this is a silent no-op.
- **Never copied**: `.article-craft-state.json` — that file is
  per-pipeline-run and the orchestrator deletes it on publish success (v1.4.2
  cleanup rule). The script's `SIDECAR_FILES` list deliberately excludes it.

### Step 4: WeChat Distribution (optional)

If the user wants to publish to WeChat, invoke `/wechat-seo-optimizer` for title and abstract optimization.

```
Question: "Optimize for WeChat distribution?"
Options:
  - Yes -- run SEO optimizer for title and abstract, then convert to WeChat format
  - No -- keep as Markdown only
```

If yes:
1. Invoke `/wechat-seo-optimizer` on the published article.
2. The WeChat converter will save the HTML to `03-创作/已发布/<YYYY-MM>/` (e.g., `03-创作/已发布/2026-03/`).

### Step 5: Completion Summary

Output a summary table with all relevant information:

```markdown
## Publish Complete

| Item | Value |
|------|-------|
| **File path** | `/absolute/path/to/02-技术/.../article.md` |
| **KB directory** | `02-技术/<matched-subdirectory>/` |
| **Sidecars** | `_evidence.json`, `_harvest_menu.md` (copied / none) |
| **Image status** | N/M uploaded (or "no images" / "N placeholders remaining") |
| **Review score** | X/70 (PASS/FAIL) |
| **WeChat** | optimized / skipped |
```

Always include the **absolute file path** so other sessions can locate the article.

---

## Standalone Mode

When invoked directly (not as part of the orchestrator pipeline):

1. AskQuestion for the article file path if not provided.
2. Read the article to extract title and tags for directory matching.
3. Execute Steps 1-5 above.
4. If review score is not available (article was not reviewed), note it in the summary:
   ```
   | **Review score** | not reviewed (run `/article-craft:review` first) |
   ```

---

## Reference

- Knowledge base directory rules: `${CLAUDE_PLUGIN_ROOT}/references/knowledge-base-rules.md`
- SmartDirectoryMatcher source: `${CLAUDE_PLUGIN_ROOT}/scripts/utils.py`
- WeChat HTML output location: `03-创作/已发布/<YYYY-MM>/`
