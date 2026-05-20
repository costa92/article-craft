# Screenshot End-to-End Snapshot Tests (B3)

**Status**: Phase 1 ✅ **done v1.6.18** (2026-05-20); Phases 2-4 queued
**Date**: 2026-05-20
**Target version**: multi-phase
**Author**: costa
**Backlog ref**: B3 in `docs/research/2026-05-20-feature-candidates.md`
**Closes pattern**: A2 (Screenshot framing / selector regressions) in same doc

---

## 0. Problem statement

Between v1.4.17 and v1.5.6 — five consecutive releases — every patch
fixed something in `scripts/screenshot_tool.py`'s framing / selector
logic:

| Release | Fix |
|---------|-----|
| v1.4.17 | Full-page default → viewport |
| v1.5.3 | 900 px max-height cap + ANCHOR keyword scrolling |
| v1.5.4 | Anchor scope was matching sidebars instead of main content |
| v1.5.5 | `HOST_MAIN_SELECTORS` dict introduced for 14 platforms |
| v1.5.6 | Selector candidate height floor 400 → 100; element-timeout viewport fallback |

The root cause isn't any individual bug — it's that **there is no
regression net**. `tests/test_screenshot_crop.py` only tests the
dictionary lookup logic (does `HOST_MAIN_SELECTORS["github.com"]`
return the right entry?), not actual rendering. A user-reported bug
becomes the only feedback signal.

Each new platform added to `HOST_MAIN_SELECTORS` (15 today) is one more
DOM contract that can silently break when the platform redesigns its
HTML. Without snapshot tests, the next regression will follow the same
pattern: ship → user reports broken screenshot → fix and release →
repeat.

---

## 1. Design goals

1. **Detect HOST_MAIN_SELECTORS regressions in CI** — for every
   platform in the dict, prove that against a known DOM fixture the
   tool selects the right element and produces a reasonable bounding
   box.
2. **Detect cropping / anchor regressions** — `crop_to_max_height`,
   `crop_to_aspect_ratio`, `ANCHOR:kw` scrolling, height-floor logic
   (v1.5.6 fix) all have observable per-platform expected behavior.
   Pin it.
3. **Detect false-positive 404 / empty-page detection** — the
   `is_404_content` heuristic has fired on real content before. Test
   it against fixture HTML that contains the word "404" in non-404
   contexts (e.g. an article about HTTP status codes).
4. **No live-network dependency in CI** — fixtures are committed
   HTML; tests must run hermetically. CI cost stays in the order of
   "Playwright already runs there for `doctor.py check`".
5. **Stable across non-regression site redesigns** — when a platform
   redesigns its HTML, the test should fail with a *useful* message
   (selector X no longer matches in fixture Y) rather than a flaky
   pixel-diff or a network-flake.

---

## 2. Non-goals

- ❌ **Pixel-exact visual diff** — Playwright screenshot comparison is
  famously brittle (font rendering, sub-pixel differences across
  Chromium builds). We assert *bounding boxes* and *selector matches*,
  not pixel buffers.
- ❌ **Live-site smoke tests** — separate concern (we already get user
  reports for this; flaky CI on real GitHub / Reddit pages would be
  worse than no CI).
- ❌ **Cross-browser** — Playwright-Chromium only (matches the
  production code path).
- ❌ **CDN upload path** — already covered by
  `tests/test_screenshot_upload.py` + `tests/test_uploaders.py`.
- ❌ **HARVEST / rehost flow** — separate test surface
  (`test_screenshot_*` files already cover this).
- ❌ **Automatic fixture refresh** — fixtures are deliberately frozen
  per release; refreshing is a manual, opt-in PR.

---

## 3. Architecture

### 3.1 Fixture format

Each fixture is a self-contained directory under
`tests/fixtures/screenshot/<platform-slug>/`:

```
tests/fixtures/screenshot/
├── github/
│   ├── repo-readme.html          # Saved HTML, single-page (no JS execution)
│   ├── repo-readme.expected.json # Expected selector + bbox + anchor result
│   └── SOURCE.txt                # Provenance (URL captured, date, archiver)
├── stackoverflow/
│   ├── question.html
│   ├── question.expected.json
│   └── SOURCE.txt
├── hn/...
├── reddit/...
└── ... (one dir per HOST_MAIN_SELECTORS entry — currently 15)
```

`*.html` is **saved page** (Chrome "Save As → Webpage, Complete" or
SingleFile extension — inlines images/CSS, no external resources). Why
not MHTML: Playwright doesn't load MHTML; the inlined HTML approach is
universally portable.

`*.expected.json` schema:

```json
{
  "url_pattern": "https://github.com/*",
  "expected_selector": "article.markdown-body, [data-testid='readme']",
  "expected_bbox_min": {"width": 600, "height": 100},
  "expected_bbox_max": {"width": 1280, "height": 5000},
  "anchor_keywords": ["installation"],
  "anchor_expected_y_min": 50,
  "is_404_expected": false
}
```

### 3.2 Fixture serving (the routing trick)

`capture_screenshot(url, ...)` resolves `HOST_MAIN_SELECTORS` from the
URL's host. To exercise this code path without leaving the host
matching to chance, the test:

1. Starts a tiny local HTTP server (`http.server` from stdlib, ephemeral
   port) that serves `tests/fixtures/screenshot/<platform>/`.
2. Uses Playwright's `page.route("**/*", handler)` to intercept the
   *real* hostname's requests and redirect them to the local server —
   so the URL `https://github.com/foo/bar` resolves to the fixture
   while `HOST_MAIN_SELECTORS["github.com"]` still gets picked.

```python
# pseudo-code
def serve_fixture(fixture_dir, fake_host, port=0):
    server = start_http_server(fixture_dir, port)
    real_port = server.port

    def route_handler(route):
        url = route.request.url
        if fake_host in url:
            local_url = f"http://localhost:{real_port}/" + url.split(fake_host, 1)[1]
            route.continue_(url=local_url)
        else:
            route.continue_()
    return server, route_handler
```

The capture flow then goes:

```
capture_screenshot("https://github.com/foo/bar")
   → context.route(handler)    # injects the redirect
   → page.goto(url)             # hits localhost; Playwright sees github.com
   → main_content_selectors_for_host(url)  # matches "github.com" entry
   → asserts against expected.json
```

### 3.3 Test runner

Single test module `tests/test_screenshot_e2e.py` that:

1. Discovers all `tests/fixtures/screenshot/*/` directories
2. Parametrizes over them (`pytest.mark.parametrize`)
3. Per fixture: serve, navigate, capture, load `expected.json`, assert

Two assertion modes per fixture:

| Mode | What it checks |
|------|----------------|
| `selector` | `suggest_selector(url)` returns one of `expected_selector` candidates AND that selector matches at least one DOM node in the fixture |
| `bbox` | The captured PNG's dimensions fall within `bbox_min`/`bbox_max` rectangle |

### 3.4 CI integration

Existing `.github/workflows/tag-release.yml` only handles tagging.
B3 needs a *separate* workflow that:

1. Installs Python deps + Playwright Chromium
2. Runs `pytest tests/test_screenshot_e2e.py` on every PR
3. Fails the PR if any fixture's assertions fail
4. Caches the Playwright browser between runs

Per-fixture run is ~5 sec (no network, in-memory HTML). 15 fixtures =
~75 sec. Acceptable for PR CI.

---

## 4. Implementation phases

### Phase 1 — Foundation (1–2 days, **1 release**)

**Scope**: Build the infrastructure with ONE platform fixture as proof
of concept. No regression coverage yet; this phase proves the
architecture works.

**Deliverables**:

- `tests/fixtures/screenshot/github/` with one fixture (repo README
  page from a stable, frozen commit URL)
- `tests/fixtures/_screenshot_e2e_helpers.py` — the HTTP server + route
  handler utility
- `tests/test_screenshot_e2e.py` — single parametrized test exercising
  only GitHub
- Documented fixture-capture procedure in
  `tests/fixtures/screenshot/README.md` (how to add a new platform)

**Done when**: `pytest tests/test_screenshot_e2e.py` passes locally
against the one GitHub fixture, with the captured selector logged in
test output.

**Estimated effort**: 1–2 days. Risk: Playwright `page.route()` URL
rewriting edge cases (cross-origin, redirect handling).

### Phase 2 — Platform coverage (3–5 days, **1–3 releases**)

**Scope**: One fixture per `HOST_MAIN_SELECTORS` entry. Can be split
across multiple releases (e.g. group by 3-platform batches).

**Per-platform work**:

1. Capture HTML — `wget --mirror` or SingleFile browser extension on a
   representative public page; commit under `tests/fixtures/screenshot/<slug>/`
2. Hand-author `expected.json` with selector + bbox tolerances
3. Add `SOURCE.txt` with provenance (URL, date, sha256 of HTML)
4. Add to the parametrize list

**Done when**: All 15 `HOST_MAIN_SELECTORS` entries have a fixture.
The first run sets the baseline; thereafter every PR exercises the
full grid.

**Estimated effort**: ~30 min per platform (capture + assert), ~7–8
hours total. Split across releases as appetite allows.

### Phase 3 — CI wiring (½ day, **1 release**)

**Scope**: New `.github/workflows/screenshot-e2e.yml` running on
`pull_request` + scheduled weekly run.

**Deliverables**:

- Workflow file with Playwright install + cached browser
- `pytest tests/test_screenshot_e2e.py -v` step
- README badge linking to workflow status

**Done when**: PR opened → workflow runs → green badge in README.

**Estimated effort**: 2–4 hours.

### Phase 4 — Maintenance protocol (½ day, **1 release**)

**Scope**: Document the human protocol for when fixtures rot (platform
redesigns HTML, selector breaks).

**Deliverables**:

- `tests/fixtures/screenshot/MAINTENANCE.md`:
  - When to refresh (quarterly cadence or when a real regression
    surfaces)
  - How to refresh (re-capture HTML, regenerate `expected.json`,
    commit as a single PR with explanation)
  - Rules: never refresh fixture + production selector in the same PR
    (otherwise the test won't catch the real regression)
- Add to CLAUDE.md "Known design debt" → close out A2 reference

**Done when**: The maintenance doc exists and is referenced from
`CONTRIBUTING.md` (or equivalent).

---

## 5. Risks

### 5.1 Fixture rot

**Risk**: A platform redesigns; the fixture stays frozen; test passes
against stale HTML while production breaks against the new HTML.

**Mitigation**:

- Phase 4's quarterly refresh cadence
- Tests assert *selector matches in the fixture*, not just "selector
  string equals expected" — so a stale fixture that the selector
  doesn't match against still fails the test loudly
- Live-site smoke test as a separate (manual / scheduled) job that
  hits real URLs and reports drift between live behavior and fixture
  behavior — out of scope for B3 but listed here as the next layer

### 5.2 Cross-origin / route rewriting edge cases

**Risk**: Playwright's `page.route()` semantics with redirected hosts
might not faithfully reproduce the production "navigate to https URL"
code path.

**Mitigation**: Phase 1 explicitly verifies the architecture works
before committing to platform coverage. If `page.route()` doesn't
suffice, fall back to monkey-patching `_user_main_content_overrides()`
or `main_content_selectors_for_host()` in the test to inject the
expected selector for the fake URL.

### 5.3 CI Playwright cost

**Risk**: GitHub Actions runners are billed per minute. 15 fixtures ×
5 sec + Playwright install (~2 min) = 3–4 min per PR. Across many
PRs, could be meaningful.

**Mitigation**:

- Cache Playwright browser (`~/.cache/ms-playwright`) — install only
  on cache miss
- Parallelize fixture runs with `pytest-xdist`
- For draft PRs, skip the workflow (manual trigger only)

### 5.4 Large fixture file size

**Risk**: Saved HTML with inlined images/CSS can be 100KB–2MB per
fixture. 15 fixtures × 1MB = 15MB in repo.

**Mitigation**:

- Strip non-essential assets during capture (no fonts, no analytics,
  no images larger than 50KB — the screenshot tool doesn't need them
  to test selector resolution)
- Use `git lfs` for any fixture >500KB
- Accept it; 15MB in a 50MB repo is acceptable cost for the
  regression net

### 5.5 Anchor / cropping behavior is harder to fixture

**Risk**: `ANCHOR:kw` scrolling depends on real page height and
`scrollIntoView` semantics. Fixture HTML is static and may not
reproduce these.

**Mitigation**: Phase 2 assertions for anchor-using fixtures can
relax the bbox check and assert only "anchor element was scrolled into
viewport region" (Y coordinate within page bounds). Acceptable
coverage — perfect not the enemy of good.

---

## 6. Open questions (resolve before Phase 1)

1. **Which one platform for Phase 1?** Recommendation: **GitHub
   repo README** — most stable HTML, simplest selector
   (`article.markdown-body`), already the test case used in
   `test_screenshot_crop.py`.
2. **Fixture capture tool**: Chrome SingleFile extension vs
   `wget --mirror` vs custom Playwright script that saves
   `page.content()`? Recommendation: **custom Playwright script**
   committed at `tests/fixtures/screenshot/_capture.py` — gives
   per-fixture reproducibility and lets us strip resources programmatically.
3. **HTTP server**: stdlib `http.server` (simple, blocking) vs
   `aiohttp` (already a dep? — no, currently not). Recommendation:
   stdlib `http.server.ThreadingHTTPServer` — zero new dependencies.
4. **`expected.json` schema versioning**: include
   `"schema_version": "1"` from day one so future expansion (e.g.
   adding `expected_text_density`) doesn't break old fixtures.
5. **Should the workflow gate releases?** If `screenshot-e2e.yml` is
   red, should `tag-release.yml` still tag? Recommendation: **no**
   — make screenshot-e2e a required check for `main` branch protection.

---

## 7. Concrete next step (when Phase 1 starts)

Pick: GitHub repo README, fixture captured from
`https://github.com/anthropics/anthropic-cookbook` (or similar
stable target). Set up the HTTP server + route handler, parametrized
test, expected.json. Run locally; green ⇒ Phase 1 ships in a single
small release; everything else from Phase 2 onward builds on it.

This document is the contract — when someone picks up Phase 1 later,
they should be able to start coding from the architecture in §3 and
the deliverable list in §4 without re-deriving any design decision.
