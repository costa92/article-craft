#!/usr/bin/env python3
"""
Shared configuration constants for article-craft skill
"""

import os
import json
import time
import atexit
from pathlib import Path
from typing import Dict, Any, Optional, List


class VerificationCache:
    """
    Session-level verification cache to avoid redundant work.

    This cache stores verification results for tools, commands, and links
    during a single session, avoiding repeated verification of the same
    content. The cache is automatically cleaned up when the session ends.
    """

    def __init__(self, cache_dir: str = "/tmp/article-gen-cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

        # Create a unique cache file for this session
        self.cache_file = self.cache_dir / f"session_{int(time.time())}.json"
        self._cache = self._load_cache()

        # Register cleanup on exit
        atexit.register(self.cleanup)

    def _load_cache(self) -> Dict[str, Any]:
        """Load cache from file if it exists"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "tools": {},      # {tool_name: {commands: [cmd1, cmd2], timestamp: float}}
            "commands": {},   # {tool_name: [cmd1, cmd2]}
            "links": {}       # {url: {status_code: int, timestamp: float}}
        }

    def _save_cache(self) -> None:
        """Save current cache to file"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f)
        except Exception:
            pass

    def is_tool_verified(self, tool_name: str) -> bool:
        """Check if a tool has been verified in this session"""
        return tool_name in self._cache["tools"]

    def mark_tool_verified(self, tool_name: str, commands: Optional[List[str]] = None) -> None:
        """Mark a tool as verified"""
        self._cache["tools"][tool_name] = {
            "verified_at": time.time(),
            "commands": commands or []
        }
        self._save_cache()

    def is_command_verified(self, tool_name: str, command: str) -> bool:
        """Check if a specific command has been verified"""
        if tool_name not in self._cache["commands"]:
            return False
        return command in self._cache["commands"][tool_name]

    def mark_command_verified(self, tool_name: str, command: str) -> None:
        """Mark a specific command as verified"""
        if tool_name not in self._cache["commands"]:
            self._cache["commands"][tool_name] = []
        if command not in self._cache["commands"][tool_name]:
            self._cache["commands"][tool_name].append(command)
        self._save_cache()

    def is_link_verified(self, url: str) -> bool:
        """Check if a link has been verified"""
        return url in self._cache["links"]

    def mark_link_verified(self, url: str, status_code: int = 200) -> None:
        """Mark a link as verified"""
        self._cache["links"][url] = {
            "verified_at": time.time(),
            "status_code": status_code
        }
        self._save_cache()

    def get_link_status(self, url: str) -> Optional[int]:
        """Get the cached status code for a link"""
        if url in self._cache["links"]:
            return self._cache["links"][url].get("status_code")
        return None

    def get_verified_tools(self) -> List[str]:
        """Get list of all verified tools"""
        return list(self._cache["tools"].keys())

    def get_verified_commands(self, tool_name: str) -> List[str]:
        """Get list of verified commands for a tool"""
        return self._cache["commands"].get(tool_name, [])

    def clear(self) -> None:
        """Clear all cache data"""
        self._cache = {"tools": {}, "commands": {}, "links": {}}
        if self.cache_file.exists():
            self.cache_file.unlink()

    def cleanup(self) -> None:
        """Cleanup cache file (called automatically on exit)"""
        try:
            if self.cache_file.exists():
                self.cache_file.unlink()
        except Exception:
            pass


# Global verification cache singleton
_verification_cache: Optional[VerificationCache] = None


def get_verification_cache() -> VerificationCache:
    """
    Get the global verification cache instance.

    Returns:
        VerificationCache: The singleton cache instance
    """
    global _verification_cache
    if _verification_cache is None:
        _verification_cache = VerificationCache()
    return _verification_cache


def load_user_config() -> Dict[str, Any]:
    """
    Load user configuration from ~/.claude/env.json (unified config)

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

    # Legacy fallback
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
# User config can override these via ~/.article-craft.conf
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

# Model degradation chain: pro → 3.1-flash → 2.5-flash
MODEL_FALLBACK_CHAIN = [
    "gemini-3-pro-image-preview",
    "gemini-3.1-flash-image-preview",
    "gemini-2.5-flash-image",
]

# Image generation defaults (read model from env.json)
IMAGE_DEFAULTS = {
    "resolution": "2K",  # 1K, 2K, or 4K
    "model": _user_config.get("gemini_image_model", "gemini-3-pro-image-preview"),
    "cover_aspect_ratio": "16:9",  # 1344x768, crop to 900x383 for WeChat
    "rhythm_aspect_ratio": "3:2",  # 1248x832 for article body images
}

# PicGo configuration
PICGO_CONFIG = {
    "command": "picgo",
    "upload_timeout": 60,
}

# S3 Configuration (Optional - Alternative to PicGo)
# Set these in ~/.article-craft.conf or environment variables
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
# Calibration: v1 starting values. Will be revisited after 20 articles
# of real review-cycle data accumulate in tone-calibration.jsonl.
TONE_THRESHOLDS = {
    "neutral": {
        "first_person_per_800w": 2,
        "strong_opinion_min": 0,
        "max_summary_phrases": 5,
        "sentence_len_variance_min": 0.0,    # 0 = sub-check D skipped
    },
    "casual": {
        "first_person_per_800w": 4,
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
# Each entry: (compiled_pattern, replacement_string, severity).
# Severity is one of "info" | "warning" | "error".
# Tiers are STACKED via get_rewrites_for_tone(): casual = neutral + casual,
# opinionated = neutral + casual + opinionated.

TONE_LEXICAL_REWRITES: Dict[str, List[Any]] = {
    "neutral": [
        # Canonical Rule 1 red flags — applied at every tone.
        (_re_for_tone.compile(r"赋能"),         "支持",   "warning"),
        (_re_for_tone.compile(r"一站式"),       "完整",   "warning"),
        (_re_for_tone.compile(r"链路"),         "流程",   "info"),
        (_re_for_tone.compile(r"底层逻辑"),     "原理",   "info"),
        (_re_for_tone.compile(r"方法论"),       "做法",   "info"),
        (_re_for_tone.compile(r"抓手"),         "切入点", "warning"),
        (_re_for_tone.compile(r"闭环"),         "回路",   "info"),
        (_re_for_tone.compile(r"降本增效"),     "省钱省力", "warning"),
    ],
    "casual": [
        # Mid-tier replacements: turn formal connectives into colloquial Chinese.
        (_re_for_tone.compile(r"在某种意义上[，,]?"),           "其实",       "warning"),
        (_re_for_tone.compile(r"可以看到[，,]?"),               "能看出",     "warning"),
        (_re_for_tone.compile(r"本质上[，,]?"),                 "说穿了",     "warning"),
        (_re_for_tone.compile(r"接下来我们[来]?(看|介绍|分析)"), r"看看\1的",  "warning"),
        (_re_for_tone.compile(r"下面分别(来看|介绍)"),          r"分别\1",    "warning"),
        (_re_for_tone.compile(r"值得注意的是[，,]?"),           "这地方注意", "warning"),
        (_re_for_tone.compile(r"不难发现"),                     "能看出",     "warning"),
        (_re_for_tone.compile(r"基于以上分析"),                 "由此",       "info"),
        (_re_for_tone.compile(r"综上[，,]?"),                   "总之",       "info"),
        # Paragraph-starter sequence words (was in PARAGRAPH_STARTERS pre-v1.4.18)
        (_re_for_tone.compile(r"^首先[，,:： ]+", _re_for_tone.MULTILINE),  "", "warning"),
        (_re_for_tone.compile(r"^其次[，,:： ]+", _re_for_tone.MULTILINE),  "", "warning"),
        (_re_for_tone.compile(r"^最后[，,:： ]+", _re_for_tone.MULTILINE),  "", "warning"),
        (_re_for_tone.compile(r"^另外[，,:： ]+", _re_for_tone.MULTILINE),  "", "info"),
        (_re_for_tone.compile(r"^此外[，,:： ]+", _re_for_tone.MULTILINE),  "", "info"),
        (_re_for_tone.compile(r"^同时[，,:： ]+", _re_for_tone.MULTILINE),  "", "info"),
    ],
    "opinionated": [
        # High-tier: stronger replacements + closing-line removal (error severity).
        (_re_for_tone.compile(r"显然[，,]?"),                   "明摆着",     "warning"),
        (_re_for_tone.compile(r"综上所述"),                     "说白了",     "error"),
        (_re_for_tone.compile(r"总而言之"),                     "一句话",     "error"),
        (_re_for_tone.compile(r"希望本文对你有帮助[^\n]*"),     "",           "error"),
        (_re_for_tone.compile(r"如果这篇文章对你有帮助[^\n]*"), "",           "error"),
        (_re_for_tone.compile(r"欢迎留言讨论[^\n]*"),           "",           "error"),
        (_re_for_tone.compile(r"点个在看[^\n]*"),               "",           "error"),
    ],
}


def get_rewrites_for_tone(tone: str) -> List[Any]:
    """Return the full rewrite list for a tone, with lower-tier inheritance.

    casual returns neutral + casual; opinionated returns neutral + casual +
    opinionated. Unknown tones fall back to neutral (which is also what
    `resolve_tone` would have returned upstream — defense in depth).
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
