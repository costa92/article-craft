"""Helpers for screenshot E2E snapshot tests (B3 Phase 1).

Provides:
- :class:`FixtureServer` — a ThreadingHTTPServer wrapper that serves a
  single fixture directory on an ephemeral port.
- :func:`route_handler_for` — Playwright route callback that rewrites
  requests for ``fake_host`` to ``http://localhost:<port>/...``, leaving
  every other request untouched. Combined with the server, this lets a
  test ``page.goto("https://github.com/example/repo")`` against fixture
  HTML while ``main_content_selectors_for_host`` still resolves
  "github.com" → the right selector dict.

Architecture (see ``docs/superpowers/specs/2026-05-20-screenshot-e2e-snapshot-tests.md`` §3.2):

  capture flow goes:

    page.goto("https://github.com/foo/bar")
      → route handler rewrites to http://localhost:PORT/<fixture>.html
      → Playwright fetches local content; URL stays github.com
      → main_content_selectors_for_host(url) resolves "github.com" → selectors
      → assertions: selector match in DOM, bbox within tolerance

The local server is intentionally **stdlib-only** — no extra dependency
just to flip-flop request paths.
"""
from __future__ import annotations

import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Optional


class FixtureServer:
    """Ephemeral-port HTTP server scoped to a single fixture directory.

    Usage::

        server = FixtureServer(Path("tests/fixtures/screenshot/github"))
        server.start()
        try:
            ...  # exercise tests
        finally:
            server.stop()

    Or via context manager::

        with FixtureServer(fixture_dir) as server:
            url = f"http://localhost:{server.port}/repo-readme.html"
            ...
    """

    def __init__(self, fixture_dir: Path):
        self.fixture_dir = fixture_dir.resolve()
        if not self.fixture_dir.is_dir():
            raise ValueError(f"Fixture directory not found: {self.fixture_dir}")
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def port(self) -> int:
        if self._server is None:
            raise RuntimeError("Server not started — call start() first")
        return self._server.server_address[1]

    def start(self) -> "FixtureServer":
        # Bind to localhost only; ephemeral port (0 → OS picks).
        directory = str(self.fixture_dir)

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=directory, **kwargs)

            def log_message(self, fmt, *args):  # silence per-request stderr
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def __enter__(self) -> "FixtureServer":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()


def route_handler_for(
    fake_host: str, fixture_dir: Path, fixture_filename: str
) -> Callable:
    """Build a Playwright route callback that fulfills ``fake_host`` requests
    with content from a local fixture file.

    Uses ``route.fulfill()`` (NOT ``route.continue_(url=...)``) because
    Playwright rejects URL rewrites that change the protocol scheme
    (``https`` → ``http``) for security reasons. ``fulfill()`` serves
    the response body inline, so the page's URL stays ``https://github.com/...``
    while the bytes come from disk.

    Subresource requests (CSS / fonts / images embedded in the fixture
    HTML) are aborted — keeps the test hermetic, no network calls.

    Why fixture_filename: real platform URLs have arbitrary paths
    (``/example/repo``, ``/example/repo/issues/12``). The fixture
    directory holds a single HTML file per scenario; the handler always
    serves that one file regardless of request path. Per-scenario
    routing is the caller's job (use a different handler per fixture).
    """
    html_path = (fixture_dir / fixture_filename).resolve()
    if not html_path.is_file():
        raise ValueError(f"Fixture HTML not found: {html_path}")
    html_body = html_path.read_text(encoding="utf-8")

    def handler(route, request) -> None:
        url = request.url
        # Only fulfill the top-level document navigation. Sub-resources
        # (favicon, fonts, the production CSS bundle) get aborted —
        # the fixture HTML embeds its own minimal <style> so the page
        # renders without them.
        if fake_host in url and request.resource_type == "document":
            route.fulfill(
                status=200,
                content_type="text/html; charset=utf-8",
                body=html_body,
            )
        elif fake_host in url:
            route.abort()
        else:
            # Off-host requests — abort to keep the test offline.
            route.abort()

    return handler


__all__ = ["FixtureServer", "route_handler_for"]
