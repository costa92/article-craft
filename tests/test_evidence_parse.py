"""Tests for scripts/evidence.parse_materials (B9).

`parse_materials` is the only pure deterministic function in
evidence.py — it reads materials.md and bucket-sorts entries into
public / local / gated. The harvest + collect functions are mostly
I/O glue and are exercised through the orchestrator flow; this file
pins the parser semantics that prose authors actually see.
"""

import importlib.util
import sys
import tempfile
from pathlib import Path

import pytest


def _load():
    p = Path(__file__).resolve().parents[1] / "scripts" / "evidence.py"
    if str(p.parent) not in sys.path:
        sys.path.insert(0, str(p.parent))
    spec = importlib.util.spec_from_file_location("evidence_test_mod", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["evidence_test_mod"] = mod
    spec.loader.exec_module(mod)
    return mod


ev = _load()


def _write(tmp: Path, text: str) -> str:
    p = tmp / "materials.md"
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        ev.parse_materials(str(tmp_path / "nope.md"))


def test_url_under_default_section_goes_to_public(tmp_path):
    path = _write(tmp_path, "- https://example.com/a\n")
    result = ev.parse_materials(path)
    assert len(result["public"]) == 1
    assert result["public"][0]["url"] == "https://example.com/a"
    assert result["local"] == []
    assert result["gated"] == []


def test_explicit_public_section(tmp_path):
    path = _write(
        tmp_path,
        "## 公开\n- https://example.com/x\n- https://example.com/y\n",
    )
    result = ev.parse_materials(path)
    assert len(result["public"]) == 2


def test_local_section_keeps_absolute_paths(tmp_path):
    path = _write(
        tmp_path,
        "## 本地\n- /abs/path/img.png\n- relative/skipped.png\n",
    )
    result = ev.parse_materials(path)
    assert len(result["local"]) == 1
    assert result["local"][0]["path"] == "/abs/path/img.png"


def test_gated_section_routes_to_gated(tmp_path):
    path = _write(
        tmp_path,
        '## 付费\n- https://example.com/paywall tier=T2 note="会员可见"\n',
    )
    result = ev.parse_materials(path)
    assert len(result["gated"]) == 1
    assert result["gated"][0]["url"] == "https://example.com/paywall"
    assert result["gated"][0]["tier"] == "T2"


def test_tier_and_note_parsing(tmp_path):
    """tier= takes a bare value; note=/desc= require double quotes."""
    path = _write(
        tmp_path,
        '- https://example.com/x tier=T1 note="官方文档"\n',
    )
    result = ev.parse_materials(path)
    entry = result["public"][0]
    assert entry["tier"] == "T1"
    assert entry["note"] == "官方文档"


def test_default_tier_is_t5(tmp_path):
    """Entries with no explicit tier default to T5 (least trusted)."""
    path = _write(tmp_path, "- https://example.com/x\n")
    assert result_tier(ev, tmp_path, "- https://example.com/x\n") == "T5"


def result_tier(ev_mod, tmp_path, contents):
    p = tmp_path / f"materials_{len(contents)}.md"
    p.write_text(contents, encoding="utf-8")
    return ev_mod.parse_materials(str(p))["public"][0]["tier"]


def test_unknown_section_routes_to_public(tmp_path):
    """Unrecognized ## headers fall back to public (URL-or-not then re-sorted)."""
    path = _write(
        tmp_path,
        "## 闲谈\n- https://example.com/z\n",
    )
    result = ev.parse_materials(path)
    assert len(result["public"]) == 1


def test_comments_and_blank_lines_skipped(tmp_path):
    path = _write(
        tmp_path,
        "\n# This is a heading-comment\n\n- https://example.com/a\n\n",
    )
    result = ev.parse_materials(path)
    assert len(result["public"]) == 1


def test_bullet_prefix_variants(tmp_path):
    """Both `- ` and `* ` bullet styles accepted."""
    path = _write(
        tmp_path,
        "- https://example.com/dash\n* https://example.com/star\n",
    )
    result = ev.parse_materials(path)
    urls = {e["url"] for e in result["public"]}
    assert urls == {"https://example.com/dash", "https://example.com/star"}


def test_trailing_punctuation_stripped(tmp_path):
    """URLs with trailing comma/period/semicolon get cleaned."""
    path = _write(tmp_path, "- https://example.com/a.\n- https://example.com/b,\n")
    result = ev.parse_materials(path)
    urls = {e["url"] for e in result["public"]}
    assert urls == {"https://example.com/a", "https://example.com/b"}


def test_alt_local_section_names(tmp_path):
    """`local` / `manual` / `screenshot` headers all route to local bucket."""
    for header in ("## local", "## manual", "## screenshot"):
        path = _write(tmp_path, f"{header}\n- /abs/img.png\n")
        result = ev.parse_materials(path)
        assert len(result["local"]) == 1


def test_alt_gated_section_names(tmp_path):
    """`gated` / `paywall` / `墙` all route to gated bucket."""
    for header in ("## gated", "## paywall", "## 登录墙"):
        path = _write(tmp_path, f"{header}\n- https://example.com/x\n")
        result = ev.parse_materials(path)
        assert len(result["gated"]) == 1
