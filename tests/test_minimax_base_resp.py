"""Regression: Minimax returns HTTP 200 with a base_resp object on logical
errors (rate limit, auth, balance). MinimaxProvider.generate only checked
status_code >= 400, so a 200+base_resp error fell through to NoImageDataError —
treated by the fallback chain as a recoverable "try next model", hiding the real
error and never triggering the rate-limit backoff.
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import image_providers  # noqa: E402
from image_providers import MinimaxProvider, NoImageDataError  # noqa: E402


class _FakeResp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")


def _patch_post(monkeypatch, payload, status=200):
    monkeypatch.setattr(
        image_providers.requests, "post",
        lambda *a, **k: _FakeResp(status, payload),
    )


def test_base_resp_rate_limit_surfaces_as_rate_limit(monkeypatch, tmp_path):
    _patch_post(monkeypatch, {"base_resp": {"status_code": 1002, "status_msg": "触发限流"}})
    with pytest.raises(RuntimeError) as ei:
        MinimaxProvider().generate("minimax-image-01", "p", tmp_path / "o.png")
    msg = str(ei.value).lower()
    # The caller detects rate limits by string-matching the error message, so a
    # Minimax rate-limit must carry a recognizable token.
    assert ("rate limit" in msg) or ("429" in msg), msg


def test_base_resp_hard_error_is_not_swallowed_as_no_image(monkeypatch, tmp_path):
    _patch_post(monkeypatch, {"base_resp": {"status_code": 1004, "status_msg": "auth failed"}})
    # NoImageDataError is recoverable ("try next model"). A real base_resp error
    # must surface as a RuntimeError instead.
    with pytest.raises(RuntimeError):
        MinimaxProvider().generate("minimax-image-01", "p", tmp_path / "o.png")


def test_base_resp_success_still_needs_image_data(monkeypatch, tmp_path):
    # status_code 0 == success; with no image payload it's still NoImageDataError.
    _patch_post(monkeypatch, {"base_resp": {"status_code": 0, "status_msg": "success"}, "data": {}})
    with pytest.raises(NoImageDataError):
        MinimaxProvider().generate("minimax-image-01", "p", tmp_path / "o.png")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
