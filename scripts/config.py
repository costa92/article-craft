#!/usr/bin/env python3
"""
Shared configuration constants for article-craft skill
"""

import os
import json
from pathlib import Path
import re
from typing import Dict, Any, Optional, List, Tuple


def load_user_config() -> Dict[str, Any]:
    """
    Load user configuration from ~/.claude/env.json (unified config).

    A template lives at the project root: env.example.json.

    Returns:
        dict: User configuration or empty dict if not found
    """
    env_json = Path("~/.claude/env.json").expanduser()
    if env_json.exists():
        try:
            with open(env_json, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass

    # Legacy fallback (pre-v1.0 config path; kept for backward compat)
    legacy = Path("~/.article-generator.conf").expanduser()
    if legacy.exists():
        try:
            with open(legacy, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass

    return {}


# Load user configuration
_user_config = load_user_config()


def cache_dir() -> Path:
    """Resolve the persistent cache directory for article-craft.

    Precedence: ``ARTICLE_CRAFT_CACHE_DIR`` env var > ``~/.cache/article-craft/``.
    The directory is created if missing. All cross-process caches (verify
    cache, screenshot cache, etc.) should resolve their location through
    this function so the override env var works uniformly.
    """
    override = os.environ.get("ARTICLE_CRAFT_CACHE_DIR")
    p = Path(override).expanduser() if override else Path.home() / ".cache" / "article-craft"
    p.mkdir(parents=True, exist_ok=True)
    return p


def share_card_logo() -> str:
    """Resolve the share-card logo text.

    Precedence: ``share_card_logo`` in env.json > ``name`` field in
    ``.claude-plugin/plugin.json`` > the literal "article-craft" fallback.
    Lets a fork override the brand without editing source.
    """
    configured = _user_config.get("share_card_logo", "")
    if configured:
        return configured

    plugin_root = (
        os.environ.get("CLAUDE_PLUGIN_ROOT")
        or str(Path.home() / ".claude" / "plugins" / "article-craft")
    )
    plugin_json = Path(plugin_root) / ".claude-plugin" / "plugin.json"
    try:
        with open(plugin_json, "r", encoding="utf-8") as f:
            return json.load(f).get("name", "article-craft")
    except Exception:
        return "article-craft"


def author_name() -> str:
    """Resolve the article author's display name.

    Precedence: env.json ``user_name`` > ``git config user.name`` >
    ``"Anonymous"``. Used by the write skill to populate the ``author``
    field in YAML frontmatter so downstream skills (share_card, publish)
    have a non-empty value to work with.
    """
    configured = _user_config.get("user_name", "")
    if configured:
        return configured

    try:
        import subprocess
        result = subprocess.run(
            ["git", "config", "--get", "user.name"],
            capture_output=True, text=True, timeout=2,
        )
        name = (result.stdout or "").strip()
        if result.returncode == 0 and name:
            return name
    except Exception:
        pass

    return "Anonymous"


def kb_category_root() -> str:
    """Resolve the top-level knowledge-base directory for technical articles.

    Precedence: env.json ``kb_category_root`` > the literal ``02-技术``
    fallback. Lets a fork with a differently-named KB tree override the
    publish auto-placement root without editing source.
    """
    return _user_config.get("kb_category_root", "02-技术")


def kb_uncategorized_dir() -> str:
    """Resolve the fallback subdirectory name for unmatched articles.

    Precedence: env.json ``kb_uncategorized_dir`` > the literal ``未分类``
    fallback. Used by publish auto-placement when no category matches.
    """
    return _user_config.get("kb_uncategorized_dir", "未分类")


def browser_cookies_path() -> str:
    """Resolve the configured cookies-JSON path for Playwright screenshots.

    Empty string means "not configured" — the caller (`screenshot_tool.py`)
    then falls back to ``~/.cache/article-craft/cookies.json`` if that file
    exists, or skips cookie loading entirely. Used to unlock login-walled
    platforms (HN-HTTPS, Reddit, 知乎, 微博, 小红书) from headless runs.

    Precedence: env.json ``browser_cookies_path`` > empty (unconfigured).
    File format: Playwright-compatible JSON — top-level list of cookie
    objects, or ``{"cookies": [...]}``.
    """
    return _user_config.get("browser_cookies_path", "")


# Aspect ratio to resolution mapping
# NOTE: Only these aspect ratios are supported by Gemini API
ASPECT_RATIO_MAP = {
    "1024x1024": "1:1",  # 1:1
    "832x1248": "2:3",  # 2:3
    "1248x832": "3:2",  # 3:2
    "864x1184": "3:4",  # 3:4
    "1184x864": "4:3",  # 4:3
    "896x1152": "4:5",  # 4:5
    "1152x896": "5:4",  # 5:4
    "768x1344": "9:16",  # 9:16
    "1344x768": "16:9",  # 16:9 - Use this for WeChat covers, then crop to 900x383
    "1536x672": "21:9",  # 21:9
}

# Reverse mapping: aspect ratio string -> size string
ASPECT_RATIO_TO_SIZE = {
    "1:1": "1024x1024",
    "2:3": "832x1248",
    "3:2": "1248x832",  # STANDARDIZED: 3:2 aspect ratio
    "3:4": "864x1184",
    "4:3": "1184x864",
    "4:5": "896x1152",
    "5:4": "1152x896",
    "9:16": "768x1344",
    "16:9": "1344x768",
    "21:9": "1536x672",
}

# Timeout configurations (in seconds)
# User config can override these via ~/.claude/env.json (timeouts.* keys).
_default_timeouts = {
    "image_generation": 120,  # 2 minutes per image
    "upload": 60,  # 1 minute for upload
    "dependency_check": 5,  # 5 seconds for version checks
    "npm_install": 120,  # 2 minutes for npm install
}

# Merge user config with defaults (user config takes precedence)
TIMEOUTS = {**_default_timeouts, **_user_config.get("timeouts", {})}

# Retry configurations
RETRY_CONFIG = {
    "max_attempts": 4,
    "initial_delay": 3,  # seconds
    "backoff_factor": 2,  # exponential backoff multiplier
    "retriable_errors": [
        "SSL",
        "ConnectionError",
        "TimeoutError",
        "NetworkError",
        "500",
        "502",
        "503",
        "504",
        "RemoteProtocolError",
        "Server disconnected",
        "disconnected",
        "UNAVAILABLE",
        "high demand",
        "No data received",
    ]
}

# Model degradation chain: minimax → pro → 3.1-flash → 2.5-flash → openai
#
# OpenAI gpt-image-1 is appended at the end of the SaaS block (B7 Phase 2).
# sd-local (self-hosted Stable Diffusion via a1111 — B7 Phase 3) is NOT
# in the default chain — it requires a running a1111 server which most
# users don't have. Opt in by either:
#   1. Setting `image_model: "sd-local"` in env.json (explicit selection)
#   2. Extending MODEL_FALLBACK_CHAIN locally if you want it as a fallback
# Default chain stays SaaS-only to avoid surprising "no a1111 found"
# errors at generation time.
MODEL_FALLBACK_CHAIN = [
    "minimax-image-01",
    "gemini-3-pro-image-preview",
    "gemini-3.1-flash-image-preview",
    "gemini-2.5-flash-image",
    "openai-gpt-image-1",
]


def filter_chain_by_available_keys(chain: List[str]) -> List[str]:
    """Drop models whose provider API key isn't configured (B13).

    Routes through the image-provider registry (B7 Phase 1) — a model
    is kept iff some registered :class:`image_providers.ImageProvider`
    claims it via ``model_names()`` AND that provider's
    ``is_configured()`` returns True. Unknown models (no registered
    provider) pass through unchanged (forward-compat for future chain
    entries).

    Returns the filtered chain preserving original order. Empty result
    means **no image provider is configured** — callers should fail
    fast with a clear error rather than letting the chain exhaust
    naturally with confusing per-model errors.

    Why: pre-v1.6.9 a user with only ``GEMINI_API_KEY`` (the common
    new-user state when ``image_model`` defaults to Minimax) would see
    every batched image first try Minimax, fail with an auth error,
    then fall through to Gemini — N wasted attempts per N-image
    generation. This filter prunes the dead leg up front.
    """
    # Late import to avoid a circular: image_providers reads env.json the
    # same way config does but doesn't depend on it.
    from image_providers import for_model

    out: List[str] = []
    for model in chain:
        provider = for_model(model)
        if provider is None:
            # Unknown model → keep (forward-compat — caller will hit a
            # registry miss at dispatch time with a clear error).
            out.append(model)
        elif provider.is_configured():
            out.append(model)
        # else: drop silently — the dead-leg prune is the entire point.
    return out

# Text model used by nanobanana.py --enhance (prompt expansion).
# Separate from MODEL_FALLBACK_CHAIN, which is image-only.
TEXT_MODEL = _user_config.get("gemini_text_model", "gemini-2.0-flash")

# CDN whitelist for verify-claims / lint URL filtering. URLs whose host
# is not in this list are flagged so the writer can rehost them.
# Intentionally excludes per-author personal CDNs — set
# `verify_cdn_whitelist` in env.json to extend.
VERIFY_CDN_WHITELIST = _user_config.get(
    "verify_cdn_whitelist",
    ["cdn.jsdelivr.net", "mmbiz.qpic.cn", "pbs.twimg.com"],
)

# Per-host main content selectors used by screenshot_tool for both
# `suggest_selector` (auto element-screenshot target) and anchor scope
# (constrains where ANCHOR keyword search runs). Users can override or
# extend per host in env.json:
#
#   "screenshot_main_content_selectors": {
#     "myblog.com": [".post-body"],
#     "x.com":      ["[data-testid='tweet']"]
#   }
#
# Returned dict shape: { "<host_substring>": [ "<css_selector>", ... ] }
SCREENSHOT_MAIN_CONTENT_OVERRIDES: Dict[str, List[str]] = (
    _user_config.get("screenshot_main_content_selectors", {}) or {}
)

# Image generation defaults (read model from env.json)
IMAGE_DEFAULTS = {
    "resolution": "2K",  # 1K, 2K, or 4K
    "model": _user_config.get("image_model", _user_config.get("gemini_image_model", "minimax-image-01")),
    "cover_aspect_ratio": "16:9",  # 1344x768, crop to 900x383 for WeChat
    "rhythm_aspect_ratio": "3:2",  # 1248x832 for article body images
}

# PicGo configuration
PICGO_CONFIG = {
    "command": "picgo",
    "upload_timeout": 60,
}

# S3 Configuration (Optional - Alternative to PicGo)
# Set these in ~/.claude/env.json (s3.* keys) or via environment variables.
S3_CONFIG = {
    "enabled": _user_config.get("s3", {}).get("enabled", False),
    "endpoint_url": os.getenv("S3_ENDPOINT", _user_config.get("s3", {}).get("endpoint_url", "")),
    "access_key_id": os.getenv("S3_ACCESS_KEY", _user_config.get("s3", {}).get("access_key_id", "")),
    "secret_access_key": os.getenv("S3_SECRET_KEY", _user_config.get("s3", {}).get("secret_access_key", "")),
    "bucket_name": os.getenv("S3_BUCKET", _user_config.get("s3", {}).get("bucket_name", "")),
    "public_url_prefix": os.getenv("S3_PUBLIC_URL", _user_config.get("s3", {}).get("public_url_prefix", "")),
}


# ─── Tone System (v1.4.18) ───────────────────────────────────────
# Three-tier register-aware de-AI system. See
# docs/superpowers/specs/2026-05-07-tone-system-design.md for design rationale.

TONE_REGISTER_LEVELS = ("neutral", "casual", "opinionated")

# Default tone per writing style (references/writing-styles.md A-H).
# Falls back to "neutral" for unknown style ids.
STYLE_TO_TONE_DEFAULT = {
    "A": "neutral",       # 技术教程
    "B": "casual",        # 经验分享 / 口语化
    "C": "neutral",       # 深度长文
    "D": "casual",        # 评测对比
    "E": "neutral",       # 资讯快报
    "F": "casual",        # 项目复盘 / Case Study
    "G": "opinionated",   # 观点输出 / 思考
    "H": "opinionated",   # AI 资讯爆料 / 自媒体爆款
}


# Per-section tone override markers (B10, v1.6.13+):
#   <!-- tone:casual -->     opens a region using a different tone
#   <!-- /tone -->           closes the current region
# Within a region, lint rewrites apply the region's tone instead of the
# article-level tone. Unknown tone names are ignored (region not opened).
# Markers are preserved verbatim in output for reproducibility.
_TONE_OPEN_RE = re.compile(r"<!--\s*tone:([a-zA-Z_-]+)\s*-->")
_TONE_CLOSE_RE = re.compile(r"<!--\s*/tone\s*-->")


def parse_tone_regions(
    text: str, default_tone: str
) -> List[Tuple[int, int, str]]:
    """Parse ``<!-- tone:X --> ... <!-- /tone -->`` regions in *text*.

    Returns a list of ``(start_line, end_line_exclusive, tone)`` tuples
    covering **every** line in the input, with no gaps and no overlaps.
    Lines outside any region get ``default_tone``; lines inside a region
    get the region's declared tone.

    Region semantics (v1 — flat, no nesting):

    - ``<!-- tone:X -->`` opens region X. If a region is already open
      (from a previous ``<!-- tone:Y -->`` without intervening ``/tone``),
      that previous region implicitly closes at the new opener.
    - ``<!-- /tone -->`` closes the current open region. Stray closers
      with no matching opener are ignored (treated as plain text).
    - Unknown tone names (not in ``TONE_REGISTER_LEVELS``) are skipped —
      the opener is treated as plain text, region not opened.
    - Unclosed regions extend to EOF.
    - The marker lines themselves get the **surrounding** tone (markers
      have no prose to rewrite — the contents are HTML comments).

    Used by ``scripts/lint_article.auto_fix_text`` to apply per-region
    tone rewrites instead of one tone for the whole article.
    """
    if default_tone not in TONE_REGISTER_LEVELS:
        default_tone = "neutral"

    lines = text.splitlines()
    if not lines:
        return []

    # Build (line_index, tone) for every line.
    per_line: List[str] = [default_tone] * len(lines)
    current_tone: Optional[str] = None  # None = no region open

    for i, line in enumerate(lines):
        # The marker line itself uses the surrounding tone (the tone
        # that was in effect on the previous line) — set BEFORE we
        # process the marker, so the marker line stays in the "outside"
        # context.
        per_line[i] = current_tone if current_tone is not None else default_tone

        # Now process any markers on this line. Process opens first
        # (so a line containing both close+open ends up in the new
        # open's region for subsequent lines).
        close_match = _TONE_CLOSE_RE.search(line)
        open_match = _TONE_OPEN_RE.search(line)

        if close_match:
            current_tone = None
        if open_match:
            requested = open_match.group(1).lower()
            if requested in TONE_REGISTER_LEVELS:
                current_tone = requested
            # else: invalid tone name — silently ignore (region not opened)

    # Compact contiguous same-tone runs into spans.
    spans: List[Tuple[int, int, str]] = []
    start = 0
    for i in range(1, len(lines) + 1):
        if i == len(lines) or per_line[i] != per_line[start]:
            spans.append((start, i, per_line[start]))
            start = i
    return spans


def resolve_tone(
    cli_tone: Optional[str] = None,
    frontmatter_tone: Optional[str] = None,
    writing_style: Optional[str] = None,
) -> str:
    """Resolve final tone using three-tier precedence: CLI > frontmatter > style default.

    Invalid values at any tier degrade silently to the next tier. Unknown
    writing styles default to "neutral". The CLI layer is expected to reject
    invalid `--tone` values BEFORE calling this function (with an explicit
    error to the user); we keep this resolver permissive so frontmatter
    typos and missing fields don't crash the pipeline.

    Returns one of TONE_REGISTER_LEVELS, never None.
    """
    if cli_tone in TONE_REGISTER_LEVELS:
        return cli_tone
    if frontmatter_tone in TONE_REGISTER_LEVELS:
        return frontmatter_tone
    if writing_style and writing_style in STYLE_TO_TONE_DEFAULT:
        return STYLE_TO_TONE_DEFAULT[writing_style]
    return "neutral"


# ─── Tone thresholds (Rule 17 sub-checks) ────────────────────────
# v1.1 calibration (2026-05-08): tightened after 4-article pilot.
#   - neutral.max_summary_phrases: 5 → 3 (caught AI-flavor article that
#     was passing with 7 summary phrases at warn-only severity)
#   - casual.first_person_per_800w: 4 → 3 (real casual blogs hover at 2-3,
#     not 4+; threshold was filtering out genuinely casual writing)
# v2 calibration target: re-run on 20 published articles and tune further.
TONE_THRESHOLDS = {
    "neutral": {
        "first_person_per_800w": 2,
        "strong_opinion_min": 0,
        "max_summary_phrases": 3,            # was 5 in v1
        "sentence_len_variance_min": 0.0,    # 0 = sub-check D skipped
    },
    "casual": {
        "first_person_per_800w": 3,          # was 4 in v1
        "strong_opinion_min": 0,
        "max_summary_phrases": 2,
        "sentence_len_variance_min": 0.30,
    },
    "opinionated": {
        "first_person_per_800w": 6,
        "strong_opinion_min": 1,
        "max_summary_phrases": 0,
        "sentence_len_variance_min": 0.45,
    },
}


# Patterns that signal an explicit personal opinion / hot take.
# Used by Rule 17 sub-check B. Patterns are kept conservative — false
# positives on plain technical prose are worse than false negatives.
import re as _re_for_tone

STRONG_OPINION_PATTERNS = [
    _re_for_tone.compile(r"我赌"),
    _re_for_tone.compile(r"我觉得.*?(?:就是|根本|纯属|没必要)"),
    _re_for_tone.compile(r"(?:这|那)(?:玩意|破事|设计).*?(?:错|烂|拉胯|蠢|坑爹)"),
    _re_for_tone.compile(r"别(?:学|用|碰|信)"),
    _re_for_tone.compile(r"真(?:香|的香)"),
    _re_for_tone.compile(r"纯(?:纯|属)"),
    _re_for_tone.compile(r"我的判断是"),
    _re_for_tone.compile(r"敢断言"),
    _re_for_tone.compile(r"(?:就是|根本)(?:错|不对|愚蠢)"),
]


# ─── Tone-aware lexical rewrites (lint_article.py consumes this) ─
# Each entry: (compiled_pattern, replacement_string, severity, rule_id).
# Severity is one of "info" | "warning" | "error".
# rule_id identifies which lint rule this rewrite enforces (used by the
# inline <!-- lint:disable rule_id --> / <!-- lint:enable rule_id --> system).
# Tiers are STACKED via get_rewrites_for_tone(): casual = neutral + casual,
# opinionated = neutral + casual + opinionated.

TONE_LEXICAL_REWRITES: Dict[str, List[Any]] = {
    "neutral": [
        # Canonical Rule 1 red flags — applied at every tone.
        (_re_for_tone.compile(r"赋能"),         "支持",    "warning", "rule1"),
        (_re_for_tone.compile(r"一站式"),       "完整",    "warning", "rule1"),
        (_re_for_tone.compile(r"链路"),         "流程",    "info",    "rule1"),
        (_re_for_tone.compile(r"底层逻辑"),     "原理",    "info",    "rule1"),
        (_re_for_tone.compile(r"方法论"),       "做法",    "info",    "rule1"),
        (_re_for_tone.compile(r"抓手"),         "切入点",  "warning", "rule1"),
        (_re_for_tone.compile(r"闭环"),         "回路",    "info",    "rule1"),
        (_re_for_tone.compile(r"降本增效"),     "省钱省力", "warning", "rule1"),
    ],
    "casual": [
        # Mid-tier replacements: turn formal connectives into colloquial Chinese.
        # Patterns with optional trailing punctuation use a named (?P<sep>...)
        # capture group + \g<sep> in the replacement so commas/colons are
        # preserved when present (avoids "值得注意的是LangChain" → "这地方注意LangChain"
        # awkwardness; v1.1 calibration fix).
        (_re_for_tone.compile(r"在某种意义上(?P<sep>[，,]?)"),    r"其实\g<sep>",       "warning", "rule5"),
        (_re_for_tone.compile(r"可以看到(?P<sep>[，,]?)"),        r"能看出\g<sep>",     "warning", "rule5"),
        (_re_for_tone.compile(r"本质上(?P<sep>[，,]?)"),          r"说穿了\g<sep>",     "warning", "rule5"),
        (_re_for_tone.compile(r"接下来我们[来]?(看|介绍|分析)"),  r"看看\1的",          "warning", "rule5"),
        (_re_for_tone.compile(r"下面分别(来看|介绍)"),            r"分别\1",            "warning", "rule5"),
        (_re_for_tone.compile(r"值得注意的是(?P<sep>[，,]?)"),    r"这地方注意\g<sep>", "warning", "rule5"),
        (_re_for_tone.compile(r"不难发现"),                       "能看出",             "warning", "rule5"),
        (_re_for_tone.compile(r"基于以上分析"),                   "由此",               "info",    "rule5"),
        (_re_for_tone.compile(r"综上(?P<sep>[，,]?)"),            r"总之\g<sep>",       "info",    "rule5"),
        # Paragraph-starter sequence words (was in PARAGRAPH_STARTERS pre-v1.4.18)
        (_re_for_tone.compile(r"^首先[，,:： ]+", _re_for_tone.MULTILINE),  "", "warning", "rule5"),
        (_re_for_tone.compile(r"^其次[，,:： ]+", _re_for_tone.MULTILINE),  "", "warning", "rule5"),
        (_re_for_tone.compile(r"^最后[，,:： ]+", _re_for_tone.MULTILINE),  "", "warning", "rule5"),
        (_re_for_tone.compile(r"^另外[，,:： ]+", _re_for_tone.MULTILINE),  "", "info",    "rule5"),
        (_re_for_tone.compile(r"^此外[，,:： ]+", _re_for_tone.MULTILINE),  "", "info",    "rule5"),
        (_re_for_tone.compile(r"^同时[，,:： ]+", _re_for_tone.MULTILINE),  "", "info",    "rule5"),
    ],
    "opinionated": [
        # High-tier: stronger replacements + closing-line removal (error severity).
        (_re_for_tone.compile(r"显然(?P<sep>[，,]?)"),          r"明摆着\g<sep>", "warning", "rule5"),
        (_re_for_tone.compile(r"综上所述"),                     "说白了",     "error",   "rule5"),
        (_re_for_tone.compile(r"总而言之"),                     "一句话",     "error",   "rule5"),
        (_re_for_tone.compile(r"希望本文对你有帮助[^\n]*"),     "",           "error",   "rule3"),
        (_re_for_tone.compile(r"如果这篇文章对你有帮助[^\n]*"), "",           "error",   "rule3"),
        (_re_for_tone.compile(r"欢迎留言讨论[^\n]*"),           "",           "error",   "rule3"),
        (_re_for_tone.compile(r"点个在看[^\n]*"),               "",           "error",   "rule3"),
    ],
}


def get_rewrites_for_tone(tone: str) -> List[Any]:
    """Return the full rewrite list for a tone, with lower-tier inheritance.

    casual returns neutral + casual; opinionated returns neutral + casual +
    opinionated. Unknown tones fall back to neutral (which is also what
    `resolve_tone` would have returned upstream — defense in depth).

    Each entry is a 4-tuple: (compiled_pattern, replacement, severity, rule_id).
    """
    if tone == "casual":
        return list(TONE_LEXICAL_REWRITES["neutral"]) + list(TONE_LEXICAL_REWRITES["casual"])
    if tone == "opinionated":
        return (
            list(TONE_LEXICAL_REWRITES["neutral"])
            + list(TONE_LEXICAL_REWRITES["casual"])
            + list(TONE_LEXICAL_REWRITES["opinionated"])
        )
    return list(TONE_LEXICAL_REWRITES["neutral"])
