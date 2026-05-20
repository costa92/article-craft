"""Tests for the image-provider registry (B7 Phase 1).

Pins:
- The Protocol contract every provider must satisfy
- Registry lookup (``for_model`` resolves models to providers, returns
  ``None`` for unknown models)
- ``is_configured()`` honors both env var AND env.json
- ``configured_providers()`` filters by the same gate
- Round-trip: ``filter_chain_by_available_keys`` consults the registry
- Provider error semantics (HTTP 4xx → RuntimeError, missing image data
  → NoImageDataError) — the contract callers rely on for fallback

Notably the actual API calls are mocked — these tests should run in
under a second with no network.
"""

import os
import sys
from pathlib import Path
from unittest import mock

import pytest

# scripts/ on path so `import image_providers` resolves cleanly.
_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import config  # noqa: E402
import image_providers  # noqa: E402
from image_providers import (  # noqa: E402
    GeminiProvider,
    ImageProvider,
    MinimaxProvider,
    NoImageDataError,
    all_providers,
    configured_providers,
    for_model,
    register,
    unregister,
)


# --------------------------------------------------------------------- #
# Protocol contract
# --------------------------------------------------------------------- #


def test_minimax_satisfies_protocol():
    """`isinstance(p, ImageProvider)` works via @runtime_checkable."""
    assert isinstance(MinimaxProvider(), ImageProvider)


def test_gemini_satisfies_protocol():
    assert isinstance(GeminiProvider(), ImageProvider)


def test_protocol_rejects_random_object():
    """A bare object missing the required attrs is not a provider."""

    class Dummy:
        pass

    assert not isinstance(Dummy(), ImageProvider)


# --------------------------------------------------------------------- #
# Registry — lookup, listing, registration
# --------------------------------------------------------------------- #


def test_for_model_resolves_minimax():
    assert for_model("minimax-image-01").name == "minimax"


def test_for_model_resolves_all_gemini_variants():
    for m in (
        "gemini-3-pro-image-preview",
        "gemini-3.1-flash-image-preview",
        "gemini-2.5-flash-image",
    ):
        assert for_model(m).name == "gemini", m


def test_for_model_unknown_returns_none():
    assert for_model("openai-dalle-99") is None
    assert for_model("totally-made-up") is None


def test_all_providers_lists_both_built_ins():
    names = [p.name for p in all_providers()]
    assert "minimax" in names
    assert "gemini" in names


def test_register_and_unregister_round_trip():
    """Forks add providers by subclass + register. Test that lifecycle."""

    class FakeProvider:
        name = "test-fake"

        def model_names(self):
            return ["fake-model-99"]

        def is_configured(self):
            return True

        def generate(self, *args, **kwargs):
            raise RuntimeError("fake provider — should not be called")

    fake = FakeProvider()
    register(fake)
    try:
        assert for_model("fake-model-99") is fake
        assert "test-fake" in [p.name for p in all_providers()]
    finally:
        unregister("test-fake")

    # Post-unregister: gone.
    assert for_model("fake-model-99") is None


def test_re_register_same_name_replaces():
    """``register(SameNameProvider())`` overwrites — supports test doubles."""
    original = MinimaxProvider()

    class FakeMinimax:
        name = "minimax"

        def model_names(self):
            return ["minimax-image-01"]

        def is_configured(self):
            return False

        def generate(self, *a, **kw):
            return None

    fake = FakeMinimax()
    register(fake)
    try:
        # for_model should resolve to the fake now.
        assert for_model("minimax-image-01") is fake
    finally:
        # Restore the canonical provider.
        register(original)
    assert for_model("minimax-image-01") is original


# --------------------------------------------------------------------- #
# is_configured — env var + env.json honored
# --------------------------------------------------------------------- #


def _clear_keys(monkeypatch):
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(config, "_user_config", {})


def test_minimax_is_configured_from_env_var(monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setenv("MINIMAX_API_KEY", "mxxx")
    assert MinimaxProvider().is_configured() is True


def test_minimax_is_configured_from_env_json(monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setattr(config, "_user_config", {"minimax_api_key": "mxxx"})
    assert MinimaxProvider().is_configured() is True


def test_minimax_not_configured_when_both_empty(monkeypatch):
    _clear_keys(monkeypatch)
    assert MinimaxProvider().is_configured() is False


def test_minimax_empty_string_env_json_treated_as_missing(monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setattr(config, "_user_config", {"minimax_api_key": ""})
    assert MinimaxProvider().is_configured() is False


def test_gemini_is_configured_from_env_var(monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "gyyy")
    assert GeminiProvider().is_configured() is True


def test_gemini_is_configured_from_env_json(monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setattr(config, "_user_config", {"gemini_api_key": "gyyy"})
    assert GeminiProvider().is_configured() is True


def test_gemini_not_configured_when_both_empty(monkeypatch):
    _clear_keys(monkeypatch)
    assert GeminiProvider().is_configured() is False


# --------------------------------------------------------------------- #
# configured_providers / chain filter integration
# --------------------------------------------------------------------- #


def test_configured_providers_filters_by_key_presence(monkeypatch):
    """When only one key is set, only that provider is configured."""
    _clear_keys(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    names = [p.name for p in configured_providers()]
    assert names == ["gemini"]


def test_configured_providers_empty_when_no_keys(monkeypatch):
    _clear_keys(monkeypatch)
    assert configured_providers() == []


def test_configured_providers_both_when_both_keys(monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setenv("MINIMAX_API_KEY", "m")
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    names = {p.name for p in configured_providers()}
    assert names == {"minimax", "gemini"}


def test_filter_chain_routes_through_registry(monkeypatch):
    """config.filter_chain_by_available_keys must consult the registry,
    not its old hardcoded prefix branches."""
    _clear_keys(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    chain = [
        "minimax-image-01",
        "gemini-3-pro-image-preview",
    ]
    result = config.filter_chain_by_available_keys(chain)
    assert result == ["gemini-3-pro-image-preview"]


# --------------------------------------------------------------------- #
# Provider error semantics
# --------------------------------------------------------------------- #


def test_minimax_raises_runtime_on_http_error(monkeypatch, tmp_path):
    """HTTP 4xx/5xx → RuntimeError with status code and excerpt."""
    monkeypatch.setenv("MINIMAX_API_KEY", "test")

    class FakeResponse:
        status_code = 429
        text = "rate limit exceeded"

        def json(self):
            return {"error": "rate limit"}

    with mock.patch.object(image_providers, "requests") as mock_requests:
        mock_requests.post.return_value = FakeResponse()
        with pytest.raises(RuntimeError) as exc_info:
            MinimaxProvider().generate(
                "minimax-image-01",
                "prompt",
                tmp_path / "out.png",
            )
    assert "429" in str(exc_info.value)


def test_minimax_raises_no_image_data_when_response_empty(monkeypatch, tmp_path):
    """No base64 + no image_urls → NoImageDataError (recoverable)."""
    monkeypatch.setenv("MINIMAX_API_KEY", "test")

    class FakeResponse:
        status_code = 200
        text = '{"data":{}}'

        def json(self):
            return {"data": {}}

    with mock.patch.object(image_providers, "requests") as mock_requests:
        mock_requests.post.return_value = FakeResponse()
        with pytest.raises(NoImageDataError):
            MinimaxProvider().generate(
                "minimax-image-01",
                "prompt",
                tmp_path / "out.png",
            )


def test_minimax_raises_when_key_missing(monkeypatch, tmp_path):
    """No key set → RuntimeError with clear message."""
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.setattr(config, "_user_config", {})
    with pytest.raises(RuntimeError) as exc_info:
        MinimaxProvider().generate(
            "minimax-image-01",
            "prompt",
            tmp_path / "out.png",
        )
    assert "MINIMAX_API_KEY" in str(exc_info.value)


def test_gemini_raises_when_key_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(config, "_user_config", {})
    with pytest.raises(RuntimeError) as exc_info:
        GeminiProvider().generate(
            "gemini-3-pro-image-preview",
            "prompt",
            tmp_path / "out.png",
        )
    assert "GEMINI_API_KEY" in str(exc_info.value)


# --------------------------------------------------------------------- #
# Model_names contract
# --------------------------------------------------------------------- #


def test_minimax_model_names_is_stable_list():
    assert MinimaxProvider().model_names() == ["minimax-image-01"]


def test_gemini_model_names_lists_three_variants():
    expected = {
        "gemini-3-pro-image-preview",
        "gemini-3.1-flash-image-preview",
        "gemini-2.5-flash-image",
    }
    assert set(GeminiProvider().model_names()) == expected


def test_model_names_do_not_overlap_across_providers():
    """Two providers claiming the same model would create ambiguity in
    ``for_model``."""
    seen = set()
    for provider in all_providers():
        for name in provider.model_names():
            assert name not in seen, f"{name} claimed by two providers"
            seen.add(name)
