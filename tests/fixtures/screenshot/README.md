# Screenshot E2E fixtures

Frozen DOM fixtures for `tests/test_screenshot_e2e.py`. Each subdirectory
exercises one entry in `scripts/screenshot_tool.HOST_MAIN_SELECTORS`.

Spec: `docs/superpowers/specs/2026-05-20-screenshot-e2e-snapshot-tests.md`

## Directory layout

```
tests/fixtures/screenshot/
├── github/
│   ├── repo-readme.html          # Frozen DOM (saved or synthetic)
│   ├── repo-readme.expected.json # Selector + bbox contract
│   └── SOURCE.txt                # Provenance (origin, date, hash)
├── stackoverflow/      (Phase 2)
├── hn/                 (Phase 2)
└── ... one dir per HOST_MAIN_SELECTORS entry
```

## How the test uses a fixture

1. The test reads `<slug>.expected.json` → gets `url_pattern`,
   `expected_selector_candidates`, `expected_first_match`,
   `expected_bbox_min` / `expected_bbox_max`.
2. Playwright opens a headless Chromium page.
3. `page.route("**/*", ...)` is wired to fulfill any request matching
   the URL's host with the local fixture HTML — keeps the page URL
   visible as the canonical `url_pattern` so `suggest_selector(url)` /
   `main_content_selectors_for_host(url)` still resolve the right
   host key.
4. `page.goto(url_pattern)` loads the fixture.
5. The test asserts:
   - `suggest_selector(url_pattern)` includes ≥1 candidate from
     `expected_selector_candidates`.
   - The `expected_first_match` selector matches ≥1 DOM node.
   - The first-match element's bounding box is within
     `[expected_bbox_min, expected_bbox_max]`.

Sub-resources (CSS / fonts / external JS) are aborted by the route
handler, so the fixture HTML must embed its own minimal `<style>`.

## Adding a new fixture

```
mkdir tests/fixtures/screenshot/<slug>/
```

1. **Capture the page** — either:
   - **Synthetic** (smaller, recommended for Phase 1-ish coverage):
     hand-author a minimal HTML reproducing the target element +
     decoy siblings that must NOT win selection.
   - **Real capture**: Chrome → Save As → "Webpage, Complete" or
     the SingleFile browser extension. Inline all sub-resources.
     Real captures are typically 100 KB - 2 MB per file.

2. **Author `<slug>.expected.json`**:

   ```json
   {
     "schema_version": "1",
     "platform": "<slug>",
     "url_pattern": "https://<host>/<canonical-path>",
     "fixture_html": "<slug>.html",
     "expected_selector_candidates": [
       "<first selector HOST_MAIN_SELECTORS lists>",
       "<second>",
       "..."
     ],
     "expected_first_match": "<the selector that should match in this fixture>",
     "expected_bbox_min": {"width": 200, "height": 100},
     "expected_bbox_max": {"width": 1600, "height": 5000},
     "anchor_keywords": [],
     "is_404_expected": false,
     "notes": "<why this fixture exists>"
   }
   ```

   - `expected_selector_candidates` mirrors the `HOST_MAIN_SELECTORS`
     entry for the host (or the path-sensitive return from
     `suggest_selector`).
   - `expected_first_match` is what the fixture itself contains —
     usually one of the candidates, but a fixture might intentionally
     reproduce only the second-candidate shape (e.g. when GitHub uses
     `.markdown-body` without an `article#readme` wrapper).
   - `expected_bbox_min` / `expected_bbox_max` are wide tolerances —
     this isn't a pixel-diff test, just "the element rendered
     reasonably."

3. **Write `SOURCE.txt`** documenting:
   - Origin (`SYNTHETIC` or a real URL)
   - Date captured
   - Author
   - Brief why (what selector / regression this fixture pins)

4. **Run the test**:

   ```bash
   python3 -m pytest tests/test_screenshot_e2e.py -v
   ```

   The fixture is auto-discovered — no test file edit needed.

## Maintenance protocol

When a platform redesigns its HTML and the production selector breaks,
**refresh the fixture in a separate PR from the production selector
change** — otherwise the test's regression net is bypassed (you'd
update both, the test passes, and you have no signal that the
production selector still works against the new DOM in the wild).

The procedure:

1. PR A: capture the new HTML, update `<slug>.html`, update
   `<slug>.expected.json` if the bbox / first-match changed.
   Run the test — it should PASS against the new fixture with the
   OLD production selector (the test pins selector-against-fixture,
   not selector-against-live-site).
2. PR B (separate): update `HOST_MAIN_SELECTORS` in
   `scripts/screenshot_tool.py` to handle the redesign.

If both selectors break (old fixture + old prod selector both fail
the new DOM), that's the cue the redesign is structural — usually
write a brand-new fixture (`<slug>-2.html`) and add a parallel
`expected.json` entry, leaving the old one in place until the next
major release.

## Running the tests

```bash
# All fixtures
python3 -m pytest tests/test_screenshot_e2e.py -v

# Specific platform
python3 -m pytest tests/test_screenshot_e2e.py -v -k "github"
```

The test module skips gracefully when Playwright Chromium isn't
installed. Install via:

```bash
shot-scraper install     # or: playwright install chromium
```

`scripts/doctor.py check` warns if Chromium is missing.
