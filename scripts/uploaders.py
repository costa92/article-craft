"""Shared CDN upload helpers (B2).

Background
----------
Before this module existed, both ``screenshot_tool.upload_to_cdn`` and
``generate_and_upload_images.upload_to_picgo`` parsed PicGo's CLI output
with their own slightly-divergent regex/JSON heuristics. v1.5.2 fixed
one parser (after a multi-line `[PicGo INFO]` log silently broke
screenshot uploads); the other had a different bug shape and wasn't
caught at the same time. Any new uploader backend (Qiniu, imgbb, …)
would have to know about both call sites.

This module centralizes the parsing into a single function
(``parse_picgo_output``) that both callers route through. The full
uploader implementations stay where they are — the retry-wrapped PicGo
flow in ``generate_and_upload_images``, the leniant fallback in
``screenshot_tool`` — because their callers have very different error
contracts (image-gen raises, screenshot returns local path on failure).
Unifying the *parser* fixes the historical fragility without touching
the working retry/contract code.

The ``Uploader`` Protocol below is a placeholder for future Qiniu /
imgbb / SMMS backends to slot into; current code doesn't depend on it.
"""

from __future__ import annotations

import json
from typing import Optional, Protocol, runtime_checkable


def parse_picgo_output(stdout: str) -> Optional[str]:
    """Extract a CDN URL from PicGo CLI output.

    Two parsing strategies, in order:

    1. **Line scan for ``http(s)://``** — matches PicGo's actual current
       output: multi-line ``[PicGo INFO]`` log followed by a bare URL
       line. This is the path that historically broke when one parser
       skipped to strategy 2 too eagerly.
    2. **JSON fallback** — handles the hypothetical case where PicGo
       changes its output format. Accepts both ``{"url": "..."}`` and
       ``[{"url": "..."}]`` shapes seen in plugin variants.

    Returns the URL string or ``None`` if neither strategy finds one.
    Callers decide what to do with ``None`` (raise for fail-fast paths,
    return local path for lenient ones).
    """
    if not stdout:
        return None

    # Strategy 1: per-line URL scan — current PicGo behavior.
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("http://") or stripped.startswith("https://"):
            return stripped

    # Strategy 2: JSON fallback — future-proof.
    try:
        data = json.loads(stdout.strip())
    except (json.JSONDecodeError, ValueError):
        return None

    if isinstance(data, dict):
        url = data.get("url")
        return url if isinstance(url, str) else None
    if isinstance(data, list) and data and isinstance(data[0], dict):
        url = data[0].get("url")
        return url if isinstance(url, str) else None

    return None


@runtime_checkable
class Uploader(Protocol):
    """Protocol for CDN upload backends (future extension point).

    Current implementations live in ``generate_and_upload_images.py``
    (``upload_to_picgo`` / ``upload_to_s3``) and ``screenshot_tool.py``
    (``upload_to_cdn``) for backward compatibility. Future backends
    (Qiniu, imgbb, SMMS, GitHub raw, etc.) should implement this
    protocol and register through a new ``get_uploader()`` factory
    rather than adding more branches to ``upload_image``.

    Contract:
        ``upload(local_path)`` returns a public CDN URL on success.
        Implementations raise ``RuntimeError`` on failure — lenient
        callers (screenshot) catch and fall back to the local path.
    """

    def upload(self, local_path: str) -> str:
        ...
