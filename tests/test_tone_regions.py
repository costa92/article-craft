"""Tests for B10 — per-section tone override regions.

`<!-- tone:casual -->...<!-- /tone -->` markers in an article let the
author override the article-level tone for a span of prose. The
parser (`config.parse_tone_regions`) maps every line to a tone; the
lint integration (`lint_article.auto_fix_text`) applies the matching
tone's rewrite table per line.

These tests pin both layers — parser semantics + lint integration.
"""

import importlib.util
import sys
from pathlib import Path


def _load(name):
    p = Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py"
    if str(p.parent) not in sys.path:
        sys.path.insert(0, str(p.parent))
    spec = importlib.util.spec_from_file_location(f"{name}_b10_test", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"{name}_b10_test"] = mod
    spec.loader.exec_module(mod)
    return mod


config = _load("config")
lint = _load("lint_article")


# --- parse_tone_regions ---


def test_no_markers_returns_single_default_span():
    text = "line 1\nline 2\nline 3\n"
    # splitlines() yields 3 lines (no trailing empty for terminating \n).
    spans = config.parse_tone_regions(text, "neutral")
    assert spans == [(0, 3, "neutral")]


def test_empty_text_returns_empty_list():
    assert config.parse_tone_regions("", "neutral") == []


def test_single_region_splits_into_three_spans():
    text = (
        "before\n"
        "<!-- tone:casual -->\n"
        "inside casual\n"
        "<!-- /tone -->\n"
        "after\n"
    )
    spans = config.parse_tone_regions(text, "neutral")
    # Expected:
    #   line 0 ("before") → neutral
    #   line 1 (opener)   → neutral (marker line gets surrounding tone)
    #   line 2 ("inside") → casual
    #   line 3 (closer)   → casual (marker still inside region until processed)
    #   line 4 ("after")  → neutral
    #   line 5 (trailing empty from \n) → neutral
    assert (0, 2, "neutral") in spans  # before + opener
    assert (2, 4, "casual") in spans   # inside + closer
    assert any(t == "neutral" for _, _, t in spans[2:])  # after


def test_multiple_regions():
    text = (
        "a\n"
        "<!-- tone:casual -->\n"
        "b\n"
        "<!-- /tone -->\n"
        "c\n"
        "<!-- tone:opinionated -->\n"
        "d\n"
        "<!-- /tone -->\n"
        "e\n"
    )
    spans = config.parse_tone_regions(text, "neutral")
    tones_used = {t for _, _, t in spans}
    assert tones_used == {"neutral", "casual", "opinionated"}


def test_implicit_close_via_new_opener():
    """A <!-- tone:X --> while a region is open implicitly closes that region."""
    text = (
        "<!-- tone:casual -->\n"
        "casual line\n"
        "<!-- tone:opinionated -->\n"
        "opinionated line (without explicit /tone)\n"
    )
    spans = config.parse_tone_regions(text, "neutral")
    tone_for_line = {}
    for s, e, t in spans:
        for i in range(s, e):
            tone_for_line[i] = t
    # Line 1 ("casual line") in casual; line 3 in opinionated
    assert tone_for_line[1] == "casual"
    assert tone_for_line[3] == "opinionated"


def test_unclosed_region_extends_to_eof():
    text = "before\n<!-- tone:casual -->\ncasual to end\nmore casual\n"
    spans = config.parse_tone_regions(text, "neutral")
    last_span_tone = spans[-1][2]
    assert last_span_tone == "casual"


def test_unknown_tone_name_is_ignored():
    """Invalid tone name → marker is treated as plain text; region NOT opened."""
    text = (
        "default line\n"
        "<!-- tone:professionalish -->\n"
        "this should still be neutral\n"
    )
    spans = config.parse_tone_regions(text, "neutral")
    # All lines stay neutral
    tones = {t for _, _, t in spans}
    assert tones == {"neutral"}


def test_stray_close_marker_is_harmless():
    """A <!-- /tone --> with no prior opener — no-op, no crash."""
    text = "line a\n<!-- /tone -->\nline b\n"
    spans = config.parse_tone_regions(text, "neutral")
    assert all(t == "neutral" for _, _, t in spans)


def test_default_tone_fallback_to_neutral_for_invalid():
    """Caller passes garbage as default_tone → falls back to neutral."""
    text = "line\n"
    spans = config.parse_tone_regions(text, "fake_tone")
    assert spans[0][2] == "neutral"


def test_marker_with_extra_whitespace():
    """Tolerant of `<!--  tone:casual  -->` etc."""
    text = "<!--    tone:casual    -->\nbody\n<!--  /tone  -->\n"
    spans = config.parse_tone_regions(text, "neutral")
    tones_used = {t for _, _, t in spans}
    assert "casual" in tones_used


# --- lint_article integration ---


def test_lint_applies_default_tone_outside_region(monkeypatch):
    """Article with no region markers behaves as before — single tone.

    Note: ``在某种意义上 → 其实`` lives in the *casual* tier
    (TONE_LEXICAL_REWRITES["casual"]), not neutral. So we use casual as
    article tone to exercise the rewrite path.
    """
    text = "在某种意义上，这个设计很有趣。\n"
    fixed, stats, warnings = lint.auto_fix_text(text, tone="casual")
    assert "其实" in fixed
    assert "在某种意义上" not in fixed
    assert stats["rewrote_red_flag"] >= 1


def test_lint_applies_region_tone_inside_region():
    """Inside <!-- tone:casual -->, lint uses casual rewrites — even when
    the article-level tone is neutral and wouldn't apply them.

    `在某种意义上 → 其实` is a casual-tier rule5 rewrite, NOT present in
    the neutral tier. So we can verify region tone won over article tone
    by checking the rewrite happened.
    """
    text = (
        "<!-- tone:casual -->\n"
        "在某种意义上，这是区域内。\n"
        "<!-- /tone -->\n"
    )
    fixed, stats, _ = lint.auto_fix_text(text, tone="neutral")
    assert "其实" in fixed
    assert "在某种意义上" not in fixed
    # The region markers themselves must be preserved verbatim.
    assert "<!-- tone:casual -->" in fixed
    assert "<!-- /tone -->" in fixed


def test_lint_outside_region_uses_article_tone():
    """The mirror: outside any region, neutral article-tone applies —
    and neutral tier does NOT include the casual rewrite. So
    `在某种意义上` survives unchanged outside a region."""
    text = "在某种意义上，没有任何区域标记。\n"
    fixed, stats, _ = lint.auto_fix_text(text, tone="neutral")
    # Neutral has no rule5 rewrite for this phrase — it stays.
    assert "在某种意义上" in fixed


def test_lint_preserves_tone_markers_verbatim():
    """Lint must not strip <!-- tone:X --> / <!-- /tone --> markers — they
    document author intent (similar to <!-- lint:disable --> markers)."""
    text = (
        "<!-- tone:opinionated -->\n"
        "strong opinion content\n"
        "<!-- /tone -->\n"
    )
    fixed, _, _ = lint.auto_fix_text(text, tone="neutral")
    assert "<!-- tone:opinionated -->" in fixed
    assert "<!-- /tone -->" in fixed


def test_lint_handles_unclosed_region_without_crash():
    """An unclosed region extends to EOF — lint should still process every
    line (using region tone for everything after the opener)."""
    text = (
        "before\n"
        "<!-- tone:casual -->\n"
        "remainder with no closing tag\n"
    )
    fixed, _, warnings = lint.auto_fix_text(text, tone="neutral")
    # Should complete without crash, all 3 lines preserved structurally
    assert "before" in fixed
    assert "remainder with no closing tag" in fixed


def test_lint_with_invalid_region_tone_falls_back_to_article_tone():
    """An invalid tone name in <!-- tone:X --> doesn't open a region —
    the line is processed using the article-level tone (casual here so
    the canonical rewrite path is exercised)."""
    text = (
        "<!-- tone:not_a_real_tone -->\n"
        "在某种意义上，常规处理。\n"
        "<!-- /tone -->\n"
    )
    fixed, stats, _ = lint.auto_fix_text(text, tone="casual")
    # 在某种意义上 still rewritten using the article tone (casual)
    assert "其实" in fixed
    assert stats["rewrote_red_flag"] >= 1
