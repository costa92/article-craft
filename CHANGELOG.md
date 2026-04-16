# Changelog

## [1.4.8] - 2026-04-16

### Fixed

- **Lazy-loaded image harvest on WeChat pages was dropping ~80% of images.** Playwright extracted `<img>` tags before scrolling, so only above-the-fold images had their `src` / dimensions populated — a 31-image 新智元 article returned 6. `harvest_images()` now scrolls the page top → bottom in `innerHeight`-sized steps with 150ms pauses between scrolls, waits for network idle, then runs the extraction. On the same 新智元 article this lifts recall from 6 to 28 (90% vs baoyu-fetch's 31-link reference).
- **0×0 `<img>` entries leaking into evidence**. Invisible shares / profile / decorative `<img>` elements sometimes report both `width` and `height` as 0 (no box model). `_filter_harvest_images()` now drops these unconditionally. Previously they'd show up in `_evidence.json` and could be selected by a `HARVEST idx=N` that happened to land on one.

### Verified

Real integration run against `https://mp.weixin.qq.com/s/ZeQ8VOEC53rmXB4jPSfPDw`:

- Before: 6 images, cover populated ✅
- After: 28 images, cover populated ✅
- Width distribution: min 252, max 1280, median 661 — no stub images or tiny icons

### Design note

The scroll loop is defensive: wrapped in a broad `try / except`, a failure falls through to the existing extraction. For short pages (≤ 1 viewport), the loop runs once with 150ms overhead. For very long pages (10+ viewports), it adds ~2–3s of wall time. Worth the trade on WeChat / Weibo / Zhihu where lazy-load is the norm.

## [1.4.7] - 2026-04-16

### Added

- **`--cover` HARVEST syntax** (gap 3 from the v1.4.6 scoping). Source pages' cover image is now extracted during `harvest` (Playwright reads `og:image` / `twitter:image` meta tags; baoyu-fetch fallback reads `document.coverImage` / `media[]` role=cover) and stored at `source.cover` in `_evidence.json`. HARVEST placeholders gain `--cover` / `cover=1` to pick this instead of an `images[N]` entry. Priority: `--cover` > `idx=` > `alt=`.
- **`expand-harvest` subcommand** on `scripts/screenshot_tool.py` — real Python implementation of what used to be pseudocode in `screenshot/SKILL.md`. Takes `--article` and optional `--evidence`, reads `_evidence.json`, walks every `<!-- HARVEST: ... -->` placeholder, resolves the image (`--cover` / `idx=` / `alt=`), invokes `rehost_image()` per the placeholder's mode, rewrites `article.md` in place. Returns a JSON summary with per-placeholder trace: `status ∈ {expanded, source_not_in_evidence, no_matching_image}`, plus counts for `expanded` / `rehosted` / `failed`.
- **HARVEST opts parser** `_parse_harvest_opts()` — handles `idx=N`, `alt="…"`, `caption="…"`, `rehost=auto|always|never`, and `--cover` / `cover=1|true|yes`. Tested against 11 syntax variants.
- **`_pick_harvest_image()`** resolver with explicit priority: cover beats idx beats alt. alt uses case-insensitive substring match against `images[].alt`.

### Changed

- **screenshot/SKILL.md**: the HARVEST expansion section drops the ~25 lines of Python pseudocode, replaced by a single `subprocess.run` against `expand-harvest`. The SKILL.md now just documents what the subcommand does and what its JSON trace means — the actual loop / rehost / substitute logic lives in a testable Python function.
- **`harvest` CLI output**: result JSON now includes a `cover` field (empty string when not available).
- **`evidence.py` `_evidence.json` schema**: `sources[i]` gains `cover` field, pass-through from `harvest_images()` result.

### Why this pairs well

The v1.4.6 rehost pipeline added non-trivial decision logic (whitelist matching, per-placeholder mode override, graceful degradation). Leaving that logic as pseudocode in SKILL.md meant Claude would re-derive the flow each run, with risk of drift. Moving it into a subcommand:

1. Makes rehost failures observable per-placeholder via the `trace[]` array
2. Lets `--cover` slot in as one more resolver case with zero prompt-engineering
3. Reduces SKILL.md token cost (~25 lines of code → 1 subprocess call)
4. Unit-testable: the 7-placeholder end-to-end run exercises expanded / source-missing / idx-out-of-range / alt-substring / --cover / rehost=never / graceful-degradation in one article

## [1.4.6] - 2026-04-16

### Added

- **HARVEST rehost pipeline** — `scripts/screenshot_tool.py` gains `rehost_image()` + `rehost` CLI subcommand. When a HARVEST placeholder points at a hotlink-protected CDN (WeChat mmbiz, Weibo sinaimg, Zhihu zhimg), article-craft now downloads the original image with the correct `Referer` and re-uploads it via the existing PicGo / S3 pipeline before substituting into the article. Non-whitelist URLs pass through unchanged, preserving the v1.4.0 "远端 CDN 保持真源" philosophy where safe.
- **Per-placeholder `rehost=auto|always|never` override** in HARVEST syntax. Default `auto` = rehost only the whitelisted CDNs. Writers who know their target platform is hotlink-friendly can opt out per image with `rehost=never`.
- **`REHOST_CDN_WHITELIST` constant** mapping CDN substring → canonical Referer. Initial list: `mmbiz.qpic.cn` (WeChat article images), `mmbiz.qlogo.cn` (WeChat avatars), `sinaimg.cn` (Weibo, covers ww1/ww2/tva*/wx1-4 subdomains), `zhimg.com` (Zhihu, covers pic1-4).

### Fixed

- **`upload_to_s3` hard-coded `ContentType: 'image/jpeg'` regardless of file extension** — broke GIFs uploaded via rehost (served as JPEG, silently). Now infers `Content-Type` via `mimetypes.guess_type()`, falling back to `image/jpeg` only if inference fails or returns non-image.

### Design notes

- **Why rehost exists**: empirical test against a live mmbiz image confirmed the CDN returns **HTTP 200** with a ~2KB silent placeholder JPEG when the `Referer` is wrong (e.g., `google.com`), and the full 96KB image when Referer is `mp.weixin.qq.com` or absent. Since the final article will be read from a different origin (Obsidian vault / blog / Zhihu), the reader's browser sends *that* origin as Referer → silent stub. No HTTP error, no way to detect visually except by looking. rehost sidesteps the whole Referer dance by moving the image to our CDN.
- **GIF preservation**: `_infer_image_extension()` detects GIF via `wx_fmt=gif`, `.gif` suffix, or `Content-Type: image/gif`. rehost writes bytes through to tempfile with `.gif` extension, `upload_image()` picks the file up with correct MIME (now that upload_to_s3 respects extension). Bypasses Pillow compression entirely — animated GIFs stay animated.
- **Graceful degradation**: any failure in rehost (download timeout, HTTP error, upload failure, suspected hotlink stub) returns `ok=False` with `final_url == original_url`. The HARVEST expander keeps the remote URL and logs a warning. No pipeline aborts.
- **Stub-detection bar**: 4KB. Real Style H source images are typically 20–100KB. The 2086B mmbiz stub we measured is well under the bar.

### Scope

Fixes the two top gaps identified from reading a real 新智元 WeChat article (31 images, 4 GIFs, all `mmbiz.qpic.cn`):

1. mmbiz silent-hotlink breakage on non-WeChat platforms
2. GIF content-type mishandling in S3 path

The third identified gap — `--cover` shorthand for grabbing a source article's cover via `baoyu-fetch` metadata instead of the `<img>` list — is intentionally deferred as a low-priority convenience.

## [1.4.5] - 2026-04-16

### Added

- **New `verify-claims` skill + `scripts/verify_claims.py`.** Post-write stage that scans the article body for shell commands (bash / sh / shell / zsh blocks) and checks each named tool against PATH via `shutil.which`. Runs **after images, before review** in standard mode. Standalone invocation: `/article-craft:verify-claims /abs/path/article.md`.
- **New `commands/article-craft/verify-claims.md`** sub-command wrapper for the skill.
- **orchestrator Step 3.6** — new stage. Returns `PASS` / `PASS_WITH_MARKS` (user edited article to tag unknown tools with `[需要验证]`) / `ABORT`. Skipped in quick / draft modes.

### Changed

- **`write` Step 7 Check C removed.** Command correctness is no longer validated inline during write; it's been lifted into the dedicated verify-claims stage. Step 7 now runs 2 handoff contract checks (placeholder format + IMAGE double-line format) instead of 3. Rationale: Check C was a grep-level approximation that competed with a proper post-write scan for the same job.
- **Role clarification (no directory rename):** the pre-write `verify` stage is a **source vetter** (URL reachability, T0–T5 trust tiering). The post-write `verify-claims` stage is a **body vetter** (shell command existence). The two are complementary and non-overlapping. Skill directory names stay stable for command compat — `/article-craft:verify` still works and still does source vetting.
- **`scripts/pipeline_state.py`** — `verify_claims` added to the stage allowlist and to `MODE_STAGES["standard"]` / `MODE_STAGES["series"]`. `--upgrade` now correctly accounts for this stage when reporting missing / done.
- **orchestrator Step 3.7 (Publish) renumbered to 3.8** to make room for verify-claims at 3.6.
- **CLAUDE.md** — introductory paragraph clarifies the two verification stages; skill count updated from 11 to 12.

### Scope notes

- verify-claims MVP covers shell-language code blocks only. Flag-level validation, API endpoint reachability, version-string claims in prose, and Python / JS imports are explicitly out of scope — each is a future enhancement, not a bug. See `skills/verify-claims/SKILL.md` "Out of scope" list.
- Closes the "Verify stage is misnamed and incomplete" item in CLAUDE.md's "Known design debt". **All 5 original debt items are now closed.**

## [1.4.4] - 2026-04-16

### Changed

- **Review Phase 2 is now diagnostic-only.** Dropped the embedded 3-round auto-modify loop + oscillation guard. The new flow: score on 7 dimensions → produce per-dimension feedback (what failed / where / suggested action) → AskUserQuestion with 3 options (Publish anyway / Re-run write with hints / Abort). Each fix is a new explicit decision; review never mutates article content during Phase 2.
- **orchestrator Step 3.6** now recognizes a third return value from review: `NEEDS_REVISION_RERUN_WRITE` (user chose "Re-run write with hints"). On that outcome the orchestrator loops back to Step 3.3 (write), passing review's feedback list as targeted hints, then continues screenshot → images → review as normal. A loop guard caps this at 2 reruns per pipeline (the 3rd NEEDS_REVISION drops the "rerun" option from AskUserQuestion).

### Why

The `<dim-score><7` → "fix corresponding issues" instruction was too open-ended to converge reliably. In practice rounds often regressed one dimension while fixing another (the very oscillation the guard was built to detect), and — worse — auto-modify happened **after** the images stage, so edits could orphan `<!-- IMAGE: -->` placeholders or invalidate CDN references. Diagnostic-only sidesteps both failure modes.

### Design notes

- Handoff-contract comments and CDN URLs are now hard invariants: review never touches them in any code path.
- Phase 1 self-check (auto-fix for mechanical violations) is unchanged — it fixes red-flag words / hook length / closings / transitions per `references/self-check-rules.md` before Phase 2 scores.
- Closes the "Review Phase 2 auto-modify is underspecified" item in CLAUDE.md's "Known design debt". 1 item remains: verify rename/split (source-vet + verify-claims).

## [1.4.3] - 2026-04-16

### Added

- **Batch-level 429/503 backoff** in the sequential image pipeline. `scripts/generate_and_upload_images.py` now distinguishes "all models in the fallback chain exhausted with rate-limit errors" from "generic failure": the former raises a new `RateLimitExhausted` exception that the batch loop catches, then sleeps 30 / 60 / 120 seconds (with up to 5s jitter) before retrying the same image. After 3 exhausted backoffs, the image is skipped and the batch continues — no more "half the placeholders ship unresolved" when Gemini throttles mid-run.
- **`_generate_with_batch_backoff` helper** inside `generate_and_upload_images.py` isolates the backoff policy from the model fallback chain. Non-rate-limit failures still fail immediately (preserves existing "fail that image, continue the batch" semantics).

### Changed

- **`generate_image()` now raises `RateLimitExhausted`** instead of silently returning `False` when every model in the chain (`gemini-3-pro-image-preview` → `gemini-3.1-flash-image-preview` → `gemini-2.5-flash-image`) hit 429/503/rate-limit/resource_exhausted. Callers that don't want batch backoff can still catch the exception and treat it as a plain failure.

### Design notes

- Fixes the sequential path only. The parallel path (`generate_and_upload_parallel`, activated by `--parallel`) still has probe-layer retries only; coordinating batch-level backoff across a thread pool is a separate refactor and not currently on the orchestrator's hot path.
- Worst-case added wall time per image: 30 + 60 + 120 + ~15s jitter ≈ 3.5 minutes before giving up. This is intentional — Gemini quota resets on a 1-minute window, so the 30s first retry usually clears it.
- Closes the "Images batch has no per-image 429 backoff" item in CLAUDE.md's "Known design debt" list (sequential path). 2 items remain: verify rename/split (source-vet + verify-claims) and review Phase 2 auto-modify → scoring-only.

## [1.4.2] - 2026-04-16

### Added

- **Persistent cross-stage state file** — `.article-craft-state.json`, co-located with each article. The orchestrator writes stage status (running / completed / failed / skipped) with per-stage result payloads at every pipeline boundary. Resurrects `scripts/pipeline_state.py` (deleted in v1.3.4) with a real CLI, proper schema versioning, atomic writes, and now actually wired into the orchestrator.
- **`pipeline_state.py` CLI** with subcommands: `init`, `start`, `complete`, `fail`, `skip`, `show`, `missing-stages`, `cleanup`, `reset`, `artifact`. The `missing-stages` command is the primary `--upgrade` entry point — it returns structured JSON with `missing` / `done` / `stale` / `skipped` lists plus a `source` field (`state_file` / `hybrid` / `heuristic`).
- **State-file conflict resolution**: article content remains ground truth. If state says `images: completed` but the body still has `<!-- IMAGE: -->` placeholders, the stage is flagged `stale` and re-runs. `source: "hybrid"` in the output makes the disagreement visible.

### Changed

- **`--upgrade` mode** now reads `.article-craft-state.json` first and falls back to content heuristics only when the file is absent. Articles predating v1.4.2 still work through the heuristic path (pure `source: "heuristic"` result).
- **orchestrator/SKILL.md Step 2** now initializes the state file after `write` produces an article path. A new "State Write Protocol" section documents `start`/`complete`/`fail`/`skip` calls + per-stage result payload shapes for all 9 stages.
- **`publish` stage cleanup**: in standard mode, the state file is deleted after `publish` completes successfully — the pipeline is done, no state needed. `draft` and `quick` modes preserve the state file so future `--upgrade` can resume from it.

### Design notes

- State file lives next to `article.md` so it survives `git mv`. Schema is versioned (`schema_version: "1"`) for future migrations; the current `pipeline_version` is recorded for audit.
- Standalone skill invocations (`/article-craft:lint`, `/article-craft:review`) do not write state. State is orchestrator-only, since it only has meaning for multi-stage pipeline runs.
- Closes the "No persistent cross-stage state file" item in CLAUDE.md's "Known design debt" list. 3 items remain: verify rename/split (source-vet + verify-claims), images batch 429 backoff, and review Phase 2 auto-modify → scoring-only.

## [1.4.1] - 2026-04-16

### Changed

- **Self-check rules are now single-sourced** in `references/self-check-rules.md`. The `write`, `lint`, and `review` skills previously re-stated the 11 rules inline — ~241 lines of duplication across 3 skills. They now reference the canonical source by rule number, declaring only their enforcement role (pre-save GATE vs auto-fix vs detect-only). New "Who enforces what" matrix at the top of the rules file makes ownership unambiguous.
- **`references/self-check-rules.md` rewritten** (201 → 433 lines). Each rule now carries explicit `Severity` / `Auto-fix` / `Escalation` metadata. Rule 1 auto-fix mapping, Rule 5 transition-word list (5 words), Rule 11 ASCII-diagram grep (12 canonical single chars) all live here once.
- **Rule 7b (minimum AI image count) migrated from review to the canonical source**, including the degradation-detection pre-check that downgrades to WARNING when unresolved `<!-- IMAGE: -->` placeholders exist (prevents orphan-placeholder injection when images stage degraded).
- **Rule 11 (ASCII diagrams) split into three-role semantics**: write Step 6 pre-save GATE auto-converts; lint reports only (may run anywhere in pipeline); review detect-only and blocks Phase 2 via AskUserQuestion. Previously this distinction lived in review's inline copy.

### Fixed

- **lint's ASCII grep drift**: was `│|├|└|┌|┐|─|▼|▶|←→|──→|←──` (12 chars + 3 useless combined sequences, missed `↑↓`). Now uses the canonical single-character set `│|├|└|┌|┐|─|▼|▶|←|→|↑|↓` shared with write and review.
- **Transition-word list divergence**: lint had 5 words, rules.md + review had 4. Unified to 5 (`此外|另外|同时|值得注意的是|除此之外`) as the canonical list.
- **Rule 11 auto-fix instructions in rules.md** contradicted review's v1.3.2 "detect-only" architecture fix. Rewrote to match actual behavior: only write Step 6 auto-converts (pre-images), everyone downstream either reports or blocks.

### Design notes

- The rules.md file is now the **only** place rule bodies, grep patterns, and auto-fix mappings live. SKILL.md files declare *which rules they enforce and how* but do not re-type the rules. Adding or changing a rule is now a one-file edit.
- Phase 2 scoring (7 dimensions), oscillation guard, write Step 6/7 gates, and handoff-contract invariants are unchanged. This is purely a deduplication refactor.

## [1.4.0] - 2026-04-15

### Added

- **Style H — 爆料自媒体 / 公众号爆款** in `references/writing-styles.md`: new writing style modeled on 新智元/量子位/机器之心 voice — 戏剧性标题、H2 钩子句、源图直引、竞争对垒叙事、泄露代号对照、极短段落。Includes auto-detect signals ("曝光"、"爆料"、"突袭"、"泄露"、"一夜"、"硬刚"、股价/竞品对垒) and hard constraints enforced by the write skill.
- **New `evidence` skill** (`skills/evidence/SKILL.md` + `commands/article-craft/evidence.md` + `scripts/evidence.py`): collects source evidence for Style H. Parses `materials.md` (public URLs / local paths / gated citations), batches `harvest` calls across all public sources, outputs `_evidence.json` consumed by write. BLOCKS the pipeline for Style H when materials are missing or evidence-image count < 2.
- **`screenshot_tool.py harvest` subcommand**: extracts all `<img>` URLs + alt + width/height + surrounding context from a source URL. **Playwright primary** (fast, JS-rendered) with **baoyu-fetch fallback** for CAPTCHA / login walls / paywalls (auto-detects 微信公众号 / Cloudflare gates and switches engines). Output JSON is directly consumed by `evidence.py`.
- **`<!-- HARVEST: url idx= | alt= [caption=] -->` placeholder**: expands in-place to `![caption](远端 url)` without downloading or re-uploading. Implements the 新智元-style "直引源站图片" pattern — the remote CDN stays the source of truth, article-craft never becomes the image host. Processed by screenshot skill alongside existing `<!-- SCREENSHOT: -->` placeholders.

### Changed

- **orchestrator/SKILL.md**: pipeline is now 8 skills (added `evidence` between `verify` and `write`). Style H makes `evidence` mandatory in every mode (standard / quick / draft); other styles mark it `skipped`. Pipeline BLOCKS if `_evidence.json` is missing or has < 2 images when Style H is selected.
- **write/SKILL.md**: adds Style H branch — 【导读】加粗 H5 替代 `> [!abstract]` callout, consumes `_evidence.json`, enforces ≥2 evidence images, requires hook-style H2 titles (感叹号 / 动词 / 代号 / 数字), forbids Obsidian callouts + "综上所述" collider phrases + 客观中性 H2 描述, requires 参考资料 section + 公众号三板斧 ending.
- **screenshot/SKILL.md**: adds HARVEST placeholder scan alongside SCREENSHOT; documents the remote-URL inlining contract; adds `harvest` subcommand docs.

### Design notes

- HARVEST vs SCREENSHOT distinction is now the canonical way to decide "reuse remote image" vs "capture new image". Use HARVEST for 源文章已有的图; SCREENSHOT for 空的页面需要自己截；manual 本地路径走 `SCREENSHOT: /abs/path`.
- baoyu-fetch fallback is opt-out (`--no-fallback`) but only triggers when Playwright hits an auto-detected gate (CAPTCHA markers, HTTP >= 400, login walls). Keeps the happy path fast while giving the unhappy path a real escape hatch.

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
