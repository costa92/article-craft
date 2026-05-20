"""Tests for B13 — filter_chain_by_available_keys.

The pre-v1.6.9 default chain is ``[minimax, gemini-3, gemini-3.1, gemini-2.5]``.
A user with only ``GEMINI_API_KEY`` would see Minimax tried first on every
image, fail with an auth error, then fall through. These tests pin the
filter so that wasted attempt is gone — and gone defensively (env var
OR env.json both honored, unknown providers passed through, empty
result surfaced cleanly).
"""

import importlib.util
import os
import sys
from pathlib import Path
from unittest import mock


def _load_config():
    p = Path(__file__).resolve().parents[1] / "scripts" / "config.py"
    if str(p.parent) not in sys.path:
        sys.path.insert(0, str(p.parent))
    spec = importlib.util.spec_from_file_location("config_filter_test", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["config_filter_test"] = mod
    spec.loader.exec_module(mod)
    return mod


config = _load_config()

# The default chain (pinned here so we don't break if MODEL_FALLBACK_CHAIN
# expands — these tests target the FILTER, not the chain contents).
CHAIN = [
    "minimax-image-01",
    "gemini-3-pro-image-preview",
    "gemini-3.1-flash-image-preview",
    "gemini-2.5-flash-image",
]


def _clear_keys(monkeypatch):
    """Strip any inherited keys from env and module-level user config."""
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(config, "_user_config", {})


def test_both_keys_present_keeps_full_chain(monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setenv("MINIMAX_API_KEY", "mxxx")
    monkeypatch.setenv("GEMINI_API_KEY", "gyyy")
    assert config.filter_chain_by_available_keys(CHAIN) == CHAIN


def test_only_gemini_drops_minimax(monkeypatch):
    """The headline B13 scenario."""
    _clear_keys(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "gyyy")
    result = config.filter_chain_by_available_keys(CHAIN)
    assert "minimax-image-01" not in result
    assert all(m.startswith("gemini") for m in result)
    assert len(result) == 3


def test_only_minimax_drops_all_gemini(monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setenv("MINIMAX_API_KEY", "mxxx")
    result = config.filter_chain_by_available_keys(CHAIN)
    assert result == ["minimax-image-01"]


def test_neither_key_returns_empty(monkeypatch):
    """Empty → callers fail fast with a clear error."""
    _clear_keys(monkeypatch)
    assert config.filter_chain_by_available_keys(CHAIN) == []


def test_env_json_key_alone_is_honored(monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setattr(config, "_user_config", {"gemini_api_key": "from-env-json"})
    result = config.filter_chain_by_available_keys(CHAIN)
    assert "minimax-image-01" not in result
    assert len(result) == 3  # all 3 gemini variants


def test_env_var_overrides_missing_env_json(monkeypatch):
    """Env var is sufficient even if env.json doesn't have the key."""
    _clear_keys(monkeypatch)
    monkeypatch.setenv("MINIMAX_API_KEY", "mxxx")
    # env.json has gemini key only
    monkeypatch.setattr(config, "_user_config", {"gemini_api_key": "g"})
    assert config.filter_chain_by_available_keys(CHAIN) == CHAIN


def test_preserves_chain_order(monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setenv("MINIMAX_API_KEY", "m")
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    # Custom order — user explicitly picked gemini-2.5 first
    custom = [
        "gemini-2.5-flash-image",
        "minimax-image-01",
        "gemini-3-pro-image-preview",
    ]
    assert config.filter_chain_by_available_keys(custom) == custom


def test_unknown_prefix_passes_through(monkeypatch):
    """Forward-compat: future providers (Qiniu, DALL-E, Flux) aren't
    arbitrarily dropped by the filter — they get their own key check
    when wired up. Today they just sail through."""
    _clear_keys(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    chain = ["openai-dalle-3", "gemini-3-pro-image-preview", "minimax-image-01"]
    result = config.filter_chain_by_available_keys(chain)
    # openai-dalle-3 kept (unknown prefix), gemini kept, minimax dropped
    assert result == ["openai-dalle-3", "gemini-3-pro-image-preview"]


def test_empty_string_key_is_treated_as_missing(monkeypatch):
    """env.json with `"minimax_api_key": ""` should still drop minimax."""
    _clear_keys(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setattr(
        config,
        "_user_config",
        {"minimax_api_key": "", "gemini_api_key": "g-from-json"},
    )
    result = config.filter_chain_by_available_keys(CHAIN)
    assert "minimax-image-01" not in result


def test_empty_input_chain_returns_empty(monkeypatch):
    _clear_keys(monkeypatch)
    monkeypatch.setenv("MINIMAX_API_KEY", "m")
    assert config.filter_chain_by_available_keys([]) == []
