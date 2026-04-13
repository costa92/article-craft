# Changelog

## [1.3.4] - 2026-04-13

### Fixed

- **CI workflow** (`tag-release.yml`): removed buggy auto-bump logic where the `if: skipping == 'false'` condition on the Bump step was inverted — the workflow was bumping the patch version on every push whose version didn't yet have a release (rather than only when a release collision existed), and the bump was never committed back to the repo, so `plugin.json` and the published tag drifted apart. The workflow is now a clean "read plugin.json → create tag + release, or skip if already released" no-auto-bump loop. `plugin.json` is authoritative.
- **marketplace.json**: synced `plugins[0].version` from stale `1.1.0` to the plugin version. It had drifted since March 2026 and was not surfaced until the v1.3.4 version audit.

### Changed

- All version-carrying files bumped in lockstep to `1.3.4`: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, and all 11 `skills/*/SKILL.md` frontmatter. When bumping in the future, touch all 13 in the same commit (the workflow will not do this for you).

## [1.3.2] - 2026-04-10

### Fixed (runtime + contract)

- **publish**: repaired broken `os.path.expanduser("${CLAUDE_PLUGIN_ROOT}/...")` Python snippet that would fail at runtime; added missing `import os, sys`.
- **orchestrator / images**: fixed unbalanced markdown code fences that broke rendering of the status tracker and image script examples.
- **review**: removed orphaned `Rule 12–15` references from the output template; aligned rule count header to 11.
- **orchestrator**: removed the outer review retry loop that compounded review's internal 3-round loop into up to 9 rounds.
- **write**: replaced direct `review_selfcheck.py` invocation with inline Grep/Bash handoff checks; renamed "Rule X" to "Check X" to stop colliding with review's rule numbering.
- **review / orchestrator / lint**: purged stale `content-reviewer` references (review is now self-contained).

### Fixed (architecture + design)

- **review Rule 11 (ASCII diagram check)**: stopped auto-converting to `<!-- IMAGE: -->` placeholders. Review runs after the images stage, so any new placeholder would be orphaned (never generated). Now detect-only with `FAIL — escalate`; conversion remains `write` Step 6's responsibility.
- **review Rule 7b (min image count)**: added degradation detection. If the article has unresolved `<!-- IMAGE: -->` placeholders (meaning images stage failed), rule downgrades to WARNING and skips placeholder injection instead of adding more orphans.
- **review auto-revision loop**: added oscillation guard — break early if `score_{round} <= score_{round-1}` — to prevent ping-pong between conflicting fixes. Revisions must also preserve handoff-contract comments (IMAGE / PROMPT / SCREENSHOT / CDN URLs).
- **orchestrator Step 0 Preflight**: verify Gemini key, Playwright chromium, and PicGo before running any skill. Fail fast instead of wasting 60–120 s to explode at the images stage.
- **orchestrator quick mode**: emits `UNVERIFIED CITATIONS` warning block in the completion summary when T3–T5 community sources were cited without `verify`.
- **orchestrator share_card**: removed mid-pipeline `AskQuestion`; auto-infer from frontmatter completeness and accept `--share-cards=yes|no|auto` flag. Autonomous runs no longer block.
- **write draft mode**: prints `/article-craft --upgrade PATH` resume hint in the completion message so users know how to finish a draft.
- **publish**: added `--output DIR` override as an escape hatch from KB auto-detection; Step 1 splits into Mode A (explicit) and Mode B (auto-detect).
- **verify**: made cache TTL configurable via `env.json` key `verify_cache_ttl_seconds`; `--series` auto-extends to 24 h so multi-article runs share vetting.
- **write Step 7**: deduped handoff checks. Removed Check 1 (red-flag), Check 3 (template summary), Check 5 (chapter depth) — these are `review`'s job. Kept only Check A (placeholder format), Check B (IMAGE double-line contract), Check C (command verification).

### Added

- **All 10 non-orchestrator skills**: declare `allowed-tools` in frontmatter (previously only orchestrator did).
- **CLAUDE.md**: introduced with project overview, key scripts, cross-skill data flow, conventions, and a "Known design debt" section documenting intentionally deferred refactors (verify rename/split, images batch 429 retry, rule deduplication across 3 skills, review Phase 2 scoring-only redesign, persistent cross-stage state file).

### Removed

- **`scripts/pipeline_state.py`**: deleted 150 lines of dead code — never imported by any skill. `--upgrade` mode continues to use text heuristics until a real state file is designed (see Known design debt).

### Housekeeping

- Aligned all 11 skill versions to the plugin version (previously drifted at 1.2.0 / 1.3.0 / 1.3.1).
- Normalized `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*.py` invocations across `screenshot` skill (some were bare `python3 script.py`).
- Removed duplicate `## Verification Philosophy` section from `verify/SKILL.md`.
- Fixed `Three modes` / 5-row table contradiction in `orchestrator/SKILL.md`.
- Deleted trailing stale version note in `write/SKILL.md`.

## [1.1.0] - 2026-03-31

### Changed

- **Path compatibility**: All hardcoded paths replaced with `${CLAUDE_PLUGIN_ROOT}` dynamic variable across all 12 command files, 11 SKILL.md files, scripts, and hooks.
- **SKILL.md frontmatter**: Added `version` and `allowed-tools` fields to all 11 skills for better Claude Code integration.
- **README.md**: Rewritten to match Claude Code plugin marketplace standard with marketplace installation instructions.
- **plugin.json**: Added `license` and `keywords` fields, removed `install` field (dependencies handled by `install.sh`).
- **marketplace.json**: Updated owner info and synchronized version to 1.1.0.
- **hooks.json**: Extended SessionStart matcher to include `error` event.
- **hooks/run-hook.sh**: Replaced hardcoded path with `${CLAUDE_PLUGIN_ROOT}` fallback.
- **lib/article-core.js**: Replaced hardcoded path with `CLAUDE_PLUGIN_ROOT` environment variable.
- **INSTALL.md**: Streamlined to two-screen quickstart, prioritizing `install.sh` one-command setup.
- **scripts/README.md**: Updated path references.

### Added

- **install.sh**: Interactive one-command installer covering Python deps, shot-scraper, PicGo, Gemini API key, and verification.

## [1.0.0] - 2026-03-22

- Initial release with 11 composable skills for the full article lifecycle.
