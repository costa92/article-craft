# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`article-craft` is a **Claude Code plugin** (not a runtime application) that ships 11 composable skills for the full article generation lifecycle. The repo is the source that gets installed to `~/.claude/plugins/article-craft/` via `install.sh` or the Claude Code plugin marketplace. Skills are executed by Claude Code itself — this repo contains the prompts, references, and supporting Python scripts, not a service to run.

## Architecture

### The orchestrator pattern

Everything funnels through `skills/orchestrator/SKILL.md`, which composes the 11 skills into a pipeline:

```
requirements → verify → write → screenshot → (share_card?) → images → review → publish
```

Each skill is also callable standalone via `/article-craft:<skill-name>`. The `commands/article-craft.md` slash command simply instructs Claude to read and follow the orchestrator SKILL.md, passing `$ARGUMENTS` through.

Four workflow modes change which steps run:
- **standard** (default): all 7 steps
- **quick** (`--quick`): skips verify + review + publish
- **draft** (`--draft`): requirements + write only
- **series** (`--series FILE`): reads a series.md index, pre-fills requirements
- **upgrade** (`--upgrade PATH`): inspects an existing article's state (placeholders, CDN URLs, KB location) and runs only the missing stages

### Two kinds of code

This is a **prompt-first** project. Most "logic" lives in `.md` files that Claude reads and executes:

1. **SKILL.md / command .md files** — the behavior definitions. Editing these changes how the pipeline behaves. They contain YAML frontmatter (`name`, `version`, `description`, `allowed-tools`) followed by markdown prose and procedural instructions.
2. **Python scripts under `scripts/`** — the deterministic helpers SKILL.md files shell out to. These handle things prompts can't reliably do: Playwright rendering, Gemini API calls, image compression, CDN upload, cache files.

When making changes: SKILL.md files reference scripts by `${CLAUDE_PLUGIN_ROOT}/scripts/<name>.py`. Never hardcode `~/.claude/plugins/article-craft/` paths in any SKILL.md, command, script, or hook — always use `${CLAUDE_PLUGIN_ROOT}` (or the `CLAUDE_PLUGIN_ROOT` env var in JS/Python). This was the entire theme of the 1.1.0 cleanup (see CHANGELOG.md).

### Key scripts and their roles

- `scripts/screenshot_tool.py` — Playwright-based screenshot capture with HEAD pre-check, smart selectors for GitHub/Twitter/Stack Overflow, and CDN upload. Reads `~/.cache/article-craft/verify-cache.json` (TTL 1h) written by the verify skill.
- `scripts/generate_and_upload_images.py` — batch processes `<!-- IMAGE: -->` / `<!-- PROMPT: -->` placeholders in an article.md, calls Gemini via `nanobanana.py`, compresses with Pillow, uploads through PicGo or S3, and edits the article file in place. The `--process-file` flag is the standard invocation.
- `scripts/nanobanana.py` — single-image Gemini call with the model fallback chain from `config.py`.
- `scripts/share_card.py` — optional social-platform card generator (9 platforms, 7 color presets). Reads article frontmatter.
- `scripts/config.py` — loads `~/.claude/env.json`, defines `VerificationCache`, `MODEL_FALLBACK_CHAIN`. All configuration (Gemini API key, S3, timeouts) lives in `~/.claude/env.json` — see `ENV.md`.
- `scripts/utils.py` — `PlaceholderManager` (in-place article mutation) and `SmartDirectoryMatcher` (knowledge base auto-placement for publish skill).
- `scripts/review_selfcheck.py` — the 11-rule self-check invoked by the review skill. Do not run it standalone from the orchestrator; the review skill calls it internally.
- `scripts/write_verify_cache.py` — writer counterpart to the verify cache; the verify skill calls it (single-URL or `--batch` JSONL) to populate `~/.cache/article-craft/verify-cache.json`.
- `scripts/bump_version.py` — bumps all 13 version carriers in lockstep: `.claude-plugin/plugin.json` (version + description `— vX.Y.Z` tail), `.claude-plugin/marketplace.json` (`plugins[0].version`), and every `skills/*/SKILL.md` frontmatter. Accepts `major` / `minor` / `patch` or an explicit `X.Y.Z`. Use `--no-tag` to let the GitHub workflow handle tag creation on push (recommended default).
- `lib/article-core.js` — tiny Node shim exposing `loadConfig()`, `resolveScriptPath()`, `findSkills()` for any JS-side consumers. Also respects `CLAUDE_PLUGIN_ROOT`.

### Cross-skill data flow

Skills pass state through three mechanisms:
1. **The article.md file itself** — the absolute path is captured after `write` and passed to every subsequent skill. Placeholders (`<!-- IMAGE: -->`, `<!-- SCREENSHOT: -->`) are the contract; downstream skills find and replace them.
2. **`~/.cache/article-craft/verify-cache.json`** — URL status cache shared between verify and screenshot (TTL 1h). Verify writes via `write_verify_cache.py`; screenshot reads via `VerificationCache` in `config.py`.
3. **Orchestrator context** — requirements outputs `_trusted_sources` (T0–T5 tiers) which verify uses to skip pre-trusted links and which write uses to cite official docs.

Since v1.4.2 there is also a **persistent state file** at `.article-craft-state.json` (next to `article.md`), written by the orchestrator at each stage boundary via `scripts/pipeline_state.py`. `--upgrade` mode reads this first and falls back to text heuristics only when the file is absent (backward compat for articles predating v1.4.2). The article content is still ground truth — if state says `images: completed` but the body still has `<!-- IMAGE: -->` placeholders, the stage is flagged `stale` and re-runs.

The **review skill** owns its own retry loop: Phase 1 self-check (11 rules, embedded) → Phase 2 7-dim scoring; if total score < 55/70 it auto-revises up to 3 rounds, then asks the user via AskUserQuestion. The loop also breaks early if a round produces a **non-improving score** (oscillation guard). The orchestrator does **not** wrap this in a second loop — it just trusts review's PASS/ABORT result.

## Common commands

Everything is shell-driven; there is no build system, no test suite, and no linter config in this repo.

```bash
# Install / reinstall the plugin (Python deps, Playwright, PicGo, Gemini key)
bash install.sh

# Install only Python deps
pip3 install -r scripts/requirements.txt

# Install Playwright browser (needed for screenshot_tool.py)
shot-scraper install     # or: playwright install chromium

# Exercise the pipeline end-to-end (inside Claude Code, not a shell)
/article-craft 写一篇关于 X 的技术文章
/article-craft --quick <topic>
/article-craft --draft <topic>
/article-craft --upgrade /abs/path/article.md

# Standalone skills (Claude Code slash commands — one per skill except orchestrator)
/article-craft:requirements /article-craft:verify /article-craft:write
/article-craft:screenshot  /article-craft:images  /article-craft:review
/article-craft:publish     /article-craft:lint    /article-craft:series
/article-craft:youtube

# Shortcut for the orchestrator's --upgrade mode (no matching skill directory)
/article-craft:upgrade /abs/path/article.md

# Bump the plugin version (source of truth: .claude-plugin/plugin.json)
python3 scripts/bump_version.py patch    # or: major | minor | 1.4.0

# Manually drive the image pipeline against an existing article
python3 scripts/generate_and_upload_images.py --process-file /abs/path/article.md

# Generate social share cards for an article
python3 scripts/share_card.py -f /abs/path/article.md \
  -p wechat-cover,twitter,xiaohongshu-sq --upload
```

## Conventions when editing this repo

- **Paths**: always `${CLAUDE_PLUGIN_ROOT}` in markdown/shell, `process.env.CLAUDE_PLUGIN_ROOT` in JS, read from env/argv in Python. Never `~/.claude/plugins/article-craft/`.
- **SKILL.md frontmatter**: every skill must declare `name`, `version`, `description`, and `allowed-tools`. As of v1.3.4 all 11 skills comply — do not regress this. The orchestrator's `allowed-tools` list must stay a superset of the union of what downstream skills declare.
- **Skill versions**: all 11 skills track the plugin version in lockstep. When bumping, use `scripts/bump_version.py` or update `.claude-plugin/plugin.json` + all 11 `skills/*/SKILL.md` frontmatter in the same commit.
- **Version bumps**: `.claude-plugin/plugin.json` is the source of truth, and **13 files must move in lockstep** — `plugin.json`, `marketplace.json`, and all 11 `skills/*/SKILL.md`. Use `python3 scripts/bump_version.py <major|minor|patch|X.Y.Z> --no-tag` to update all 13 atomically, then update `CHANGELOG.md` and commit. `.github/workflows/tag-release.yml` reads `plugin.json` on push to `main`; if the release for that version doesn't exist, it creates the tag + release (no auto-bump — that was a v1.3.2 bug fixed in v1.3.4). If the release already exists, the workflow is an idempotent no-op, so pushes without a version bump are safe.
- **Configuration**: all API keys, model selection, S3, timeouts go in `~/.claude/env.json` (see `ENV.md`). Do not add new config files; extend `scripts/config.py` to read additional keys.
- **New skills**: create `skills/<name>/SKILL.md` with frontmatter, then add a standalone command at `commands/article-craft/<name>.md`, then wire it into `skills/orchestrator/SKILL.md` if it belongs in the main pipeline. Every skill (except `orchestrator`) should have a matching sub-command file — this 1:1 mapping is the invariant downstream users rely on.
- **Command-level shortcuts**: if you want a dedicated slash entry point for an *orchestrator mode* (not a real skill), add a `commands/article-craft/<name>.md` that reads `skills/orchestrator/SKILL.md` and follows the relevant mode section — do **not** create an empty `skills/<name>/` directory. `commands/article-craft/upgrade.md` is the reference example: it's a shortcut for `--upgrade`, with no matching skill.
- **Reference docs**: writing rules live in `references/` (`writing-styles.md`, `self-check-rules.md`, `verification-checklist.md`, `knowledge-base-rules.md`, `gemini-models.md`). SKILL.md files should read these rather than inlining the rules.
- **Plugin hooks**: `hooks/hooks.json` registers a single `SessionStart` hook (matcher: `startup|resume|clear|compact|error`) that runs `hooks/run-hook.sh session-start` asynchronously. If you add hooks, keep the `${CLAUDE_PLUGIN_ROOT}` prefix and the async flag so session startup isn't blocked.

## Known design debt

These are architectural gaps identified in the v1.3.4 design review that were **intentionally deferred** because they require coordinated multi-file refactors. When you touch the adjacent code, consider taking one of these on:

- **Verify stage is misnamed and incomplete**. The current `verify` skill runs **before** `write`, so it only vets user-provided source URLs — it cannot validate claims the writer actually makes. The fix is a split: rename current verify to `source-vet` (what it really does, T0-T5 classification of the source pool), and add a new `verify-claims` stage **after** write that scans the article body for commands/API calls/flag names and confirms they exist. Until that lands, `write` Step 7 Check C does a grep-level approximation.
- **Images batch has no per-image 429 backoff**. `generate_and_upload_images.py --process-file` retries only at the probe layer (model fallback chain), not at the batch layer. If Gemini rate-limits mid-batch, half the placeholders ship unresolved. Fix: per-image exponential backoff inside the batch loop in `scripts/generate_and_upload_images.py`, with the model fallback chain re-triggered on 429/503.
- **Self-check rules are duplicated across three skills**. `references/self-check-rules.md` is supposed to be the single source, but `write/SKILL.md` Step 7, `lint/SKILL.md`, and `review/SKILL.md` Phase 1 each re-inline slices of it in prose. When you update the red-flag list, you must remember three places. Fix: make the three skills reference rules by number (e.g. "apply Rule 1 from references/self-check-rules.md") instead of re-stating them.
- **Review Phase 2 auto-modify is underspecified**. "For dimensions <7/10, fix corresponding issues" is a creative-rewrite instruction, not a mechanical transform. The oscillation guard (break on non-improving score) added in v1.3.4 bounds the damage, but the real fix is to make Phase 2 **scoring-only** (diagnostic, not corrective), surface an actionable feedback list, and let the user decide whether to re-run write with targeted section hints. Removing the auto-modify loop would also eliminate the orphan-image risk noted in review's Rule 11 warning.
