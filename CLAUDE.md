# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`article-craft` is a **Claude Code plugin** (not a runtime application) that ships 13 composable skills for the full article generation lifecycle, plus the orchestrator that composes them. The repo is the source that gets installed to `~/.claude/plugins/article-craft/` via `install.sh` or the Claude Code plugin marketplace. Skills are executed by Claude Code itself — this repo contains the prompts, references, and supporting Python scripts, not a service to run.

**Two verification stages (since v1.4.5):** `verify` runs **before** `write` and vets the *sources* (URL reachability, T0–T5 trust tiering — this is effectively a source-vet stage, the directory kept its name for command compat). `verify-claims` runs **after images, before review** and vets the *article body* (scans shell code blocks for tool names, checks each is on PATH via `scripts/verify_claims.py`).

**WeChat distribution focus (v1.7.x):** Built on the experience of an author whose published WeChat articles consistently underperformed (4 articles, 8 rules with 100% failure rate against `review_selfcheck.py`). The v1.7.x series adds 6 new self-check rules (Rules 18-24, except 21 reserved) targeting WeChat compliance + reach mechanics + LLM systematic failure modes. **Active rule count: 23 (v1.7.4; unchanged through v1.8.4)**. Rule details: `references/self-check-rules.md`. Empirical validation: v1.7.4 dogfood article passes 23/23 vs the original 4 articles' 63% pass rate — augmentation > gating works.

## Architecture

### The orchestrator pattern

Everything funnels through `skills/orchestrator/SKILL.md`, which composes the main article pipeline:

```
requirements → verify → [evidence if Style H] → write → screenshot → (share_card?) → images → verify-claims → review → publish
```

Each skill is also callable standalone via `/article-craft:<skill-name>`. The `commands/article-craft.md` slash command simply instructs Claude to read and follow the orchestrator SKILL.md, passing `$ARGUMENTS` through.

Four workflow modes change which steps run:
- **standard** (default): requirements + verify + conditional evidence + write + screenshot + optional share card + images + verify-claims + review + publish
- **quick** (`--quick`): skips both verification stages, review, and publish
- **draft** (`--draft`): requirements + conditional evidence + write only
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
- `scripts/share_card.py` — optional social-platform card generator (11 `PLATFORMS` presets = 9 platforms + 2 aliases, 7 `COLOR_PRESETS`). Reads article frontmatter.
- `scripts/config.py` — loads `~/.claude/env.json`, defines `MODEL_FALLBACK_CHAIN`, `cache_dir()`, tone tables. All configuration (Gemini API key, S3, timeouts) lives in `~/.claude/env.json` — see `ENV.md`.
- `scripts/utils.py` — `PlaceholderManager` (in-place article mutation) and `SmartDirectoryMatcher` (knowledge base auto-placement for publish skill).
- `scripts/review_selfcheck.py` — the 23-rule self-check invoked by the review skill (`check_rule_1` … `check_rule_24`, with Rule 21 reserved → 23 active, dispatched from `_RULE_DISPATCH` at the bottom of the file). The pre-save write GATE subset is `WRITE_GATE_RULES = (1, 2, 6, 13, 14, 16)` — Rule 11 (placeholder residue) is **not** in the write gate (placeholders are expected pre-images); Rule 14 (ASCII-in-code-blocks) is the pre-images gate. Do not run it standalone from the orchestrator; the review skill calls it internally.
- `scripts/write_verify_cache.py` — writer counterpart to the verify cache; the verify skill calls it (single-URL or `--batch` JSONL) to populate `~/.cache/article-craft/verify-cache.json`.
- `scripts/bump_version.py` — bumps `plugin.json`, `marketplace.json`, and every `skills/*/SKILL.md` frontmatter in lockstep. Accepts `major` / `minor` / `patch` or an explicit `X.Y.Z`. Use `--no-tag` to let the GitHub workflow handle tag creation on push (recommended default).
- `lib/article-core.js` — tiny Node shim exposing `loadConfig()`, `resolveScriptPath()`, `findSkills()` for any JS-side consumers. Also respects `CLAUDE_PLUGIN_ROOT`.

### Tone system (v1.4.18)

Three-tier register intensity (`neutral` / `casual` / `opinionated`),
threaded as a frontmatter field through the entire pipeline. Resolution
precedence: `--tone` CLI > frontmatter `tone:` > `STYLE_TO_TONE_DEFAULT`
in `scripts/config.py`. Rule 17 in `scripts/review_selfcheck.py` runs
four tier-aware sub-checks; `scripts/lint_article.py` consumes
`TONE_LEXICAL_REWRITES` with Vale-style severity (info/warning/error),
inline `<!-- lint:disable rule_id -->` regions, and a 3-pass oscillation
guard; `skills/write/style-guide.md` has three matching `## Tone: <tier>`
sections used by the writer prompt.

Calibration data lives at `~/.cache/article-craft/tone-calibration.jsonl`
and seeds future threshold tuning. Opt out via `ARTICLE_CRAFT_TONE_CALIBRATION=false`.

Spec: `docs/superpowers/specs/2026-05-07-tone-system-design.md`.
Plan: `docs/superpowers/plans/2026-05-07-tone-system.md`.

### Body-form axis (v1.8.0)

A second orthogonal axis alongside tone: `body_form` decides 正文形态 —
`wechat-native` (default, mobile-shaped 公众号 body: short paragraphs, no
Obsidian callouts, ≤ `##`/`###` headings, image rhythm, single throughline)
vs `long-form` (today's blog body: callouts allowed, deep sections — the
KB/blog archive copy). It is independent of *style* (A–H content identity)
and *depth* (字数): a `wechat-native + deep` article is long but mobile-shaped.

Resolution precedence (mirrors tone): `--body-form` CLI > frontmatter
`body_form:` > legacy `wechat_target: false` alias > default `wechat-native`.
The canonical resolver is `config.resolve_body_form()`. **`wechat_target` is
no longer dead** — `wechat_target: false` is the back-compat spelling for
`body_form: long-form`. requirements emits `body_form` into article
frontmatter; write injects the matching `## Body Form` section from
`style-guide.md` and renders callouts only under `long-form`;
`check_rule_6` lowers its per-section threshold by 1 for `wechat-native`;
review adds a **soft** Phase-2 form-consistency signal (no new write gate —
augmentation > gating). Default is always `wechat-native`; `long-form` is
opt-in only (never auto-inferred from depth/教程 keywords).

Spec: `docs/superpowers/specs/2026-05-29-wechat-native-body-form-design.md`.
Plan: `docs/superpowers/plans/2026-05-29-wechat-native-body-form.md`.

### WeChat distribution rules (v1.7.x)

5 incremental releases (v1.7.0–v1.7.4) shipped over 5 days, driven by
**4-article dogfooding** that found 8 self-check rules with 100% failure
rate on real WeChat publications. Each release targets one failure mode:

| Release | Adds | Targets failure mode |
|---|---|---|
| **v1.7.0** | Rules 18-22 + CTA + double cover | WeChat compliance + base hooks |
| **v1.7.1** | Rule 23 + publish step 3.5 checklist | Anti-recommendation blacklist + 6-item human checklist |
| **v1.7.2** | Rule 24 + Rule 23 bugfix | LLM-fabricated numbers + `strip_code_blocks` regression |
| **v1.7.3** | Style G + opinionated enhanced template | 4 fill-in-the-blank tables (个人经历 / 主观判断 / 强观点 / 具体锚点) |
| **v1.7.4** | Rule 4 tag enforcement (write + publish) | Defense-in-depth for ≥3 Chinese tags |

**Design philosophy: augmentation > gating.** Considered adding
Rules 5/17/22 to `WRITE_GATE_RULES` but rejected — too high FP rate (8-12%
empirically) would force writing loops. Instead, the prompt augmentation
in `style-guide.md` `### Style G + opinionated 加强模板` section feeds
句式表 directly into the LLM's writing context. **v1.7.4 dogfood**:
1 dogfood article passes 23/23 vs 4 historical articles' 14.5/23 average,
suggesting the augmentation path works without forcing reviewer loops.

**Empirical validation cadence:** 4-6 week observation window for v1.7.4
augmentation effectiveness. If new articles' Rule 17/22 pass rate doesn't
hold above 80%, v1.7.5 starts the gating path as plan B.

**A/B tier research basis:** all v1.7.x rule additions trace to A-tier
official sources (cac.gov.cn / openstd.samr.gov.cn / mp.weixin.qq.com or
developers.weixin.qq.com 运营专员 answers) or B-tier (mainstream media
citing 微信珊瑚安全 / 微信团队). Detailed evidence chain in
`.research/official-sources-verification.md` (round 1, 20 propositions)
and `.research/wechat-distribution-mechanism-2026.md` (round 2, 9 incremental
propositions). When adding new rules, follow the same evidence-chain
convention: each rule → 1 commit → commit message links ≥1 first-party URL.

**Rule 5 / Rule 6 and real author experience:** Rule 6 (浅层章节) still
needs runnable code blocks from real work — no augmentation can fabricate
them, so it stays **deferred**: the author needs to live the project.
Rule 5 (反 AI 结构) used to share this debt but was **partially addressed
in v1.8.4** (attribution-as-voice): source attribution (据/根据/官方/原文/
"视频里说") now counts as a valid concrete anchor, and Rule 5 skips
conclusion/intro sections — so a faithfully-attributed source summary no
longer gets penalized for "缺少具体锚点" while a fabricated-anecdote article
passes. This removed a perverse fabrication-reward incentive. The v1.7.4
dogfood article passes both because the author (Costa) genuinely lived the
v1.7.x evolution; future from-scratch articles still hit Rule 6 unless they
bring real material.

### Cross-skill data flow

Skills pass state through three mechanisms:
1. **The article.md file itself** — the absolute path is captured after `write` and passed to every subsequent skill. Placeholders (`<!-- IMAGE: -->`, `<!-- SCREENSHOT: -->`) are the contract; downstream skills find and replace them.
2. **`~/.cache/article-craft/verify-cache.json`** — URL status cache shared between verify and screenshot (TTL 1h). Verify writes via `write_verify_cache.py` (`CACHE_TTL = 3600`); screenshot reads it via `VERIFY_CACHE_FILE` in `screenshot_tool.py`. Both resolve the path through `config.cache_dir()`.
3. **Orchestrator context** — requirements outputs `_trusted_sources` (T0–T5 tiers) which verify uses to skip pre-trusted links and which write uses to cite official docs.

Since v1.4.2 there is also a **persistent state file** at `.article-craft-state.json` (next to `article.md`), written by the orchestrator at each stage boundary via `scripts/pipeline_state.py`. `--upgrade` mode reads this first and falls back to text heuristics only when the file is absent (backward compat for articles predating v1.4.2). The article content is still ground truth — if state says `images: completed` but the body still has `<!-- IMAGE: -->` placeholders, the stage is flagged `stale` and re-runs.

The **review skill** runs Phase 1 self-check (23 rules, embedded — see `scripts/review_selfcheck.py`) → Phase 2 8-dim scoring (threshold 63/80). **Since v1.4.4 Phase 2 is diagnostic-only — there is no auto-revise loop.** Earlier versions (≤ v1.4.3) auto-revised up to 3 rounds with an oscillation guard, but the open-ended "fix dimensions <7/10" instruction failed to converge and risked orphaning post-images placeholders, so it was removed. Phase 2 now scores once and, if `< 63/80`, surfaces an AskUserQuestion (Publish anyway / Abort / Re-run write with hints) — each revision is a fresh explicit user decision. The orchestrator caps "Re-run write with hints" at 2 re-jumps and trusts review's PASS/NEEDS_REVISION/ABORT verdict.

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

# Standalone skills (one per skill except orchestrator). Since v1.6.3 every
# command file lives at commands/<name>.md top-level so it resolves as the
# single-prefix /article-craft:<name> (was the doubled /article-craft:article-craft:<name>
# while files sat under commands/article-craft/).
/article-craft:requirements /article-craft:verify       /article-craft:evidence
/article-craft:write        /article-craft:screenshot   /article-craft:images
/article-craft:verify-claims /article-craft:review      /article-craft:publish
/article-craft:lint         /article-craft:series       /article-craft:youtube

# Shortcut for the orchestrator's --upgrade mode (no matching skill directory)
/article-craft:upgrade /abs/path/article.md

# Runtime healthcheck command — thin wrapper around scripts/doctor.py (no matching skill directory)
/article-craft:doctor          # or: /article-craft:doctor --json

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
- **SKILL.md frontmatter**: every skill must declare `name`, `version`, `description`, and `allowed-tools`. All 13 non-orchestrator skills comply (the invariant dates to v1.3.4's 12 skills; share-card became standalone in v1.6.7) — do not regress this. The orchestrator's `allowed-tools` list must stay a superset of the union of what downstream skills declare.
- **Skill versions**: all 13 non-orchestrator skills track the plugin version in lockstep. When bumping manually, update `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, and all `skills/*/SKILL.md` frontmatter in the same commit; `scripts/bump_version.py` does that for you.
- **Version bumps**: `.claude-plugin/plugin.json` is the source of truth, and `scripts/bump_version.py` must update `plugin.json`, `marketplace.json`, and all `skills/*/SKILL.md` frontmatter together. `.github/workflows/tag-release.yml` reads `plugin.json` on push to `main`; if the release for that version doesn't exist, it creates the tag + release (no auto-bump — that was a v1.3.2 bug fixed in v1.3.4). If the release already exists, the workflow is an idempotent no-op, so pushes without a version bump are safe.
- **Owner auto-merge CI** (`.github/workflows/auto-merge-owner.yml`, since v1.9.0): when the PR author equals `github.repository_owner` and the PR is non-draft, a `gate` job runs the test suite (excludes the Playwright E2E, which has its own workflow) and a `merge` job (`needs: gate`) then `gh pr merge --merge --delete-branch`. Non-owner PRs are left for human review. **Gotcha worth preserving**: a merge push made with `GITHUB_TOKEN` does *not* cascade-trigger `on: push` workflows, so `tag-release.yml` would never fire after an auto-merge and a version bump would ship untagged — the merge job works around this by explicitly `gh workflow run tag-release.yml --ref main` (`workflow_dispatch` is the documented exception to that suppression). If you touch either workflow, keep this dispatch link intact.
- **Configuration**: all API keys, model selection, S3, timeouts go in `~/.claude/env.json` (see `ENV.md`). Do not add new config files; extend `scripts/config.py` to read additional keys. A populated template lives at `env.example.json` in the repo root — keep it in sync when you add new keys.
- **Cache paths**: anything writing to a cross-process persistent cache (verify cache, screenshot cache, review-selfcheck cache) must resolve its path through `config.cache_dir()`. This is the only path that honors `ARTICLE_CRAFT_CACHE_DIR`. Session-scratch directories should use `tempfile.gettempdir()` rather than hardcoding `/tmp/`.
- **Model lists**: the canonical Gemini image fallback chain is `config.MODEL_FALLBACK_CHAIN`; the prompt-expansion text model is `config.TEXT_MODEL`. Don't duplicate these lists in callers — `import` them. Standalone scripts that need to run outside the plugin layout may keep a `try/except ImportError` fallback that mirrors the constants.
- **Brand strings**: card logos, public-facing names, and similar branded text must go through `config.share_card_logo()` (or a similar helper) so a fork can override via env.json without editing source. Never hardcode personal domains, usernames, or URLs in skill markdown — use placeholders or read from `config.VERIFY_CDN_WHITELIST`.
- **New skills**: create `skills/<name>/SKILL.md` with frontmatter, then add a standalone command at `commands/<name>.md` (top level — **not** under `commands/article-craft/`), then wire it into `skills/orchestrator/SKILL.md` if it belongs in the main pipeline. Every skill (except `orchestrator`) should have a matching sub-command file — this 1:1 mapping is the invariant downstream users rely on. The top-level placement is what makes the command resolve as `/article-craft:<name>` (single prefix) rather than the doubled `/article-craft:article-craft:<name>` a `commands/article-craft/<name>.md` location would produce.
- **Command-level shortcuts**: if you want a dedicated slash entry point for an *orchestrator mode* (not a real skill), add a `commands/<name>.md` that reads `skills/orchestrator/SKILL.md` and follows the relevant mode section — do **not** create an empty `skills/<name>/` directory. `commands/upgrade.md` is the reference example: it's a shortcut for `--upgrade`, with no matching skill. Same rule applies to script wrappers — `commands/doctor.md` wraps `scripts/doctor.py` without a backing skill.
- **Reference docs**: writing rules live in `references/` (`writing-styles.md`, `self-check-rules.md`, `verification-checklist.md`, `knowledge-base-rules.md`, `gemini-models.md`). SKILL.md files should read these rather than inlining the rules.
- **Plugin hooks**: `hooks/hooks.json` registers a single `SessionStart` hook (matcher: `startup|resume|clear|compact|error`) that runs `hooks/run-hook.sh session-start` asynchronously. If you add hooks, keep the `${CLAUDE_PLUGIN_ROOT}` prefix and the async flag so session startup isn't blocked.

## Known design debt

These are architectural gaps **intentionally deferred** because they require coordinated multi-file refactors or are blocked on real-world data. When you touch the adjacent code, consider taking one of these on:

### Open

- **Rule 6 (浅层章节) substance not auto-fixable.** Rule 6 needs runnable
  code blocks from work the author has actually done — no prompt
  augmentation can fabricate them. (Rule 6 *is* a write pre-save GATE —
  `WRITE_GATE_RULES` includes 6 — so a shallow chapter blocks save; what's
  "not auto-fixable" is the *substance*, since the gate can't write the
  missing code for you.) Rule 5 (反 AI 结构) used to share this debt but was
  **addressed in v1.8.4**: attribution-as-voice (`ATTRIBUTION_ANCHOR_REGEX`)
  lets source attribution count as a concrete anchor, Rule 22 passes on
  `个人经历 ≥2 OR 来源归属 ≥2`, and Rule 5 now skips conclusion/intro
  sections — removing the fabrication-reward incentive (see
  `tests/test_attribution_anchor.py`). Rule 5 remains detect-only,
  review-stage. See `references/self-check-rules.md` Rule 5/6 sections.

- **Rule 24 (虚构数字) high warning-density tolerance.** v1.7.4 dogfood
  article generates 36 unverified-number warnings (mostly version numbers
  like `v1.7.0/1/2/3/4` and self-evident counts like "5 个 release"). The
  rule is intentionally warning-only (not blocking), but if authors learn
  to ignore high-density warnings the rule loses signal value. Two
  possible refinements: (a) auto-exempt version-number patterns
  (`v\d+\.\d+\.\d+`), (b) bucket warnings by "novel claim" vs "structural
  reference" and only count novel claims toward the high-density threshold.

- **v1.7.4 augmentation path needs 4-6 week field validation.** The dogfood
  experiment is n=1. If new articles by Costa or other adopters don't
  consistently hit 80%+ Rule 17/22 pass rate, v1.7.5 starts the gating
  path as plan B (adding Rules 5/17/22 to `WRITE_GATE_RULES` despite
  the 8-12% FP penalty).

### Closed (kept for historical context)

- ~~**Images parallel path still lacks coordinated backoff**~~. Fixed in v1.4.3 for the **sequential** batch loop. The **parallel** path now also has worker-coordinated backoff via `_ParallelRateLimitCoordinator` in `scripts/generate_and_upload_images.py` — when one worker exhausts the model fallback chain (`RateLimitExhausted`), it sets a shared pause window and every other worker blocks in `wait_if_paused()` before its next `generate_image()` call. Multiple concurrent rate-limit signals coalesce into the longest end-time. Per-image attempt counters preserve sequential-equivalent semantics. Exercised by `tests/test_image_parallel_backoff.py` (13 tests, runs in <2s by patching `BATCH_BACKOFF_DELAYS_SEC` / `BATCH_BACKOFF_JITTER_MAX_SEC`).
- ~~**Self-check rules are duplicated across three skills**~~. Closed via the v1.4.x refactor: `write/SKILL.md` Step 7 explicitly delegates content-quality rules to `review` Phase 1 and only checks downstream-skill handoff contracts; `lint/SKILL.md` invokes `scripts/lint_article.py` for Rule 5 mechanical fixes; `review/SKILL.md` Phase 1 references rules by number from `references/self-check-rules.md`. The canonical rules now live in one place.
- ~~**Rule 23 strip_code_blocks regression**~~ (v1.7.1 → v1.7.2). First-pass `check_rule_23` computed `body = strip_code_blocks(content)` but then iterated `lines` (full content), so articles documenting Rule 23 itself (with reverse-declaration examples in ```text blocks) were falsely flagged. Fixed by tracking code-block line numbers in a set and skipping them in the violation loop. 8 unit tests in `tests/test_rule_23_code_block_exempt.py` pin the contract.
