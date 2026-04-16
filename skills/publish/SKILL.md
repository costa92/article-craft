---
name: article-craft:publish
version: 1.4.3
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

### Step 1: Determine Output Mode

Two modes, selected by presence of `--output`:

**Mode A — Explicit output** (`--output DIR` passed):
1. Validate `DIR` exists and is writable. If not, fail with a clear error.
2. Skip KB detection entirely.
3. Skip Smart Directory Matching (Step 2).
4. Move the article to `DIR/<filename>.md` and jump to Step 4.

**Mode B — Auto-detect KB** (no `--output`):
Check if the current working directory (or a known parent) is an Obsidian knowledge base by looking for the `02-技术/` directory.

```bash
# Check from current directory upward
[ -d "02-技术" ] || [ -d "../02-技术" ] || [ -d "../../02-技术" ]
```

Also check for `.obsidian/` directory or numbered directories (`01-工作/`, `03-创作/`).

- **KB detected**: proceed to Step 2 (directory matching).
- **KB not detected**: save to the current working directory. Skip to Step 4.

### Step 2: Smart Directory Matching

When a knowledge base is detected, determine the best subdirectory under `02-技术/` for the article.

**Option A -- Use SmartDirectoryMatcher** (if available):

The `SmartDirectoryMatcher` class is located at `${CLAUDE_PLUGIN_ROOT}/scripts/utils.py`. It performs keyword matching, pattern matching, and history-based matching to find the best directory.

```python
import os
import sys
sys.path.insert(0, os.path.join(os.environ["CLAUDE_PLUGIN_ROOT"], "scripts"))
from utils import SmartDirectoryMatcher

matcher = SmartDirectoryMatcher(kb_root=PROJECT_ROOT)
matched_dir = matcher.match_directory(article_title, article_content)
```

**Option B -- Manual keyword matching** (if SmartDirectoryMatcher is not available):

Use the directory mapping table below to determine the target directory:

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

Analyze the article title and frontmatter tags to determine the best match. When ambiguous, ask the user.

### Step 3: Create Directory and Move Article

```bash
# Set the target directory
ARTICLE_DIR="${PROJECT_ROOT}/02-技术/<matched-subdirectory>"

# Create if not exists
mkdir -p "${ARTICLE_DIR}"

# Move the article to its final location
# Use cp if the original should be preserved, mv if it should be relocated
cp /path/to/article.md "${ARTICLE_DIR}/"
```

Rules:
- **Never hardcode paths.** Derive `PROJECT_ROOT` from the user's working directory or explicit input.
- **Use `mkdir -p`** to create any missing intermediate directories.
- **Collision handling:** Before copying, check if the target file already exists:
  - If exists and content is identical → skip (already published)
  - If exists and content differs → rename new file with timestamp suffix (e.g., `article_20260322.md`) and warn user
  - Never silently overwrite an existing file

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
