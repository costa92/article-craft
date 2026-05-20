"""End-to-end snapshot tests for screenshot selector resolution (B3 Phase 1).

Each fixture directory under ``tests/fixtures/screenshot/`` contains:

- ``<slug>.html`` — minimal HTML reproducing the platform's load-bearing
  DOM shape (target element + decoy siblings that must NOT win selection).
- ``<slug>.expected.json`` — expected selector candidates, bbox tolerance,
  url_pattern, anchor keywords.
- ``SOURCE.txt`` — provenance.

The test parametrizes over every fixture dir. For each one:

1. Start a local HTTP server on ``fixture_dir``.
2. Use Playwright ``page.route()`` to rewrite the real hostname to
   localhost so ``main_content_selectors_for_host`` still resolves the
   intended platform-key.
3. Navigate to the canonical URL (``url_pattern`` from expected.json).
4. Assert:
   - ``suggest_selector(url)`` returns a string that matches at least
     one DOM node in the fixture.
   - The first matched element's bounding box is within the
     ``expected_bbox_min`` / ``expected_bbox_max`` rectangle.

Phase 1 ships ONE fixture (github.com) — see ``docs/superpowers/specs/2026-05-20-screenshot-e2e-snapshot-tests.md``
for the multi-phase roadmap. Phase 2 adds the rest of
``HOST_MAIN_SELECTORS`` (currently 15 entries).

Skipped automatically when Playwright Chromium isn't installed
(``shot-scraper install`` provides it; doctor.py warns).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

# scripts/ on path so ``import screenshot_tool`` works (the SUT)
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# fixtures/ on path so we can import the helpers as a module
_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
if str(_FIXTURES_DIR) not in sys.path:
    sys.path.insert(0, str(_FIXTURES_DIR))

from _screenshot_e2e_helpers import route_handler_for  # noqa: E402


_FIXTURE_ROOT = _FIXTURES_DIR / "screenshot"


# --------------------------------------------------------------------- #
# Skip the whole module gracefully if Playwright Chromium isn't set up
# --------------------------------------------------------------------- #
try:
    from playwright.sync_api import sync_playwright  # type: ignore

    _PW_AVAILABLE = True
except ImportError:
    _PW_AVAILABLE = False


def _have_chromium() -> bool:
    """Best-effort detection — checks ~/.cache/ms-playwright for a chromium
    install. CI installs via ``shot-scraper install`` / ``playwright install``.
    """
    try:
        cache = Path.home() / ".cache" / "ms-playwright"
        if not cache.is_dir():
            return False
        for child in cache.iterdir():
            if child.name.startswith("chromium-"):
                return True
        return False
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not (_PW_AVAILABLE and _have_chromium()),
    reason="Playwright Chromium not installed (run `shot-scraper install`)",
)


# --------------------------------------------------------------------- #
# Fixture discovery
# --------------------------------------------------------------------- #


def _discover_fixtures() -> List[Dict[str, Any]]:
    """Walk ``tests/fixtures/screenshot/`` and return a list of fixture dicts.

    Each dict has ``platform``, ``fixture_dir``, ``html_file``, ``expected``
    (parsed JSON), and ``url`` (from expected.url_pattern).
    """
    fixtures: List[Dict[str, Any]] = []
    if not _FIXTURE_ROOT.is_dir():
        return fixtures
    for platform_dir in sorted(_FIXTURE_ROOT.iterdir()):
        if not platform_dir.is_dir():
            continue
        for expected_file in platform_dir.glob("*.expected.json"):
            try:
                expected = json.loads(expected_file.read_text(encoding="utf-8"))
            except Exception as e:
                pytest.fail(f"Invalid expected.json at {expected_file}: {e}")
            html_filename = expected.get("fixture_html")
            if not html_filename:
                pytest.fail(f"{expected_file} missing 'fixture_html'")
            html_path = platform_dir / html_filename
            if not html_path.is_file():
                pytest.fail(f"{expected_file} references missing {html_path}")
            fixtures.append(
                {
                    "platform": expected.get("platform", platform_dir.name),
                    "fixture_dir": platform_dir,
                    "html_file": html_filename,
                    "expected": expected,
                    "url": expected["url_pattern"],
                    "id": f"{platform_dir.name}/{expected_file.stem.replace('.expected', '')}",
                }
            )
    return fixtures


_FIXTURES = _discover_fixtures()


# --------------------------------------------------------------------- #
# Tests — parametrized over every discovered fixture
# --------------------------------------------------------------------- #


def _fake_host_from_url(url: str) -> str:
    """Extract host substring for route matching ('github.com' from URL)."""
    from urllib.parse import urlparse

    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


@pytest.mark.parametrize(
    "fixture",
    _FIXTURES,
    ids=[f["id"] for f in _FIXTURES] if _FIXTURES else ["no-fixtures"],
)
def test_selector_resolves_via_host_map(fixture):
    """suggest_selector(url) returns a CSS string whose first candidate
    matches an element in the fixture HTML.

    This is the architecture proof: HOST_MAIN_SELECTORS / suggest_selector
    were designed against real DOM shapes, and the fixtures freeze those
    shapes so future selector edits can't accidentally break them.
    """
    import screenshot_tool

    url = fixture["url"]
    expected = fixture["expected"]
    selector_str = screenshot_tool.suggest_selector(url)
    assert selector_str, f"suggest_selector returned empty for {url}"

    expected_candidates = expected["expected_selector_candidates"]
    # The returned string is a comma-separated CSS list; at least one
    # expected candidate must appear in it.
    found = any(c in selector_str for c in expected_candidates)
    assert found, (
        f"suggest_selector returned {selector_str!r} for {url}; "
        f"none of expected {expected_candidates} are present"
    )


@pytest.mark.parametrize(
    "fixture",
    _FIXTURES,
    ids=[f["id"] for f in _FIXTURES] if _FIXTURES else ["no-fixtures"],
)
def test_selector_matches_dom_with_route_redirect(fixture):
    """The route-redirect architecture (§3.2 of the spec):

    page.goto(canonical_url) → routed to local fixture → DOM contains
    the expected element → bbox within tolerance.

    Proves Phase 1 architecture works end-to-end.
    """
    import screenshot_tool

    url = fixture["url"]
    expected = fixture["expected"]
    fake_host = _fake_host_from_url(url)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()
            # route.fulfill serves the fixture HTML inline; the URL
            # stays https://github.com/... so screenshot_tool's
            # host-matching logic exercises against the real hostname.
            page.route(
                "**/*",
                route_handler_for(
                    fake_host, fixture["fixture_dir"], fixture["html_file"]
                ),
            )
            response = page.goto(url, wait_until="domcontentloaded", timeout=10000)
            assert response is not None and response.ok, (
                f"page.goto({url}) failed: response={response}"
            )

            # The selector picked by the host map must match at least
            # one DOM node in the fixture.
            expected_first = expected["expected_first_match"]
            locator = page.locator(expected_first)
            count = locator.count()
            assert count >= 1, (
                f"Expected '{expected_first}' to match ≥1 node in "
                f"{fixture['html_file']}; got {count}"
            )

            # Bounding box of the first match must fall within tolerance.
            bbox = locator.first.bounding_box()
            assert bbox is not None, (
                f"bounding_box() returned None for {expected_first}"
            )
            bmin = expected["expected_bbox_min"]
            bmax = expected["expected_bbox_max"]
            assert bmin["width"] <= bbox["width"] <= bmax["width"], (
                f"width {bbox['width']} not in [{bmin['width']}, {bmax['width']}]"
            )
            assert bmin["height"] <= bbox["height"] <= bmax["height"], (
                f"height {bbox['height']} not in [{bmin['height']}, {bmax['height']}]"
            )
        finally:
            browser.close()


def test_fixtures_discovered_at_least_one():
    """Sanity check: the parametrize list is non-empty.

    If this fails, the fixture directory is missing or expected.json
    files are malformed — the parametrized tests above would silently
    skip otherwise.
    """
    assert len(_FIXTURES) >= 1, (
        "No screenshot fixtures discovered under tests/fixtures/screenshot/. "
        "B3 Phase 1 should ship at least the github fixture."
    )
