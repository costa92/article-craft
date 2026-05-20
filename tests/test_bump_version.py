"""Tests for scripts/bump_version.py (B9).

`bump_version.py` is the release tooling — if its arg parsing or
version arithmetic ever regressed, every future release would land
broken plugin.json. Pin the pure-function surface; the file-mutation
helpers (update_plugin_json, etc.) are tested through actual releases.
"""

import argparse
import importlib.util
import sys
from pathlib import Path

import pytest


def _load():
    p = Path(__file__).resolve().parents[1] / "scripts" / "bump_version.py"
    if str(p.parent) not in sys.path:
        sys.path.insert(0, str(p.parent))
    spec = importlib.util.spec_from_file_location("bump_version_test", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["bump_version_test"] = mod
    spec.loader.exec_module(mod)
    return mod


bv = _load()


# --- bump_version() arithmetic ---


@pytest.mark.parametrize(
    "current,bump,expected",
    [
        ("1.6.9", "patch", "1.6.10"),
        ("1.6.10", "patch", "1.6.11"),
        ("1.6.9", "minor", "1.7.0"),
        ("1.6.9", "major", "2.0.0"),
        ("0.0.1", "patch", "0.0.2"),
        ("9.9.9", "major", "10.0.0"),
    ],
)
def test_bump_version_arithmetic(current, bump, expected):
    assert bv.bump_version(current, bump) == expected


def test_bump_version_rejects_wrong_arity():
    """Less than or more than 3 dot-parts triggers the format check."""
    with pytest.raises(ValueError, match="Invalid version format"):
        bv.bump_version("1.6", "patch")
    with pytest.raises(ValueError, match="Invalid version format"):
        bv.bump_version("1.6.9.0", "patch")


def test_bump_version_rejects_non_numeric_parts():
    """3 parts but non-numeric (e.g. 'v1.6.9') hits int() conversion."""
    with pytest.raises(ValueError):
        bv.bump_version("v1.6.9", "patch")
    with pytest.raises(ValueError):
        bv.bump_version("1.x.9", "patch")


def test_bump_version_rejects_unknown_bump_type():
    with pytest.raises(ValueError, match="Unknown bump type"):
        bv.bump_version("1.6.9", "yolo")


# --- parse_bump_arg() CLI arg validation ---


def test_parse_bump_arg_accepts_keywords():
    assert bv.parse_bump_arg("major") == "major"
    assert bv.parse_bump_arg("minor") == "minor"
    assert bv.parse_bump_arg("patch") == "patch"


def test_parse_bump_arg_accepts_explicit_version():
    assert bv.parse_bump_arg("1.6.9") == "1.6.9"
    assert bv.parse_bump_arg("0.0.1") == "0.0.1"
    assert bv.parse_bump_arg("99.99.99") == "99.99.99"


def test_parse_bump_arg_rejects_garbage():
    with pytest.raises(argparse.ArgumentTypeError):
        bv.parse_bump_arg("v1.6.9")  # leading 'v'
    with pytest.raises(argparse.ArgumentTypeError):
        bv.parse_bump_arg("1.6")  # only 2 parts
    with pytest.raises(argparse.ArgumentTypeError):
        bv.parse_bump_arg("nope")
    with pytest.raises(argparse.ArgumentTypeError):
        bv.parse_bump_arg("1.6.9-rc1")  # no pre-release strings (yet)


# --- get_current_version() smoke test ---


def test_get_current_version_returns_semver():
    """plugin.json must always be readable + parse as semver."""
    v = bv.get_current_version()
    parts = v.split(".")
    assert len(parts) == 3
    for p in parts:
        int(p)  # raises if non-numeric


def test_get_current_version_matches_marketplace():
    """plugin.json and marketplace.json must agree — they're updated
    in lockstep by update_plugin_json + update_marketplace_json."""
    import json as _json
    repo = Path(__file__).resolve().parents[1]
    plugin_v = _json.loads((repo / ".claude-plugin" / "plugin.json").read_text())["version"]
    mp = _json.loads((repo / ".claude-plugin" / "marketplace.json").read_text())
    # marketplace.json structure: plugins[0].version
    mp_v = mp["plugins"][0]["version"]
    assert plugin_v == mp_v, (
        f"plugin.json says {plugin_v} but marketplace.json says {mp_v} — "
        f"bump_version.py update_plugin_json/update_marketplace_json out of sync"
    )
