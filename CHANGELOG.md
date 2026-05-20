# Changelog

## [1.6.9] - 2026-05-20 — auto-prune fallback chain by available API keys (B13)

### Fix — no more wasted Minimax attempts for Gemini-only users

Before: a user with only `GEMINI_API_KEY` (the default new-user state
since v1.6.0 made Minimax the headline default) saw the fallback chain
try `minimax-image-01` first **per image**, fail with an auth error,
then fall through to Gemini. Across a batch of N placeholders that was
N wasted Minimax attempts plus the latency / log-noise overhead.

After: `config.filter_chain_by_available_keys(chain)` prunes models
whose provider key isn't set. Minimax models need
`minimax_api_key` (env.json) or `MINIMAX_API_KEY` (env var); Gemini
models need `gemini_api_key` or `GEMINI_API_KEY`. Both call sites
(`generate_and_upload_images.py:864`, `nanobanana.py:308`) filter
through the helper after building the chain.

### Behaviour notes

- **Filtered chain empty** → callers raise `RuntimeError` with a clear
  fix hint instead of letting an empty loop silently succeed-zero or
  emit a confusing "all attempts exhausted" error.
- **Explicit `--model` dropped** → warning printed showing what fell
  back to. (User selected a model whose provider isn't configured —
  surface the override rather than silently overriding their choice.)
- **Unknown provider prefix** → passes through (forward-compat: future
  Qiniu / DALL-E / Flux entries get their own key check when wired up,
  not arbitrarily dropped by this filter).
- **Empty-string env.json key** treated as missing (matches the
  existing API-key-check semantics in `doctor.py`).

### Tests

10 new tests (`tests/test_filter_chain.py`) cover: both keys, only
Gemini (the headline scenario), only Minimax, neither, env.json-only,
env-var-only, chain order preservation, unknown-prefix pass-through,
empty-string-key handling, empty input chain. **279 total tests pass**
(was 269).

### Closes

- B13 from `docs/research/2026-05-20-feature-candidates.md` —
  originally surfaced as a side observation while documenting the
  Minimax default for a user question.

## [1.6.8] - 2026-05-20 — shared PicGo parser + Uploader protocol (B2)

### Refactor — canonical PicGo output parser in `scripts/uploaders.py`

Closes the v1.5.2-pattern fragility: previously
`screenshot_tool.upload_to_cdn` and
`generate_and_upload_images.upload_to_picgo` each had their own
duplicated line-scan + JSON-fallback heuristic for extracting a URL from
PicGo CLI output. v1.5.2 fixed one parser (the multi-line
`[PicGo INFO]` log case that silently broke screenshot uploads); the
other was a parallel implementation with subtly different defensiveness
that would have needed its own fix on the next regression.

Now both call sites delegate to a single
`scripts/uploaders.parse_picgo_output(stdout)`:

- Strategy 1: line scan for `http://` or `https://` (the real-world
  PicGo output shape — multi-line log + final URL line)
- Strategy 2: JSON fallback (`{"url": ...}` or `[{"url": ...}]`) for
  forward-compat with potential PicGo format changes
- Returns `None` if neither finds a URL — callers decide whether to
  raise (image-gen, fail-fast) or fall back to local path (screenshot,
  lenient)

Inline `line.startswith("http://")` parsing removed from both
`screenshot_tool.py` and `generate_and_upload_images.py`. Both files
now `from uploaders import parse_picgo_output`.

### New — `Uploader` Protocol (future extension point)

`uploaders.Uploader` is a `@runtime_checkable` Protocol with a single
`upload(local_path: str) -> str` method. Current uploader functions
(`upload_to_picgo`, `upload_to_s3`, `upload_to_cdn`) are intentionally
**not** refactored to instances yet — their callers have very different
error contracts (image-gen raises, screenshot returns local path) and
forcing them into one shape would force converting the retry-wrapped
PicGo flow and the lenient screenshot fallback, expanding scope beyond
what B2 demands. The protocol exists so future Qiniu / imgbb / SMMS
backends slot in cleanly via a `get_uploader()` factory rather than
adding more branches to `upload_image`.

### Tests

16 new tests (`tests/test_uploaders.py`):

- Parser behavior: real-world multi-line log, bare URL, http vs https,
  URL anywhere in lines
- JSON fallbacks: dict / list shapes, line-URL beats JSON when both
  present
- Failure modes: empty string, no URL anywhere, invalid JSON, dict
  without `url`, empty list, non-dict list head, non-string `url` value
- Uploader Protocol: `isinstance()` accepts correct shape, rejects wrong

All existing upload tests (`tests/test_screenshot_upload.py`,
`tests/test_share_card_upload.py`, `tests/test_images_cli.py`) pass
unchanged — the refactor preserves the public contracts.

**269 total tests pass** (was 253).

### Closes

- B2 from `docs/research/2026-05-20-feature-candidates.md`
- Pattern A1 (silent stub / stdout-pollution) from the same doc

## [1.6.7] - 2026-05-20 — share-card standalone skill (B4)

### New — `/article-craft:share-card` standalone skill

`scripts/share_card.py` (553 LOC, 10 platform presets, 7 color schemes)
was previously only reachable from the orchestrator pipeline's Step
3.4.5 — there was no way to regenerate cards for a published article
without rerunning the whole pipeline.

Promoted to a first-class skill at `skills/share-card/SKILL.md` with
top-level `commands/share-card.md` (single-prefix `/article-craft:share-card`
per the v1.6.3 convention). Same engine, just a standalone entry point
for post-publish card regeneration, brand-refresh batches, and color
tweaks without article-level changes.

The orchestrator still calls the same script directly — no behavior
change for the integrated pipeline.

### Skill count

13 → **14** child skills under `skills/` (orchestrator unchanged at 1).
README, INSTALL, scripts/README all updated.

## [1.6.6] - 2026-05-20 — cookie injection for headless screenshots (B1)

### New — Playwright cookie loading in `screenshot_tool`

Closes the v1.5.6 "Out of scope" item: login-walled platforms (HN-HTTPS,
Reddit, 知乎, 微博, 小红书 …) whose selectors landed in v1.5.5 now work
end-to-end from headless runs once a cookies file is configured.

The integration is deliberately format-agnostic — we consume
**Playwright-format cookies JSON** (the shape `BrowserContext.cookies()`
emits), so any extractor that produces it works: gstack
`setup-browser-cookies` skill, Playwright's own dump, browser extensions
like EditThisCookie, or hand-written.

**Configuration** (priority order):

1. CLI `--cookies PATH` (highest) or `--no-cookies` (disable)
2. env.json `browser_cookies_path`
3. Default `~/.cache/article-craft/cookies.json` (only if file exists —
   no behavior change for unconfigured installs)

**Format**: top-level JSON list, or `{"cookies": [...]}` wrapper. Each
entry needs `name` + `value` + (`url` or `domain`). Malformed entries
are skipped individually rather than failing the whole load.

**Safety**: Playwright filters cookies by domain at send time, so
loading the full jar for any screenshot is safe — only matching cookies
are sent. A bad cookies file logs a warning and screenshot continues
without cookies (not a fatal error).

### New — `--cookies` / `--no-cookies` CLI flags

Both `screenshot_tool.py screenshot` and `screenshot_tool.py batch`
accept the flags. ENV.md has a new "截图 cookie 注入" section with
format example and provenance notes. `skills/screenshot/SKILL.md` —
the "需要登录的页面" row in the avoidance table flipped from "跳过" to
the actual integration path.

### Tests

14 new tests (`tests/test_screenshot_cookies.py`) cover the three
helpers: `_resolve_cookies_path` (5 cases — disabled / explicit /
config / default-present / default-missing), `_load_cookies` (6 cases
— missing / invalid JSON / list / wrapped / wrong-shape / partial
skip), `_apply_cookies` (3 cases — empty / success / playwright error
swallowed). 253 total tests pass (was 239).

### Closes

- B1 from `docs/research/2026-05-20-feature-candidates.md`
- v1.5.6 CHANGELOG "Out of scope" deferral

## [1.6.5] - 2026-05-20 — doctor extended checks (B5)

### New — `env_json` check

`scripts/setup_dependencies.py` previously parsed `~/.claude/env.json`
through `_load_env_json()` which swallows `JSONDecodeError` and returns
`{}`. A single typo in env.json silently degraded every downstream
check (API keys, S3, PicGo override) without any user-visible signal.
The new `env_json` check surfaces this explicitly:

- **PASS** — file absent (optional) or parses cleanly
- **WARN** — file present but empty
- **BLOCK** — file present but invalid JSON (with line/col + fix hint)

### New — `plugin_root` check

Verifies `CLAUDE_PLUGIN_ROOT` (when set) points to an existing directory.
A typo or stale checkout silently broke scripts that join paths onto it.

- **PASS** — env var resolves to a real dir
- **WARN** — env var not set (script-relative fallback works for direct
  shell runs; Claude Code sets it automatically)
- **BLOCK** — env var points to a non-existent path

### New — `--network` flag for network reachability

`doctor.py check --network` adds an optional Minimax / Gemini host
reachability probe (HEAD with 3 s timeout each). Only probes hosts
whose API key is actually configured. Default `check` stays fast
(~1 s) — the network flag is opt-in to avoid blocking the orchestrator
preflight on a slow corporate proxy.

Default `doctor check` now runs **11** checks (was 9); with `--network`
it runs 12.

### Tests

10 new tests added (`tests/test_doctor.py`: env_json valid/invalid/
empty/missing, plugin_root unset/missing/valid, network excluded-by-
default / runs-with-flag / warns-no-keys / warns-unreachable). 239
total tests pass (was 228).

## [1.6.4] - 2026-05-20 — post-v1.6.3 doc sweep

### Fix — rule-count drift across docs (11 / 12 / 17 disagreement)

`scripts/review_selfcheck.py` implements **17** active rules
(`check_rule_1` through `check_rule_17`, dispatched at line 1076) — but
the canonical reference said "11 rules" in its preamble, `CLAUDE.md`
said "11", and `README.md` said "12". Synced all three to 17.

`references/self-check-rules.md` preamble updated to be honest about
the doc gap: full reference entries exist for rules 1–11, 16, 17, plus
the 7b degradation-aware variant; prose entries for rules 12–15 are
doc-debt and the preamble now points readers at the `check_rule_N`
docstrings in `scripts/review_selfcheck.py` until those entries land.

### Docs — `scripts/README.md` expanded

Was listing 6 of 17 `.py` files. Updated to include all 17, organized
by purpose (healthcheck, image generation, screenshot, publish, series,
lint/review, release tooling). Adds a "run the healthcheck" example
using `doctor.py`.

228 tests pass — markdown only, no Python changed.

## [1.6.3] - 2026-05-20 — flatten command directory + sync docs

### Fix — every sub-command now resolves as `/article-craft:<name>` (single prefix)

v1.6.2 fixed only the `doctor` command. The 13 other sub-commands
(`write`, `publish`, `series`, `review`, `lint`, `images`, `screenshot`,
`requirements`, `verify`, `verify-claims`, `evidence`, `youtube`,
`upgrade`) still sat under `commands/article-craft/` and resolved as the
nested `/article-craft:article-craft:<name>` for marketplace installs —
which contradicted every doc, README, and CLAUDE.md mention of the
intended single-prefix form.

Moved all 13 to the top level of `commands/`. The repo convention now
matches what users (and the docs) have always expected: one command file
per skill at `commands/<name>.md`, resolving as `/article-craft:<name>`.
`commands/doctor.md` (the v1.6.2 fix) and the new placement are now
consistent.

### Docs — synced to match reality

- `INSTALL.md` skill count corrected (11 → 13), tree updated to include
  `evidence/` and `verify-claims/`, scripts tree updated to include the
  v1.6.0 additions (`doctor.py`, `publish_plan.py`, `series_state.py`,
  `share_card.py`, etc.). The "单独使用" example block — which previously
  listed nonexistent commands like `/article-write` — now shows the real
  14 commands.
- `README.md` "Standalone Commands" block expanded from 8 to 14 entries
  (was missing `requirements`, `verify`, `evidence`, `series`, `publish`,
  `doctor`, `upgrade`). The "series" Workflow Modes row fixed
  (`/article-series` → `/article-craft:series`).
- `CLAUDE.md` "New skills" convention rewritten: new commands go at
  `commands/<name>.md` top-level (not `commands/article-craft/<name>.md`)
  with the why-it-matters explanation inline.
- `commands/doctor.md` self-explanation simplified (it no longer needs
  to call out its location as a special case — every command does this
  now).

228 tests pass — no Python code changed, this release is markdown only.

## [1.6.2] - 2026-05-19 — fix /article-craft:doctor command name

### Fix — doctor command moved to `commands/doctor.md`

v1.6.1 shipped the command at `commands/article-craft/doctor.md`, which a
plugin install registers as the nested `/article-craft:article-craft:doctor`
(`/article-craft:doctor` returned "Unknown command"). Moved the file to the
top level of `commands/` so it resolves as the intended `/article-craft:doctor`.

## [1.6.1] - 2026-05-19 — /article-craft:doctor command

### New — `/article-craft:doctor` slash command

`commands/article-craft/doctor.md` — a thin command wrapping
`scripts/doctor.py check`, so the runtime healthcheck (the same preflight
the orchestrator runs as its Step 0) has a standalone slash entry point.
Supports `--json`. No matching skill directory — `doctor.py` is a script,
not a skill — mirroring how `commands/article-craft/upgrade.md` wraps an
orchestrator mode.

## [1.6.0] - 2026-05-19 — doctor preflight, publish/series state scripts, pipeline hardening

The post-1.5.6 batch: three new deterministic helper scripts, broad
hardening of the image / screenshot / install paths, and a round of
review-driven fixes folded in.

### New — `scripts/doctor.py` runtime healthcheck

Unified preflight CLI (`doctor.py check [--json]`) that delegates to
`setup_dependencies.run_all_checks`, summarizes pass/warn/block counts,
and maps them to exit codes 0/1/2. Backs the orchestrator's "Step 0:
Preflight Dependency Check".

### New — `scripts/series_state.py` series state machine

`status` / `next` / `mark-published` / `validate` subcommands. The
`series` skill's modes 2/3/7 now delegate state handling here instead
of carrying their own ad-hoc logic. `next` returns full prev/next
navigation context. A documented `validate` mode (模式 7) was added.

### New — `scripts/publish_plan.py` publish planner

Single command with a `--dry-run` preview: KB auto-placement (via
`SmartDirectoryMatcher`), SHA-256 collision detection with timestamped
rename, and Style H sidecar (`_evidence.json` / `_harvest_menu.md`)
collection. The `publish` skill's Steps 1–3 now delegate to it.

### Config — KB directory names are no longer hardcoded

`config.kb_category_root()` / `config.kb_uncategorized_dir()` replace
the literal `02-技术` / `未分类` strings, overridable via env.json so a
fork with a differently-named KB tree works unchanged. `ENV.md` and
`env.example.json` updated.

### Fixes — review-driven

- `publish_plan.py`: planning is now side-effect-free — a `--dry-run`
  no longer creates directories; `mkdir` happens only on the executed
  run. The earlier `plan` / `apply` subcommand split (where `apply`
  silently re-computed the plan) was collapsed into one command so the
  preview and the executed run share a single code path.
- `series_state.py`: `mark-published` now fails loudly (exit 1,
  `error_code: series_row_not_found`) on an unknown `--index` instead
  of silently rewriting nothing and reporting success.
- `series_state.py`: dropped the unused `slug` parameter from
  `_article_filename`.

### Docs

- Purged the last stale `content-reviewer` references (`INSTALL.md`,
  `README.md`, `write/style-guide.md`, `orchestrator/SKILL.md`). The
  `content-reviewer` script was superseded long ago — review is
  self-contained (`review_selfcheck.py` + inline 7-dim scoring) — but
  these textual mentions had lingered.

228 tests pass.

## [1.5.6] - 2026-05-08 — robustness fixes from v1.5.5 e2e testing

End-to-end testing v1.5.5 across 14 platforms surfaced two robustness
issues that the unit tests didn't catch.

### Fix — selector candidate height floor: 400 → 100

`capture_screenshot` rejected any `suggest_selector` candidate whose
bounding box was <400px tall. The threshold was originally meant to
filter out tiny nav icons, but it also discarded legitimately short
main-content containers:
  - arxiv `#abs` is ~375px — silently dropped, fell through to
    full-page (1280×wide × very long).
  - Single tweets, short Reddit threads, etc. — same fate.

Lowered to 100px (matches `MIN_CONTENT_HEIGHT_PX`). E2E confirmed:
arxiv now produces a clean 1021×375 element screenshot.

### Fix — element-timeout fallback to viewport

`el.screenshot()` raises `PlaywrightError` when the element matches
but isn't stable/visible — common on lazy-loaded SPAs. YouTube hit
this consistently: `#meta` matched but mounted later, screenshot
timed out after 15s, entire run failed.

Wrapped the call in try/except: on timeout, fall back to
`page.screenshot(full_page=False)` (viewport) plus a warning. User
gets a working screenshot tagged `selector_used: "X (timeout →
viewport)"` instead of the whole pipeline failing.

E2E confirmed: YouTube watch page now produces a 1280×800 viewport
shot with the warning surfaced.

### Out of scope

Hard-network-blocked / aggressive-anti-bot platforms (HN via HTTPS,
Reddit / 知乎 / 微博 / 小红书 from headless) still need cookie
support to work end-to-end — that's a much bigger fix involving
`setup-browser-cookies` integration and is intentionally deferred.

166/166 tests pass.

## [1.5.5] - 2026-05-08 — multi-platform main-content selectors

User report after v1.5.4: anchor + auto-suggest still only had useful
entries for GitHub. On X / 微博 / 小红书 / 知乎 / 微信公众号 /
Reddit / HN / YouTube / B 站, screenshots fell back to viewport
mode, anchor scope fell through to the generic markdown-body family
(nothing matched), then to body-global (sidebar/header noise).

### Refactor

Pull all platform-specific selector knowledge into a single
`HOST_MAIN_SELECTORS` dict consumed by both `suggest_selector()`
and `capture_screenshot`'s anchor scope. Adding a new platform is
one entry; both code paths benefit immediately.

### New built-in coverage

| Category | Hosts |
|---|---|
| Code/dev | github.com, stackoverflow.com, npmjs.com |
| Western UGC | x.com + twitter.com, reddit.com, news.ycombinator.com |
| Chinese UGC | weibo.com, xiaohongshu.com + xhslink.com, zhihu.com, mp.weixin.qq.com |
| Video | youtube.com, bilibili.com |
| Long-form | medium.com, arxiv.org |
| Docs (generic) | `.markdown-body` / `.docs-content` / `.documentation` / `.main-content` |

`www.` prefix is stripped before matching; host substring match means
`x.com` covers `m.x.com` too.

### Configuration

env.json `screenshot_main_content_selectors` lets users add private
platforms or override built-ins when sites redesign:

```json
"screenshot_main_content_selectors": {
  "myblog.com": [".post-body"],
  "weibo.com":  [".New_Feed_Content_Container"]
}
```

User entries win over built-ins via host substring match.

### Tests

`tests/test_screenshot_crop.py` adds 22 cases: 14 per-platform
recognition tests (parameterized), www. stripping, unknown-host
empty-list, user-override-wins-over-builtin, user-override-for-new-host,
suggest_selector reading host map for video/zhihu, and the v1.5.4
guardrail (`main`/`article` must NOT be in GENERIC_CONTENT_SELECTORS).

166/166 tests pass.

## [1.5.4] - 2026-05-08 — anchor scope fix (followup to v1.5.3)

v1.5.3 added ANCHOR keyword scrolling but searched the whole
`document.body`. On GitHub repo pages the DOM order is header →
file tree → README → sidebar (Topics / About / Releases). If the
keyword existed anywhere outside the README (sidebar tag, file
name fragment, topic chip), tree-walker hit it first and scrolled
there. Screenshots came out showing file lists / commit history
instead of the README section the article was discussing.

User-visible repro on github.com/vectorize-io/hindsight:
  - `ANCHOR:TEMPR`        → README has no "TEMPR"; v1.5.3 scrolled to
                            commit list anyway. Now: doesn't scroll,
                            falls back to README top.
  - `ANCHOR:LongMemEval`  → README has "LongMemEval"; v1.5.3 scrolled
                            to a sidebar/file match. Now: scrolls to
                            the README's Memory Performance section.
  - `ANCHOR:memory bank`  → same story, now correct.

Fix: scope the tree walker to a prioritized list of content
containers: explicit selector → `article#readme` →
`article.markdown-body` → `.markdown-body` → `.docs-content` etc.
Bare `<main>` and bare `<article>` are intentionally excluded
because GitHub wraps both file tree and README in them.

If the keyword exists on the page but only outside the content
containers, return a `no_scroll` hit so we can warn instead of
silently misleading. If the keyword isn't on the page at all,
keep the default screenshot position.

144/144 tests still pass.

## [1.5.3] - 2026-05-08 — screenshot framing: anchor keywords + 900px cap

User report after the v1.5.2 verification run: screenshots came out at
1400px tall and didn't reflect what the surrounding article paragraph
was actually discussing. Two-part fix.

### Fix — Default screenshot height capped at 900px

`screenshot_tool.upload_to_cdn` already worked from v1.5.2, but
`capture_screenshot` had no height cap on element screenshots — a
GitHub README selector matched the entire 1400px+ `article#readme`
container and that's what got returned. `--max-height` defaulted to
`0` (no cap), so the only thing keeping screenshots reasonable was
manual user intervention.

`--max-height` now defaults to **900px** (≈ one viewport). The
`crop_to_max_height` call moved from `batch_capture`'s outer loop
into `capture_screenshot` itself, so CLI / batch / programmatic
callers all benefit equally. Verified: same GitHub repo URL that
produced 756×1400 yesterday now produces 445×900.

`--max-height 0` still disables the cap if needed.

### Feat — `ANCHOR:` placeholder syntax wires up keyword scrolling

The `article_keywords` parameter on `capture_screenshot` had been
declared in the signature for many releases but never actually used
inside the function — the local variable was set then ignored. Now
it drives a `page.evaluate` walk that scrolls the page to the first
text node containing any of the keywords (skipping elements <50px
tall so we don't anchor on sidebar nav links), then takes a viewport
screenshot at that scroll position. The result: the image shows the
part of the page that's relevant to the surrounding article
paragraph, not the page header.

New placeholder syntax (documented in both `skills/screenshot/SKILL.md`
and `skills/write/SKILL.md`):

```
<!-- SCREENSHOT: URL ANCHOR:kw1,kw2 -->     # scroll to first kw
<!-- SCREENSHOT: URL FOLD -->               # ≤ viewport height (800)
<!-- SCREENSHOT: URL MAX_HEIGHT:1200 -->    # custom height cap
```

CLI gains `--fold` (== `--max-height 800`). `--keywords` already
existed; now it actually does something.

The `write` skill is told to default-include `ANCHOR:` when emitting
a SCREENSHOT placeholder — at write time the skill already knows what
each section is about, so picking 1-3 keywords from the surrounding
paragraph is essentially free.

### E2E verification (`https://github.com/vectorize-io/hindsight`)

| Mode | Output | What it proves |
|---|---|---|
| no flags | 445×900 | Default cap kicks in |
| `--keywords TEMPR` | 1280×800, `anchor_kw_used: "tempr"` | Scrolled to TEMPR section + screenshot is viewport-sized at that scroll |
| `--fold` | 642×800 | Viewport-only screenshot |

144/144 tests pass (+5 new in `tests/test_screenshot_crop.py`).

## [1.5.2] - 2026-05-08 — orchestrator pipeline fixes from real-world run

After a full `/article-craft:orchestrator` run on a real article
yesterday (3025-char Hindsight intro), four pain points surfaced.
This release closes all four:

### Fix — `screenshot_tool.upload_to_cdn()` parsed picgo wrong

`upload_to_cdn()` assumed picgo emitted JSON, but picgo's actual stdout
is multi-line `[PicGo INFO]` log lines + a final bare URL. The old
parser called `json.loads(stdout)` (always failed) then checked
`stdout.startswith("http")` on the multi-line blob (also always
failed) and returned the local path — so callers silently treated
every screenshot as "upload failed". During the Hindsight run, both
screenshots had to be uploaded by hand and the CDN URL pasted into
the article manually.

The matching parser in `generate_and_upload_images.upload_to_picgo()`
was already doing this right (line-by-line scan, JSON fallback).
Aligned `upload_to_cdn` to the same strategy. Also promoted
`import shutil` and `import subprocess` to the top of
`screenshot_tool.py` so the function is unit-testable.

Adds `tests/test_screenshot_upload.py` (6 cases): multiline log +
bare URL, JSON dict / list output, no URL → local path, no picgo on
PATH, nonzero exit.

### Fix — `review_selfcheck.py` couldn't be invoked as a direct script

`from scripts.config import ...` (package-style import) at the top
of the file required the repo root to be on `sys.path`, so
`python3 scripts/review_selfcheck.py article.md` always failed with
`ModuleNotFoundError: No module named 'scripts'`. The Usage docstring
explicitly advertised that invocation, and the review skill kept
working around it with `cd` + `python3 -m scripts.review_selfcheck`.

Now the file inserts its own directory into `sys.path` before the
import, so all three modes work:
1. `python3 scripts/review_selfcheck.py article.md`
2. `python3 -m scripts.review_selfcheck article.md`
3. `from scripts.review_selfcheck import check_rule_17` (pytest)

### Feat — `write` skill self-checks word count before save

The Hindsight run wrote ~2000 chars on first pass against a
3000-4000 target, then needed 5 rounds of orchestrator-driven
`Update` calls to expand. New **Step 5.5: Word Count Self-Check**
in `skills/write/SKILL.md` does the count + targeted expansion
inside the write skill, with explicit guidance against padding via
restated transitions. Loops up to 2 rounds; if still under min,
saves and surfaces the shortfall in the handoff output instead of
spinning forever.

### Feat — frontmatter `author` field, resolved at write time

`share_card` auto-skipped on the Hindsight article with "missing:
author" because `write`'s frontmatter template literally never
emitted the field. New `config.author_name()` resolves
`env.json user_name > git config user.name > "Anonymous"`. The
write template now includes `author:` and shows how to fill it
inline. `env.example.json` and `ENV.md` document the new
`user_name` env field.

139/139 tests pass (+7 new: 6 screenshot, 1 author).

## [1.5.1] - 2026-05-08 — hardcoding audit + publish preflight

### Refactor — Eliminate hardcoded paths and brand strings

Project-wide audit (12 files) to remove hardcoded paths, model lists,
personal CDN domains, and `/tmp` literals. Behavior is unchanged on a
default install; the audit only opens up customization seams.

**`scripts/config.py` — four new APIs:**

- `cache_dir() -> Path` — single source for `~/.cache/article-craft/`,
  honoring `ARTICLE_CRAFT_CACHE_DIR`. `screenshot_tool.py`,
  `write_verify_cache.py`, and `review_selfcheck.py` now all flow through
  it (previously only the last one did).
- `TEXT_MODEL` — separates the prompt-expansion text model used by
  `nanobanana.py --enhance` (`gemini-2.0-flash` default) from the
  image-only `MODEL_FALLBACK_CHAIN`. Override via env.json
  `gemini_text_model`.
- `VERIFY_CDN_WHITELIST` — the CDN allowlist that used to live as a
  hardcoded `grep -v` filter inside `skills/write/SKILL.md`. Default
  excludes per-author personal domains. Override via env.json
  `verify_cdn_whitelist`.
- `share_card_logo()` — resolves card logo text from env.json >
  `.claude-plugin/plugin.json` `name` > `"article-craft"`. Forks can
  re-brand without source edits.

**Configuration template:** new `env.example.json` at repo root,
referenced by `ENV.md` (the template `install.sh` had been copying from
`~/.claude/env.example.json` was never in this repo until now).

**DRY cleanup:**

- `nanobanana.py` and `generate_and_upload_images.py` no longer carry
  parallel copies of `MODEL_FALLBACK_CHAIN` — both import from
  `config`. Standalone `try/except ImportError` fallbacks are kept.
- `generate_and_upload_images.py` model-chain construction switched from
  the buggy `[user_model, gemini-3.1-flash, gemini-2.5-flash]` (which
  silently dropped `gemini-3-pro` whenever the user picked a non-pro
  default) to `[user_model] + canonical chain` with order preserved.

**Cross-platform `/tmp`:**

- Six `/tmp/...` literals migrated to `tempfile.gettempdir()`:
  `VerificationCache` default, `gemini_probe.jpg`, `verify-tmp.txt`,
  `utils.py` demo, plus the cache-dir helpers above. Same effective path
  on Linux, now portable to Windows.

**De-personalization:**

- `skills/write/SKILL.md`: example URL `file.costalong.com` → generic
  placeholder `your-cdn.example.com` with note about
  `verify_cdn_whitelist`. Coverage-warning shell snippet now reads the
  whitelist from `config.VERIFY_CDN_WHITELIST` instead of hardcoding it.
- `scripts/share_card.py`: card-footer logo HTML uses
  `share_card_logo()` instead of the literal `"article-craft"`.

**Stale comment fixes:** `config.py` references to a non-existent
`~/.article-craft.conf` corrected to `~/.claude/env.json`. The
`screenshot_tool.py` doc comment citing
`/tmp/article-craft-verify-cache.json` corrected to the actual
`~/.cache/article-craft/verify-cache.json` path.

**Tests:** 8 new `test_config.py` cases cover defaults + env-json
overrides for all four new APIs (`cache_dir`, `TEXT_MODEL`,
`VERIFY_CDN_WHITELIST`, `share_card_logo`). Total: 132/132 pass.

### Added — Pre-publish placeholder gate

Closes the "article published with unresolved `<!-- IMAGE/SCREENSHOT/PROMPT/HARVEST: -->`
placeholders" silent-failure mode. Caught during round4 e2e testing —
running image generation with `--no-upload` produced an article that the
script reported as "1 placeholder replaced" (only the screenshot got a
local path) while 4 IMAGE placeholders remained intact, but the publish
skill would happily move that half-baked file into the knowledge base.

**New CLI subcommand**: `pipeline_state.py check-publish-ready --article PATH`

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/pipeline_state.py check-publish-ready \
    --article /abs/path/article.md
```

Exit codes:
- `0` — clean (no `<!-- IMAGE/PROMPT/SCREENSHOT/HARVEST: -->` placeholders remain)
- `1` — unresolved placeholders detected (BLOCK publish)
- `2` — article path doesn't exist

Output: JSON on stdout for machine consumption, human-readable summary
on stderr listing per-kind placeholder counts and likely cause.

**Wiring**: `skills/publish/SKILL.md` adds Step 0 — runs the preflight
gate before any directory matching or file movement. Block-with-detail
on placeholder presence; never override.

### Tests

`tests/test_pipeline_state.py` adds `CheckPublishReadyTests` (6 tests):
- clean article returns 0 + ready=true
- IMAGE/PROMPT placeholder pair blocks with both counted
- SCREENSHOT placeholder blocks
- HARVEST placeholder (Style H) blocks
- multi-kind article reports each kind separately
- nonexistent article returns exit 2

Total suite: 128 passed (122 baseline + 6 new).

### Why this layer at publish, not earlier

The pipeline already has earlier checks (write Step 7 handoff, verify-claims
post-write) but those happen *before* image generation. The preflight gate
is the last line of defense — it runs *after* all generation/upload stages
and catches any silent failure (--no-upload, CDN error, manual edit drift)
right before the article enters the knowledge base. Cheap to run (single
regex scan of the article body) and fail-loud.

### Validated

- `python3 -m pytest tests/test_pipeline_state.py -v` → 12 passed
- Manual smoke test on round4-final.md (clean) → exit 0
- Manual smoke test on round4-test-run.md (--no-upload artifact) →
  exit 1, BLOCK with "IMAGE: 4, PROMPT: 4"

---

## [Unreleased] - 2026-05-08 (image variety, v1.4.19 dev)

### Added — Per-position image variation (Layer A + C)

Closes the "image style too monotone" feedback. Two compounding causes:

1. **Within-article**: `image-guide.md` locked all 4 design tokens (palette
   / preset / mood / background) so sibling images shared camera, composition
   and framing. Visually they looked like 4 stickers from the same sheet.
2. **Cross-article**: `STYLE_TO_VISUAL` mapped 80% of articles to 2-3 presets
   with default palettes (Style A → S1 → blue+teal) — article-after-article
   looked like one branded series.

**Layer A (rule rewrite)** — `skills/images/image-guide.md` § 风格一致性
规则 split into:

- **全篇必锁**: visual_style preset, color family, mood keywords, background
- **鼓励变化** (per image): camera angle, composition, subject framing,
  visual density

Plus new "镜头/构图轮转表" documenting which directives the script injects
per image position (cover → establishing wide / centered; img 2 →
three-quarter perspective / rule-of-thirds; etc.).

**Layer C (script injection)** — `scripts/generate_and_upload_images.py`:

- `CAMERA_ROTATION` (6-tuple) + `COMPOSITION_ROTATION` (6-tuple)
- `vary_prompt_for_position(base_prompt, image_index, total)` — appends
  `Camera: ...` + `Composition: ...` based on image position
- `_CAMERA_KEYWORDS_RE` / `_COMPOSITION_KEYWORDS_RE` — detect author
  override per axis and skip injection (author wins)
- `vary_prompts: bool = True` on `generate_and_upload_batch` and
  `generate_and_upload_parallel`
- `--no-vary-prompts` CLI flag for opt-out

`skills/write/SKILL.md` updated to tell writers NOT to manually add
Camera/Composition (script handles it).

**Verified end-to-end (2026-05-08)**: 6 images with the same base PROMPT
plus varying Camera/Composition directives → Gemini produced visibly
different framings (vertical stack / wide w/ breathing / horizontal flow
/ detail dashboard / stair-step / 3D isometric) while keeping locked
palette + preset + background uniform across all 6.

**Tests**: `tests/test_image_variation.py` (11 tests) — index rotation,
locked-prefix preservation, author-override skip, partial override,
structural invariants. Total suite: 118 passed.

### Why not Layer B / D yet

Layer B (expand from 7 → 12-15 visual presets) and Layer D (cross-article
style rotation cache) are **deferred**. A + C cover within-article
monotony — the higher-impact complaint. Cross-article variety needs more
presets first (B), and shuffling needs presets to shuffle from. Decide
after 5-10 real articles run through A + C.

### Validated

- `python3 -m pytest tests/ -q` → 118 passed (107 baseline + 11 new)
- 6-image visual A/B confirmed Gemini responds to directives
- `--no-vary-prompts` opt-out path verified

---

## [Unreleased] - 2026-05-08 (calibration v1.1)

### Changed — Rule 17 threshold calibration after 4-article pilot

Drove a 4-article pilot (1 Style A neutral PostgreSQL tutorial / 1 Style D
casual Bun-vs-Node review / 1 Style G opinionated Cursor hot take / 1
deliberately-AI-flavor LangChain article) and discovered two real-world
miscalibrations in v1's starting thresholds:

- **`TONE_THRESHOLDS["neutral"]["max_summary_phrases"]: 5 → 3`.** v1's
  ceiling of 5 let the deliberately-AI-flavor article through with only 2
  warnings (passed under "warnings don't block" semantics). v1.1's ceiling
  of 3 catches that article with a clearer signal. Unit tests updated:
  `test_neutral_allows_3_summary_phrases` (was `test_neutral_allows_5_*`)
  + new regression test `test_neutral_fails_on_4_summary_phrases_v1_1_regression`.

- **`TONE_THRESHOLDS["casual"]["first_person_per_800w"]: 4 → 3`.** Real
  casual blogs in the pilot hovered at first-person density 2–3 per 800
  chars. v1's threshold of 4 was rejecting genuinely casual writing that
  read fine. Lowered to 3 to match the observed distribution.

### Fixed — Lint replacement preserves trailing punctuation

Casual + opinionated tier lexical rewrites (`在某种意义上`, `可以看到`,
`本质上`, `值得注意的是`, `综上`, `显然`) used regex `[，,]?` to consume
the optional trailing comma but the replacement string didn't put it
back. Result: `"值得注意的是，LangChain..."` → `"这地方注意LangChain..."`
(missing comma → ungrammatical join).

Switched to named capture group `(?P<sep>[，,]?)` + back-reference
`\g<sep>` in the replacement. Comma-when-present is preserved; no phantom
comma added when original had none. Tests: 3 new in
`tests/test_lint_tone_aware.py` `CommaPreservationTests`.

### Documented — Rule 17 warning-vs-error semantics

Expanded `references/self-check-rules.md` § Rule 17 with explicit
guidance on what `passed=True` with multiple warnings actually means.
Rule 17 is **detection-only with three signal levels**; warnings feed
the review skill's Phase 2 7-dimension AI-trace score, they don't gate
publication on their own. Calibrated articles can ship with warnings;
articles drowning in warnings will lose enough 7-dim points to trigger
revision. v2 may upgrade severe sub-check violations to `error`.

### Validated

- `python3 -m pytest tests/ -q` → 107 passed (103 baseline + 4 new
  calibration tests)
- 4-article pilot data preserved at `~/.cache/article-craft/tone-calibration.jsonl`
  (108 records pre-pilot, 12 added during the cross-tier matrix run)
- v2 calibration target: re-run on 20 published articles before further tuning

### Fixed (also rolled in)

- `tests/test_lint_article.py::test_main_honors_frontmatter_tone` had a
  hardcoded path to the now-removed `feat/tone-system` worktree. Replaced
  with `Path(__file__).resolve().parent.parent` so the test runs from any
  repo location (worktree or main).

---

## [Unreleased] - 2026-05-08

### Added

- **Tone system: three-tier register-aware de-AI infrastructure (`neutral` / `casual` / `opinionated`).** New `--tone` CLI flag on `/article-craft` with `flag > frontmatter > writing-style default` precedence; `STYLE_TO_TONE_DEFAULT` maps Style A/C/E → neutral, B/D/F → casual, G/H → opinionated. New `Rule 17: Register Naturalness` in `scripts/review_selfcheck.py` runs four sub-checks (first-person density / strong-opinion presence / summary-phrase ceiling / sentence-length CV) against tier-specific thresholds in `scripts/config.py TONE_THRESHOLDS`. `scripts/lint_article.py` refactored from a single rewrite list into tier-stacked `TONE_LEXICAL_REWRITES` with Vale-style severity (info / warning / error), inline `<!-- lint:disable rule_id -->` regions, and a max-pass oscillation guard. Calibration JSONL written to `~/.cache/article-craft/tone-calibration.jsonl` (opt-out via `ARTICLE_CRAFT_TONE_CALIBRATION=false`) seeds the v2 threshold-tuning pass. Closes the "register too uniform" feedback loop without coupling to AI-detection scoring tools.

### Changed (BREAKING)

- **`scripts/lint_article.py --fix` at default `tone=neutral` no longer auto-deletes paragraph-leading `首先 / 其次 / 最后 / 另外 / 此外 / 同时`.** Those replacements moved to `casual` and `opinionated` tiers. Articles previously relying on lint to strip these at neutral now keep them — set `tone: casual` in frontmatter to restore the old behavior, or run `--tone=casual` on the CLI.
- **Several v1.4.17 red-flag patterns are no longer auto-replaced at neutral**: `综上所述`, `总而言之`, `值得注意的是`, `显然` moved to opinionated/casual tiers; `实际上`, `事实上`, `众所周知`, `不难看出` are no longer in any tier (consider adding back to neutral via `TONE_LEXICAL_REWRITES["neutral"]` if your articles relied on them).

### Why

Closes the "register too uniform" pain captured in `docs/superpowers/specs/2026-05-07-tone-system-design.md`. Reading-feel for AI articles wasn't a structural problem (Rule 5/6 already managed structure) but a register one — every paragraph in the same formal book voice. The tone system gives authors three discrete dial positions and threads them through prevent (write skill) → detect (Rule 17) → fix (lint_article.py) — same architecture as the existing 16 rules, just orthogonal.

Prior-art research (blader/humanizer, hylarucoder/ai-flavor-remover, Vale prose linter, GPTZero burstiness, Zhihu Chinese de-AI consensus) informed the design; rationale and citations in the spec.

### Validated

- `python3 -m pytest tests/ -v` → 103 passed (43 baseline + 60 new across the tone system)
- 4 golden fixture integration tests (neutral / casual / opinionated + cross-tier check)
- Existing 43 baseline tests preserved (regression-protected throughout 30-task plan)
- Calibration JSONL writes verified in temp-dir test
- 16-commit history on `feat/tone-system` branch with two-stage review per task

## [Unreleased] - 2026-05-07

### Added

- **`_ParallelRateLimitCoordinator` — worker-coordinated backoff for the images parallel path.** Closes the long-standing technical debt called out in `CLAUDE.md` § Known design debt: "images parallel path still lacks coordinated backoff". The sequential `generate_and_upload_batch` path got per-image batch-level backoff (30/60/120s + jitter) in v1.4.3, but `generate_and_upload_parallel` workers had no shared rate-limit awareness — when one worker hit `RateLimitExhausted` from the model fallback chain, all the other workers continued hammering the API.

  The new coordinator gives parallel workers a shared pause window. When any worker sees `RateLimitExhausted`, it calls `signal_rate_limit(attempt)` which sets/extends a pool-wide `_pause_until` deadline; every other worker calls `wait_if_paused()` before its next `generate_image()` call and blocks until the deadline expires. Multiple concurrent signals coalesce — only the longest end-time persists, so concurrent 429s on the same wave do not stack. Per-image attempt counters preserve sequential-equivalent semantics: each image gets up to `len(BATCH_BACKOFF_DELAYS_SEC)` retries against the shared schedule, then gives up and the worker moves on with `error_type="rate_limit_exhausted"`.

  `process_single_image` inside `generate_and_upload_parallel` now wraps its `generate_image()` call in a retry loop with explicit `RateLimitExhausted` handling ahead of the generic `Exception` catch — preserving existing handoff for `FileNotFoundError`, `subprocess.TimeoutExpired`, and unknown failures (single-shot fail, no retry).

  New module-level constant `BATCH_BACKOFF_JITTER_MAX_SEC = 5.0` parameterizes the jitter range so tests can pin both delays and jitter to deterministic values. The coordinator resolves both constants at construction time (when args are `None`) so `monkeypatch` of the module attributes flows through.
- **`scripts/lint_article.py` — lightweight auto-fix for mechanical AI-style patterns.** New 484-line script invoked by `skills/lint/SKILL.md` for Rule 5 fixes. Removes roadmap filler (`本文将...` / `接下来我们将...` / `下面分别...`), empty judgement wrappers (`可以看到` / `本质上` / `从这个角度看` / `某种意义上` / `回到问题本身`), repetitive paragraph starters (`首先` / `其次` / `另外` / `此外` / `同时`), high-confidence red-flag words (`赋能` / `一站式` / `链路`), splits overlong hook paragraphs, deletes engagement-style closings, and drops standalone trailing `## 参考资料` sections. Intentionally conservative — never touches code blocks, HTML comment placeholders (`<!-- IMAGE: -->`, `<!-- HARVEST: -->`), Markdown headings, or image/link syntax lines. Reports high-risk sections (consecutive 3 paragraphs without concrete anchors, consecutive summary-tone paragraphs without anchors) that cannot be safely auto-fixed.
- **Rule 5 template-cadence detection** in `references/self-check-rules.md` and `scripts/review_selfcheck.py`. Review now flags: roadmap filler appearing 2+ times, adjacent paragraphs sharing the same starter class (transition-heavy, sequence-heavy), articles with fewer than 2 concrete anchors (numbers, version strings, command snippets, file paths, benchmark output, exact error text), any 3 consecutive body paragraphs with 0 concrete anchors, and sections with 2 consecutive summary-tone paragraphs with 0 anchors. Adds `SEQUENCE_OPENERS`, `EMPTY_JUDGEMENT_PHRASES`, `SUMMARY_TONE_PHRASES`, `ROADMAP_FILLER_PATTERNS` constants. Concrete-anchor heuristic checks for backticks, version strings, multi-segment paths, and error/metric tokens.
- **Test suites for lint and review extensions.** `tests/test_lint_article.py` (10 tests) covers auto-fix coverage, code-block / placeholder safety, hook splitting, trailing-reference deletion, high-risk-section reporting, and `--fix` writeback. `tests/test_review_selfcheck.py` (7 tests) covers Rule 5 template-cadence flagging, summary-tone detection, anchor-density heuristic, code-block break handling, personal-voice pass case, and Rule 6 / Rule 12 boundary cases.
- **`tests/test_image_parallel_backoff.py`** (13 tests) covers the parallel rate-limit coordinator: idle state, schedule exhaustion, jitter bounds, coalescing concurrent signals, pool-wide blocking under `wait_if_paused()`, longer-wave extension over a still-active shorter pause, plus two end-to-end tests of `generate_and_upload_parallel` with monkeypatched `generate_image` (one retries through a 429 then succeeds, one exhausts the schedule and gives up). Whole suite (43 tests across all files) runs in 1.57s.

### Changed

- **`skills/lint/SKILL.md` Step 4 now invokes `lint_article.py` for Rule 5.** Documents the exact `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lint_article.py --article PATH --fix` command and which mechanical patterns it touches. Adds a "High-Risk Sections" review queue to the report format for sections the auto-fix flagged but did not modify.
- **`skills/write/SKILL.md` Step 7 explicitly delegates content-quality rules to `review`.** Adds a 职责分工 block stating that Step 7 only checks downstream-skill handoff contracts (placeholder format, IMAGE / HARVEST validity), and that content-quality rules (red-flag words, template cadence, chapter depth, ending strength) are owned by `review` skill Phase 1's 11 self-check rules. Removes the duplicated instruction to call `review_selfcheck.py` from write.
- **`skills/write/style-guide.md`** picks up the same anti-template-cadence guidance so the writer model has the rule visible at generation time, not just at review.
- **`README.md`** gains an Architecture Overview section: two-layer architecture (skills = workflow, scripts = execution), module relationship tree, responsibility-by-directory table, and key runtime component glossary.

### Why

Closes both technical debt items called out in `CLAUDE.md` § Known design debt:

1. _Self-check rules duplicated across three skills._ `references/self-check-rules.md` was already canonical, but `write/SKILL.md` Step 7, `lint/SKILL.md`, and `review/SKILL.md` Phase 1 each re-stated slices of it in prose, so updating the red-flag list meant remembering three places. Now `write` defers to `review`, `lint` calls the deterministic auto-fix script, and the prose in each skill points at `references/self-check-rules.md` by rule number instead of restating it.
2. _Images parallel path lacks coordinated backoff._ The sequential path got 30/60/120s + jitter batch backoff in v1.4.3. The parallel path now matches via `_ParallelRateLimitCoordinator`. Workers no longer stampede a rate-limited Gemini quota.

### Validated

- `python3 -m pytest tests/ -q` → 43 passed in 1.57s
- Coordinator integration tests use patched `BATCH_BACKOFF_DELAYS_SEC=(0.05, 0.05)` + `BATCH_BACKOFF_JITTER_MAX_SEC=0.0` for deterministic, fast runs (<2s)
- Existing tests (`tests/test_config.py`, `tests/test_pipeline_state.py`, `tests/test_verify_claims.py`) unaffected.

## [Unreleased] - 2026-04-22

### Fixed

- **Gemini can't render Chinese text in images — articles silently produced garbled glyphs.** Two articles shipped with CDN cover images full of distorted/misspelled Chinese characters because `<!-- PROMPT: -->` lines asked Gemini to render menus, magazine covers, calligraphy scrolls, etc. with embedded Chinese text. Triple-layer fix:
  1. **Write-stage rule** in `skills/write/SKILL.md` section 3f: a new "⛔ 硬禁止：PROMPT 里绝对不能要求 Gemini 渲染任何可读文字" block with a 5-line bad/good matrix and the mandatory tail constraint `No readable text anywhere, no letters, no numbers, no labels, no captions, no logos.` Also documents the self-contradiction case (don't use Gemini to illustrate another model's text-rendering ability).
  2. **Style-guide rule** in `skills/images/image-guide.md` "Prompt 写作规则": expanded rules #5-6 from one-line soft guidance into a full hard-block with examples of visual-substitution patterns (menu → menu silhouette with column layout, calligraphy → brush-stroke marks without characters, etc.).
  3. **Self-check Rule 16** in `scripts/review_selfcheck.py` and `references/self-check-rules.md`: new automated detector that scans every `<!-- PROMPT: -->` line for (a) any CJK character `[一-鿿぀-ヿ가-힯]` — hard fail; and (b) common "render text X" instructions like `text "…"`, `title "…"`, `headline "…"` unless the prompt also contains `no readable text` / `no letters` / `no labels` as a defusing whitelist. Rule count upgraded from 15 to 16.

### How it was caught

User shipped two articles (`chatgpt-image-2-prompt-handbook.md`, `kimi-k2-6-from-k25-upgrade.md`) where cover + rhythm image CDN URLs came back with mangled Chinese characters. The old image-guide had one line ("不要写文字内容") but it wasn't enforced anywhere downstream, so Gemini still got prompts asking for things like `magazine cover titled "VOL.08 慢生活"`, `menu with items "招牌菜 ¥68"`, `calligraphy scroll saying "静"`. Rule 16 now catches these pre-generation.

### Validated

- `review_selfcheck.py` on the fixed text-free articles → Rule 16 PASS ✅
- Synthetic test with CJK in PROMPT → Rule 16 FAIL with specific character samples in the suggestion
- Synthetic test with `text "X"` + `no readable text` whitelist → Rule 16 PASS (correctly defused)

## [1.4.17] - 2026-04-16

### Fixed

- **Screenshot skill was capturing entire scrolling pages instead of the relevant content.** Two compounding bugs:
  1. `suggest_selector()` for `github.com/<user>/<repo>` returned `#repo-content-pjax-container` (the entire repo content pane incl. file tree + sidebar = basically full page). Changed to `"article#readme, #readme, article.markdown-body, .markdown-body"` — try in order, pick the first that exists and is ≥ 400px tall.
  2. When `suggest_selector()` returned an empty string (no pattern matched), `capture_screenshot()` fell through to `full_page=True`. For an unknown URL with no writer-supplied selector, this silently produced a giant scrolling capture. Changed default to `full_page=False` (viewport only / above-the-fold) so the image stays manageable and obviously "the main thing" on that page.
- **Candidate selector iteration.** Previously `.split(",")[0]` used only the first comma-separated candidate; if it didn't match, the code stopped. Now iterates all candidates, rejecting any whose bounding box height is < 400px so too-narrow elements (e.g., a single feature card) don't get picked as the "content zone" on landing pages.
- **Extended doc-pattern match list** in `suggest_selector()`: adds `official.`, `/guide/`, `/reference/`, `/getting-started`, `/quickstart`, `/tutorial`, `/manual` so product docs sites like `mempalaceofficial.com/guide/hooks.html` resolve to `article, main, ...` instead of falling through to the viewport fallback.

### Added

- **Recommended-selectors table in `skills/write/SKILL.md`** Section 3f — writer now has an explicit reference for which selectors to pair with which URL types (GitHub repo → `#readme`, docs site → `main` or `article`, Twitter status → `[data-testid="tweet"]`, etc.).

### How it was caught

User reported that a published tutorial article (`mempalace-local-memory-tutorial.md`) had two screenshots captured as entire scrolling pages instead of the key sections described in their captions ("README with scam alert + benchmark", "docs homepage hero"). Live end-to-end rescreenshot validated:
- `github.com/MemPalace/mempalace` → `article.markdown-body` (3597px tall — the full README, matching caption)
- `mempalaceofficial.com` → viewport (1280×800 hero section — the actual landing page, not a feature card)

### Takeaway

Any "smart selector" path that returns nothing or a null-match needs an opinionated narrow-ish default (viewport beats full-page for unattended captures). Writer guidance table prevents this from recurring as a quiet regression.

## [1.4.16] - 2026-04-16

### Fixed

- **`rehost` and `expand-harvest` subcommands: stdout no longer polluted by upload progress.** Every CDN upload (PicGo / S3) prints "📤 上传图片: ..." / "✅ Upload successful" / etc. to stdout. `expand-harvest` also writes its JSON result to stdout, so downstream `| jq` / automated consumers got an interleaved text+JSON stream that couldn't be parsed. Both CLI dispatchers now wrap their work in `contextlib.redirect_stdout(sys.stderr)` — progress goes to stderr (still visible when you're running interactively), and stdout is guaranteed pure JSON.

### How it was caught

Running a real end-to-end Style H integration test (3 HARVEST placeholders → rehost → upload → substitute) against a real WeChat Style H article URL. The article.md output was correct — all 3 CDN URLs present, GIF preserved as `.gif`, cover right — but piping `expand-harvest` stdout to `jq` in the test harness failed with `JSONDecodeError: Expecting value`. The end-to-end test is what surfaced it; unit tests with mocked upload never saw the noise.

### Takeaway

Any subcommand that emits JSON for machine consumption needs to keep stdout clean. Rule: progress → stderr, result → stdout. Checked by `subcommand | jq . > /dev/null && echo ok`. Other candidates in the repo (not fixed here — no JSON output yet): `check`, `screenshot`, `harvest` already either go to stdout intentionally or write to files; `batch` writes to a dir; `harvest-menu --json` doesn't invoke upload paths.

## [1.4.15] - 2026-04-16

### Added

- **Publish copies Style H sidecars to the KB.** New publish Step 3.5: if `_evidence.json` or `_harvest_menu.md` exist alongside `article.md` in the source directory, `cp` them into the same target subdirectory in the KB. Preserves the full HARVEST picking context so a future `/article-craft --upgrade /kb/path/article.md` can resume operations (re-rehost a rotted CDN URL, regenerate menu, verify placeholders) without the user chasing down the original materials dir.
- **`pipeline_state.py` infers Style H from sidecars** in heuristic mode. When no state file exists (post-publish cleanup, or articles predating v1.4.2), `_scan_article()` now also checks for `_evidence.json` and `_harvest_menu.md` next to the article. `_stage_done_heuristic("evidence", scan)` returns true when the sidecar is present; `_compute_missing()` treats `writing_style="H"` as inferred in that case, so the evidence stage stays in the `want` list instead of being pruned.
- **Publish summary shows sidecar status** (`_evidence.json`, `_harvest_menu.md` — copied / none).

### Why

The "11 releases from one WeChat article" streak shipped evidence, menu, preflight, and drop-in placeholders — all fantastic at write time. But publish silently stranded them in the source dir. Net effect: published Style H articles couldn't be re-upgraded. Fixing it is one `cp` loop in publish + two small helpers in `pipeline_state.py`.

### What this unlocks

- `/article-craft --upgrade /kb/2026-04/article.md` on a published Style H article now finds `_evidence.json` via heuristic, correctly identifies Style H, keeps `evidence` stage as done, and re-runs only what's genuinely stale (e.g., a broken CDN URL).
- Re-running `harvest-menu --evidence /kb/path/_evidence.json` still works post-publish (file is where the article is).
- `expand-harvest` still works because `--evidence` defaults to article dir.

### Design note

Policy split:
- **`.article-craft-state.json`**: pipeline-run-scoped, deleted on publish (v1.4.2 rule unchanged)
- **`_evidence.json` + `_harvest_menu.md`**: article-scoped, follow the article (v1.4.15 new rule)

Hyphen vs underscore in filenames reflects the divide: `.state` (hidden, ephemeral) vs `_evidence`/`_harvest_menu` (visible, per-article artifacts).

## [1.4.14] - 2026-04-16

### Added

- **Drop-in HARVEST placeholder block** in `_harvest_menu.md`. For each source, a fenced markdown code block renders the recommended picks as ready-to-paste `<!-- HARVEST: url idx=N caption="..." -->` lines. Writer copies the block, replaces `...` with actual captions, deletes unused lines. GIF picks carry an inline `# GIF / 动图` comment.

### Why

v1.4.13 gave the writer recommended idx values. But the writer still had to manually compose `<!-- HARVEST: {url} idx={N} caption="..." -->` — typing the URL, remembering `--cover` syntax, deciding GIF vs still. This removes all that boilerplate. The full recommendation structure (1 cover + up to 5 main + all GIF demos) ships pre-wired; writer only types captions.

### Impact

Pipeline progression for the writer now looks like:
1. `cat _harvest_menu.md` — see 28 images summarized + recommendations
2. Copy the "🧱 Drop-in HARVEST placeholders" block
3. Paste into article.md at the chosen narrative positions
4. Replace `...` with captions (the only non-mechanical step)
5. Delete unused lines
6. Save — write Step 7 Check C validates against `_evidence.json` via `expand-harvest --dry-run --strict`

Zero URL typing, zero idx guessing, zero cover-syntax recall. The remaining cognitive load is exactly what it should be: where each image goes in the narrative and what its caption says.

## [1.4.13] - 2026-04-16

### Added

- **Recommended picks in `harvest-menu`**. Each source now gets a `📌 Recommended picks` block with four curated groups:
  - **Cover** — prefers `--cover` when source has og:image, else picks the biggest wide non-GIF
  - **Main visuals** — up to 5 non-GIF idx values ≥400×200, ranked by area
  - **Animation demos** — every GIF idx, ranked by area
  - **Likely avoid** — tiny images (<400×200) that are probably icons, QR codes, or decorative flourishes
- **JSON output gains `recommend` field** per source with `{use_cover_flag, cover_idx, main, demo, avoid}`.

### Why

v1.4.12 gave writers a menu file. But reading a 28-row image table and mentally finding "biggest jpg with good aspect ratio for cover" is still work Claude has to do, which means inconsistency. The recommendation block converts the raw listing into a "point at what to copy" guide — for the real WeChat article this surfaced cover=--cover, 4 correct GIF demos, and 5 icon-sized images to skip, all without writer judgement.

### Design note

Recommendations are **soft hints**, phrased as "guidance — not exhaustive, override freely". They don't prune the full image table; writers can still pick any idx. The goal is to reduce cognitive load, not lock writers in.

Thresholds chosen from observed behavior on a real WeChat Style H article:
- wide enough: ≥400×200 (filters out WeChat QR codes at 272×272 and follow-up cards at 252×214)
- cover candidate aspect: ≥1.3 (landscape bias for hero images)
- main visuals top-5 (enough for a long article, not spam)

## [1.4.12] - 2026-04-16

### Added

- **`evidence.py collect` now also emits `_harvest_menu.md`** next to `_evidence.json`. Calls `screenshot_tool.harvest_menu()` as a side effect; failure is non-fatal (printed warning, evidence still written).
- **write Step 3d-H now reads `_harvest_menu.md` by `cat`**, with CLI fallback when the file is missing (compat for legacy evidence output or manual invocations).

### Why

v1.4.11 gave writers a cheat-sheet command (`harvest-menu`) but relied on the writer to remember to run it. That's another step between "evidence exists" and "writer knows what's available" — one the writer can skip. Making the menu a **file** next to `_evidence.json` means it's always present, always fresh, and write skill consumes it with a trivial `cat` rather than a subcommand call.

### Design note

The menu is a pure view of `_evidence.json`. When someone regenerates evidence, menu regenerates too; when evidence is up-to-date, menu is up-to-date. Coupling generation this way avoids "menu out of sync with evidence" — a failure mode you'd otherwise need cache invalidation to prevent.

## [1.4.11] - 2026-04-16

### Added

- **New `harvest-menu` subcommand** — emits a writer-facing cheat-sheet from `_evidence.json` listing every HARVEST option with its exact `idx=N` value. Default output is markdown (a table per source with `idx | dim | fmt | alt` + ready-to-paste placeholder examples); `--json` emits structured data. Cover availability, paywall citations, and local manual files are each their own section.
- **write Step 3d-H now requires reading the menu** before emitting HARVEST placeholders. Replaces the previous "consume `_evidence.json` from memory" approach with a mechanical lookup: `idx` values in the menu are guaranteed to match what `expand-harvest --dry-run --strict` will validate downstream. write is explicitly told: cover from menu example, main images by scanning the `dim` column for the largest, GIFs by filtering `fmt=gif`, and to **not** use `alt="..."` matching for WeChat sources (where all alts are the generic "图片").

### Why this was needed

Running `harvest-menu` against real WeChat evidence surfaced a subtle systemic issue: all 28 WeChat `<img>` alts come back as "图片" (the generic fallback). A writer guessing "pick the Claude Code UI image by alt" would never match. The menu makes this visible — writer sees 27 identical "图片" alt entries and automatically switches to `idx=` by dimension. No more silent mismatches piling up for v1.4.10's Check C preflight to catch.

### Design note

Three-way purpose split now locked in:
- `harvest`: crawls a source page, returns list + cover to evidence.py
- `harvest-menu`: formats that list for the writer, no side effects
- `expand-harvest`: consumes the placeholders the writer emitted, applies rehost

Each speaks to exactly one actor (collector, writer, expander) and never crosses wires.

## [1.4.10] - 2026-04-16

### Added

- **Write Step 7 gains Check C: HARVEST preflight for Style H.** After article.md is saved and the existing Check A / B pass, if `_evidence.json` exists next to the article (Style H signal), Check C runs `expand-harvest --dry-run --strict` to verify every `<!-- HARVEST: -->` placeholder resolves against evidence. On failure, the trace is parsed and each broken placeholder gets a specific remediation hint:
  - `source_not_in_evidence` → register the URL in materials.md or switch to a registered one
  - `no_matching_image` with `idx=N` → `idx` is out of range, pick a valid index
  - `no_matching_image` with `alt="…"` → alt substring didn't match; use a matching substring
  - `no_matching_image` with `--cover` → source has no og:image; use `idx=` instead
- The writer iterates: fix placeholders → re-save → re-run preflight → until exit 0 before leaving write stage.

### Why this was needed

Without this check, a writer confidently typing `idx=7` (when evidence only has 5 filtered images) produces an article that silently carries unresolved `<!-- HARVEST: -->` comments into the images stage. The article ships with visible placeholder comments. Check C closes this failure mode **at write time**, where the fix is cheap — no images-stage quota burned, no expensive round trip.

### Design note

Check C is **Style H-triggered** (gated on `_evidence.json` existence), not style-triggered, so it also runs for any non-Style-H article that happens to use HARVEST. The `--dry-run` means zero network calls during the check. `--strict` means a single broken placeholder blocks completion, keeping the failure surface sharp.

## [1.4.9] - 2026-04-16

### Added

- **`expand-harvest --dry-run`** — preview mode. Parses placeholders, resolves images against `_evidence.json`, and reports what would happen (including whether each URL matches the rehost whitelist), but **skips all network calls and never writes `article.md`**. Added after an integration test accidentally uploaded 3 real images to the project's CDN during a hand-run check — `--dry-run` is the "no side effects" escape hatch.
- **`expand-harvest --strict`** — preflight quality gate. If any placeholder resolves to `source_not_in_evidence` or `no_matching_image`, the subcommand exits `1` and **does not modify `article.md`**. Intended as an orchestrator / CI gate before the (irreversible, network-spending) real expand. Works in combination with `--dry-run` to validate materials.md correctness without any upload.
- **New `trace[].rehost` states for dry-run**: `would_rehost` / `skipped_mode_never` / `skipped_not_whitelisted`. Makes the preview output actionable — you can see exactly which images would flow through rehost vs pass through.
- **Summary fields `dry_run` / `strict` / `would_write`** in the JSON output, so downstream tooling can distinguish preview from real runs.

### Design note

`--strict` wraps around `--dry-run` cleanly: one to confirm the article parses correctly, the other to commit. Recommended orchestrator flow:

```bash
# preflight
expand-harvest --dry-run --strict   # exit 1 → fix materials first
# real run
expand-harvest                       # network calls + article mutation
```

## [1.4.8] - 2026-04-16

### Fixed

- **Lazy-loaded image harvest on WeChat pages was dropping ~80% of images.** Playwright extracted `<img>` tags before scrolling, so only above-the-fold images had their `src` / dimensions populated — a 31-image WeChat article returned 6. `harvest_images()` now scrolls the page top → bottom in `innerHeight`-sized steps with 150ms pauses between scrolls, waits for network idle, then runs the extraction. On the same WeChat article this lifts recall from 6 to 28 (90% vs baoyu-fetch's 31-link reference).
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

Fixes the two top gaps identified from reading a real WeChat Style H article (31 images, 4 GIFs, all `mmbiz.qpic.cn`):

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

- **Style H — 爆料自媒体 / 公众号爆款** in `references/writing-styles.md`: new writing style modeled on AI-news 公众号 voice (dramatic headlines, short hook paragraphs, source-image reuse) — 戏剧性标题、H2 钩子句、源图直引、竞争对垒叙事、泄露代号对照、极短段落。Includes auto-detect signals ("曝光"、"爆料"、"突袭"、"泄露"、"一夜"、"硬刚"、股价/竞品对垒) and hard constraints enforced by the write skill.
- **New `evidence` skill** (`skills/evidence/SKILL.md` + `commands/article-craft/evidence.md` + `scripts/evidence.py`): collects source evidence for Style H. Parses `materials.md` (public URLs / local paths / gated citations), batches `harvest` calls across all public sources, outputs `_evidence.json` consumed by write. BLOCKS the pipeline for Style H when materials are missing or evidence-image count < 2.
- **`screenshot_tool.py harvest` subcommand**: extracts all `<img>` URLs + alt + width/height + surrounding context from a source URL. **Playwright primary** (fast, JS-rendered) with **baoyu-fetch fallback** for CAPTCHA / login walls / paywalls (auto-detects 微信公众号 / Cloudflare gates and switches engines). Output JSON is directly consumed by `evidence.py`.
- **`<!-- HARVEST: url idx= | alt= [caption=] -->` placeholder**: expands in-place to `![caption](远端 url)` without downloading or re-uploading. Implements the WeChat-爆款-style "直引源站图片" pattern — the remote CDN stays the source of truth, article-craft never becomes the image host. Processed by screenshot skill alongside existing `<!-- SCREENSHOT: -->` placeholders.

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
