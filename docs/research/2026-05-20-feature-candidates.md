# Feature Candidates — post-v1.6.2 backlog research

> **Date**: 2026-05-20
> **Baseline**: v1.6.2 (`/article-craft:doctor` command name fix)
> **Method**: Codebase + CHANGELOG + design-debt audit conducted by a research agent.
> **Status**: Backlog reference. Not a roadmap — items here have not been triaged or committed.

---

## Summary

The plugin is mature and well-tested (228 tests passing, ~11.7K LOC of Python,
13 skills + orchestrator, all five "Known design debt" items from v1.3.4 closed
by v1.5.x). The dominant fragility theme of the last 10 releases is **silent-
failure modes around external rendering / upload** — every patch release since
v1.5.1 fixed something where the pipeline reported success while shipping
broken artifacts. The single biggest opportunity is **converting the v1.6.0
batch (`doctor.py` / `publish_plan.py` / `series_state.py`) from "exists" into
"first-class observability + test coverage,"** plus closing the cookie-gated
platform gap that v1.5.6 explicitly deferred.

---

## A. Recurring fragility patterns

### A1. Silent stub / stdout pollution in upload paths

- **Evidence**: v1.5.2 fixed `screenshot_tool.upload_to_cdn()` silently
  returning local paths because picgo emits multi-line `[PicGo INFO]` logs,
  not JSON. v1.4.16 fixed `rehost` / `expand-harvest` polluting stdout with
  the same upload progress (broke `| jq` pipelines). v1.4.6 fixed `mmbiz`
  returning HTTP 200 + 2KB stub when `Referer` was wrong (rehost added).
  v1.5.1 found `upload_to_s3` hardcoding `image/jpeg` regardless of extension.
- **Root cause**: Every subprocess shell-out to PicGo / S3 / Playwright
  invents its own output contract. There is no canonical "uploader
  interface" — `generate_and_upload_images.upload_to_picgo`
  (`scripts/generate_and_upload_images.py:1131`) and
  `screenshot_tool.upload_to_cdn` (`scripts/screenshot_tool.py:977`) parse
  their own outputs and `rehost_image` invents its own stub-detection bar
  (4 KB).

### A2. Screenshot framing / selector regressions

- **Evidence**: v1.4.17 (full-page default → viewport), v1.5.3 (900 px cap +
  ANCHOR), v1.5.4 (anchor scoping bug → was matching sidebars), v1.5.5
  (`HOST_MAIN_SELECTORS` introduced for 14 platforms), v1.5.6 (height floor
  400→100; element-timeout viewport fallback). **Five consecutive releases
  on the same subsystem.**
- **Root cause**: One-off fixes preceded the abstraction. Every new platform
  = empirical reverse-engineering of DOM. No automated regression —
  `tests/test_screenshot_crop.py` only checks the selector-dict
  registration, not actual rendered output.

### A3. Sub-command name / path drift between releases

- **Evidence**: v1.6.2 fixed `/article-craft:doctor` resolving as
  `/article-craft:article-craft:doctor` (nested command file). v1.3.4 fixed
  `marketplace.json` `version` stuck at 1.1.0 for months. v1.3.2 fixed
  `os.path.expanduser("${CLAUDE_PLUGIN_ROOT}/...")` runtime crash from a
  missing import. v1.1.0 was a sweep removing hardcoded
  `~/.claude/plugins/article-craft/` paths.
- **Root cause**: No CI step actually exercises the installed plugin
  layout. A test that registers the marketplace → installs → runs each
  command's `--help` would catch every one of these.

### A4. Cross-stage state-assumption breakage

- **Evidence**: v1.4.15 (publish stranded `_evidence.json` sidecars,
  breaking re-upgrade). v1.5.1 (publish placeholder gate added because
  images-with-`--no-upload` silently shipped placeholder-laden articles to
  the KB). v1.4.10 (write Step 7 Check C — HARVEST validation at write
  time). v1.4.2 (added `.article-craft-state.json` because `--upgrade`
  was guessing from heuristics).
- **Root cause**: Each stage trusts the previous one's "success" claim,
  but actual ground truth is the article body. Defenses keep being added
  one regex at a time.

### A5. Rate-limit / quota handling rolled out twice

- **Evidence**: v1.4.3 added sequential batch backoff; v1.5.0 added the
  parallel coordinator. Both fix the same root issue half a year apart.
  The parallel path was "intentionally deferred" in CLAUDE.md until a
  reviewer asked again.
- **Root cause**: Design debt explicitly tracked in CLAUDE.md but only
  addressed when triggered. Now all closed — the pattern for the future
  is "consciously deferred items go in CLAUDE.md and need a closing PR."

---

## B. Candidate features (ranked)

### P0 — high-leverage, near-term

| # | Title | Effort | Risk |
|---|-------|--------|------|
| **B1** | Cookie-gated platform support for screenshots | S–M | Cookie storage security |
| **B2** | Image upload backend abstraction + standardized JSON contract | M | Minor — well-covered tests |
| **B3** | Real screenshot end-to-end snapshot tests | M–L | CI dep on Playwright (already required) |
| **B4** | `share_card` standalone skill + command | S | Zero |
| **B5** | `doctor.py` extended checks (network probe + env.json validity) | S | Low |

**B1. Cookie-gated platform support for screenshots** — *S to M*
Wire `setup-browser-cookies` into `screenshot_tool.py` so HN-HTTPS / Reddit /
知乎 / 微博 / 小红书 work end-to-end from headless.
- Problem: v1.5.6 explicitly deferred this as "Out of scope" (CHANGELOG).
  Five of the platforms whose selectors we added in v1.5.5 can't actually
  be screenshot from a headless context — the selector lands on a login
  wall.
- Refs: `skills/screenshot/SKILL.md:467` already references the
  `setup-browser-cookies` skill as the workaround; CHANGELOG v1.5.6
  "Out of scope" block.
- Effort: load a cookie jar via `browser_context.add_cookies()`; document
  the cookie-file location in `env.json`.

**B2. Image upload backend abstraction + standardized JSON contract** — *M*
Extract an `Uploader` protocol (`upload_to_picgo` / `upload_to_s3` / future
`upload_to_qiniu` / `imgbb`) and a parser-agnostic CDN-URL detector used
by both `screenshot_tool.upload_to_cdn` and
`generate_and_upload_images.upload_to_picgo`.
- Problem: see A1. v1.5.2 fixed one of the two parsers; the other already
  worked. There are two parallel implementations of "parse PicGo output"
  with subtly different defensiveness. Adding any new backend would need
  to know about both.
- Refs: `scripts/screenshot_tool.py:977-1034` re-imports `upload_image`
  from `generate_and_upload_images.py` as a band-aid; `screenshot_tool.py:989`.
- Effort: 1–2 days. Risk: minor — covered by `tests/test_screenshot_upload.py`
  and `tests/test_share_card_upload.py`.

**B3. Real screenshot end-to-end snapshot tests** — *M to L*
For each of the ~15 platforms in `HOST_MAIN_SELECTORS`
(`scripts/screenshot_tool.py:267-299`), record an HTML fixture + selector
+ expected bounding box; replay against Playwright in CI.
- Problem: see A2 — 5 consecutive releases on screenshot framing because
  there's no regression net. `tests/test_screenshot_crop.py` only tests
  the dict-lookup logic, not actual rendering.
- Refs: `HOST_MAIN_SELECTORS` at `screenshot_tool.py:267`; CHANGELOG
  v1.5.3 → v1.5.6.
- Risk: needs vendored or generated fixtures; CI dependency on Playwright
  browsers (already required by `doctor.py`).

**B4. `share_card` standalone skill + command** — *S*
Promote `scripts/share_card.py` to a first-class skill at
`skills/share-card/SKILL.md` with command
`commands/article-craft/share-card.md` (or top-level `commands/share-card.md`
for the single-prefix invocation — see C3 below).
- Problem: 553-line script with 9 platform presets and 7 color schemes
  that is effectively a major feature, yet not discoverable via
  `/article-craft:share-card`. Currently invokable only from
  `orchestrator` Step 3.4.5 and informally from `screenshot/SKILL.md:521`.
- Refs: `scripts/share_card.py` exists; no `commands/.../share-card.md`.
  `tests/test_share_card_upload.py` already covers the upload path.
- Effort: one SKILL.md + one command stub.

**B5. `doctor.py` extended checks** — *S*
Add network-reachability probes for Minimax / Gemini / PicGo target
endpoints; check `CLAUDE_PLUGIN_ROOT` env resolution; verify
`~/.claude/env.json` is valid JSON (currently parsed silently via
`_load_env_json` returning `{}` on error).
- Problem: A3-flavored. Many CHANGELOG fixes are "user reports X failed
  because env.json was malformed / wrong key / missing." `doctor` is brand
  new (v1.6.0) and currently only does presence checks, not connectivity
  or validity.
- Refs: `scripts/setup_dependencies.py:46-53` silently returns `{}` on bad
  JSON. CHANGELOG v1.5.2 (author field undefined → share_card auto-skipped);
  v1.5.6 ("Out of scope" because cookies missing).

### P1 — solid wins, medium term

| # | Title | Effort | Notes |
|---|-------|--------|-------|
| **B6** | Plugin-layout smoke test in CI | S–M | Prevents v1.6.2-class drift |
| **B7** | Multi-provider image abstraction | M | Enables English-language output (D2) |
| **B8** | Verify-claims expanded scope (flag validation) | M | Start with 5–10 high-frequency tools |
| **B9** | Tests for `evidence.py` / `bump_version.py` / `utils.py` | S | Three biggest no-test scripts |
| **B10** | Per-section tone override syntax | M | Tone spec v2 candidate |
| **B12** | Write reference entries for self-check rules 12–15 | S | Discovered in the v1.6.4 doc sweep; canonical reference has the gap flagged |
| **B13** | Auto-prune `MODEL_FALLBACK_CHAIN` by available API keys | S | Discovered while documenting the Minimax default on 2026-05-20; cuts a wasted attempt for single-key users |

**B6. Plugin-layout smoke test in CI**
GitHub workflow that does `bash install.sh --no-interactive`, then runs each
`commands/**/*.md` definition through a smoke check (validates frontmatter +
that referenced scripts exist). Would have caught v1.6.2 and v1.3.4.
- Refs: `.github/workflows/tag-release.yml` only tags; no install-and-smoke
  step. v1.6.2 commit `8e32ba2`.
- Effort: probably ≤30 LOC headless install path in `install.sh`.

**B7. Multi-provider image abstraction** *(strategic enabler — see D2)*
Factor Minimax + Gemini calls behind an `ImageProvider` protocol with a
registry. Add OpenAI gpt-image-1 / Stable Diffusion / DALL-E 3 / Flux as
opt-in providers. Same fallback-chain semantics.
- Refs: `scripts/generate_and_upload_images.py:351-360` hardcodes
  `MODEL_FALLBACK_CHAIN`; lines 510–520 are Minimax-specific API-key
  resolution. Today the pipeline is hard-tied to Minimax (`:711`
  `_generate_minimax_image`) + Gemini (`:817`).
- Risk: medium — touches the hottest script in the codebase.

**B8. Verify-claims expanded scope — flag validation**
Today `scripts/verify_claims.py` only checks `command -v TOOL`. Step up
to: for tools listed in a known schema (`uv` / `kubectl` / `docker`), parse
`--help` and warn on unknown flags.
- Refs: `scripts/verify_claims.py:17-19` calls this out as future
  enhancement; `skills/verify-claims/SKILL.md:40-45` lists 4 deferred items.
- Risk: scope creep — start with 5–10 high-frequency tools.

**B9. Test coverage for `evidence.py`, `bump_version.py`, `utils.py`**
- `evidence.py` (356 LOC, materials.md parsing)
- `utils.py` (317 LOC, `PlaceholderManager` + `SmartDirectoryMatcher`)
- `bump_version.py` (254 LOC, release tooling)

All three have no matching `tests/test_*.py`. `SmartDirectoryMatcher` is
the publish-skill auto-placement engine — silently picking the wrong KB
folder is the kind of bug that won't get noticed for releases.

**B10. Per-section tone override syntax**
`<!-- tone:casual -->...<!-- /tone -->` regions in articles, recognized by
`lint_article.py` + `review_selfcheck.py`.
- Refs: `docs/superpowers/specs/2026-05-07-tone-system-design.md:474`
  explicitly lists this as "v2 candidate." Spec shipped in v1.5.0; authors
  hitting the limit now.

**B12. Reference entries for self-check rules 12–15** *(doc debt — discovered in v1.6.4)*
`scripts/review_selfcheck.py` implements 17 active rules
(`check_rule_1` … `check_rule_17`), but `references/self-check-rules.md`
only carries prose entries for rules 1–11, 16, 17, plus the 7b
degradation-aware variant. Rules 12–15 work in code but the canonical
reference has no description — `references/self-check-rules.md`'s
preamble (post-v1.6.4) flags this and points readers to the docstrings
as the interim source.

- Refs: `scripts/review_selfcheck.py` — `check_rule_12` (line 691, AI-style
  summary detection), `check_rule_13` (line 713, code-block language tags),
  `check_rule_14` (line 754, ASCII diagrams in code blocks),
  `check_rule_15` (line 795, orphan PROMPT comments).
  `references/self-check-rules.md:1-13` (preamble flagging the gap).
- Effort: S — read each docstring + body, write a prose entry in the
  canonical reference matching the format used for rules 1–11 (one
  function/regex per rule, plus the "Who enforces what" table row).
- Risk: zero — pure documentation of existing behavior.
- Why it matters: closes the loop on the v1.6.4 sweep, removes the
  preamble's apologetic "consult the docstrings" pointer.

**B13. Auto-prune `MODEL_FALLBACK_CHAIN` by available API keys** *(discovered while answering "default is Minimax?" on 2026-05-20)*
Today the fallback chain is consumed verbatim regardless of which keys
are configured. A user with only `GEMINI_API_KEY` (no
`MINIMAX_API_KEY`) still sees `minimax-image-01` tried first, fail
immediately, then fall back to Gemini — a wasted API attempt **per
image**. Across a batch of N placeholders that is N wasted Minimax
calls, each adding latency and noise to the run.

- Fix: introduce `config.available_models(env, environ) -> list[str]`
  that filters `MODEL_FALLBACK_CHAIN` by key presence (Minimax models
  require `minimax_api_key` or `MINIMAX_API_KEY`; Gemini models
  require `gemini_api_key` or `GEMINI_API_KEY`). Both consumers route
  through it.
- Refs: `scripts/config.py:307-312` (the chain); `scripts/generate_and_upload_images.py:864`
  (`model_chain = [model] + [m for m in MODEL_FALLBACK_CHAIN if m != model]` — add the filter);
  `scripts/nanobanana.py:308` (`chain = MODEL_FALLBACK_CHAIN.copy()` — same).
- Effort: S, ~1 h. Risk: zero — pure pruning; an explicit user-selected
  model still takes priority. Edge case: filtered chain empty → fail
  fast with "no API keys configured for any image provider" instead of
  the current opaque exhaust-then-error.
- Why it matters: removes the "expected failure" attempt on every image
  generation for single-key users (which is the common new-user state
  since v1.6.0 made Minimax the headline default).

### P2 — bigger investments

**B11. v2 tone-threshold recalibration from collected data** *(assumes data exists)*
The tone system writes to `~/.cache/article-craft/tone-calibration.jsonl`.
Spec target was 20 articles before re-tuning. If 20+ articles have been
written, this becomes a stats analysis + threshold change.
- Refs: spec at `docs/superpowers/specs/2026-05-07-tone-system-design.md:437-445`.

---

## C. Quick wins — each < 2 hours

**C1. README skill-count drift**
`README.md:3` says "12 composable skills"; the table at `README.md:42`
lists 13 rows; `share_card` is effectively a 14th. Pick one number, fix
both places.

**C2. README "Standalone Commands" missing entries**
`README.md:178-188` lists 8 of the 13 skills. Missing: `requirements`,
`verify`, `evidence`, `series`, `publish`. Add them.

**C3. INSTALL.md skill count + wrong command names**
- `INSTALL.md:128` says "11 个 Skill 模块" but lists fewer in the tree
  (`evidence`, `verify-claims` missing; `series` briefly at line 140).
- `INSTALL.md:178` lists commands as `/article-write`, `/article-images` —
  these do not exist. Correct names are `/article-craft:write` etc.

> Also worth bundling into the C-batch: audit whether other sub-commands
> should be moved from `commands/article-craft/` to `commands/` top-level
> for clean `/article-craft:<name>` invocation (doctor was just moved
> there in v1.6.2). Today the entire `commands/article-craft/` subdir
> resolves as the nested `/article-craft:article-craft:<name>`, which is
> what the README/CLAUDE.md documentation already (incorrectly) implies
> is the user-facing name. Whether to flatten the rest is a deliberate
> convention decision; flag it now and decide before any new sub-command
> ships.

---

## D. Strategic forks

### D1. Cookie-gated UGC platforms as a *category* (extends B1)

Adding cookie support is the gate that unlocks: Twitter timeline screenshots,
Reddit private subs, X paid-tier threads, 知乎 paid columns, Substack paid
newsletters, dev.to drafts. Each of those is a Style H source today.

**Case for**: Style H is the most distinctive thing this plugin does —
`references/writing-styles.md` defines 公众号-style "爆料" articles, and the
entire evidence pipeline (v1.4.0 through v1.4.16, eleven releases) was built
around WeChat sourcing. Extending the harvestable surface continues the same
product bet.

**Risk**: anti-bot escalation race; account-suspension risk for users who
give bot credentials.

### D2. English-language output target (extends B7)

The plugin's writing rules, style guide, lint rewrites, and tone calibration
are all CJK-centric:
- `scripts/lint_article.py:152` counts Chinese chars only
- `references/writing-styles.md:56` references "中文数字编号"
- word-count target is in Chinese characters (`skills/write/SKILL.md:679`)

An English fork would need a parallel `references/writing-styles-en.md`,
English lint patterns, English tone-rewrite dictionary, English word-count
semantics, and an image provider that isn't Minimax-only (B7).

**Case for**: the technical architecture (skills, scripts, state file, KB
placement) is provably language-agnostic — only the text-level rules are
not. Multi-language is the natural strategic broadening once the v1.6.x
architecture stabilizes.

### D3. "Article-craft Lite" as a single-file plugin

Install footprint today: Playwright browsers (~200 MB), PicGo via npm,
Minimax API key, optional Gemini key, optional yt-dlp, optional NotebookLM
CLI. The install bar is high. A "Lite" variant with no Playwright
(image-gen only, no screenshots) + no PicGo (S3-only or local-only mode)
would be a 10-min install vs the current 30-min install.

**Case for**: lowers DX friction for "I just want to write a draft" users —
exactly `--draft` mode today, but those users still have to install
everything to *start*. The Lite variant could ship as a separate
`article-craft-lite` plugin in the marketplace.

---

## File references

| File | Purpose |
|------|---------|
| `CHANGELOG.md` | release history (mining input) |
| `CLAUDE.md` | architecture + design debt section |
| `skills/orchestrator/SKILL.md` | pipeline definition (stage-by-stage audit) |
| `scripts/screenshot_tool.py` | 2,151 LOC — `HOST_MAIN_SELECTORS:267`, `REHOST_CDN_WHITELIST:1042`, `upload_to_cdn:977` |
| `scripts/generate_and_upload_images.py` | 3,000 LOC — `MODEL_FALLBACK_CHAIN:351`, Minimax `:708`, Gemini `:817` |
| `scripts/setup_dependencies.py` | silent env.json error at `:46-53` |
| `scripts/verify_claims.py:17-19` | deferred-scope comment |
| `skills/verify-claims/SKILL.md:40-45` | 4 deferred enhancements |
| `docs/superpowers/specs/2026-05-07-tone-system-design.md:472-477` | 4 tone v2 candidates |
| `README.md:3,42` | skill-count drift |
| `INSTALL.md:128,178` | skill count + wrong command names |
