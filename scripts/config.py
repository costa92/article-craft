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
