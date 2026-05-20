#!/usr/bin/env python3
"""
Auto-detect and optionally install missing dependencies for article-craft.

This module now exposes reusable healthcheck functions consumed by
`scripts/doctor.py`, while preserving the original standalone CLI behavior.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REQUIREMENTS_FILE = SCRIPT_DIR / "requirements.txt"


def _result(
    name: str,
    status: str,
    message: str,
    fix: str = "",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "message": message,
        "fix": fix,
        "details": details or {},
    }


def check_command_exists(cmd: str) -> bool:
    """Check if a command exists in PATH."""
    return shutil.which(cmd) is not None


def _load_env_json() -> dict[str, Any]:
    env_json = Path("~/.claude/env.json").expanduser()
    if not env_json.exists():
        return {}
    try:
        return json.loads(env_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _requires_picgo() -> bool:
    env = _load_env_json()
    s3_enabled = bool((env.get("s3") or {}).get("enabled", False))
    upload_mode = str(env.get("upload_mode", "")).strip().lower()
    if upload_mode:
        return upload_mode == "picgo"
    return not s3_enabled


def check_python_dependencies() -> dict[str, Any]:
    required_packages = {
        "google.genai": "google-genai>=0.1.0",
        "PIL": "Pillow>=10.0.0",
        "dotenv": "python-dotenv>=1.0.0",
        "yaml": "PyYAML>=6.0",
        "tqdm": "tqdm>=4.65.0",
        "tenacity": "tenacity>=8.2.0",
        "playwright": "playwright>=1.40.0",
        "requests": "requests>=2.31.0",
    }

    missing_packages: list[str] = []

    for import_name, pip_name in required_packages.items():
        try:
            if import_name == "google.genai":
                from google import genai  # noqa: F401
            elif import_name == "PIL":
                import PIL  # noqa: F401
            elif import_name == "dotenv":
                import dotenv  # noqa: F401
            elif import_name == "yaml":
                import yaml  # noqa: F401
            elif import_name == "tqdm":
                import tqdm  # noqa: F401
            elif import_name == "tenacity":
                import tenacity  # noqa: F401
            elif import_name == "playwright":
                import playwright  # noqa: F401
            elif import_name == "requests":
                import requests  # noqa: F401
        except ImportError:
            missing_packages.append(pip_name)

    if missing_packages:
        return _result(
            "python_dependencies",
            "block",
            f"Missing Python packages: {', '.join(missing_packages)}",
            f"Run: pip install -r {REQUIREMENTS_FILE}",
            {"missing": missing_packages},
        )

    return _result(
        "python_dependencies",
        "pass",
        "All required Python packages are installed",
    )


def check_playwright() -> dict[str, Any]:
    def _pass(executable: str, fallback_used: bool = False) -> dict[str, Any]:
        return _result(
            "playwright",
            "pass",
            "Playwright and Chromium are available",
            details={
                "chromium_executable": executable,
                "fallback_used": fallback_used,
            },
        )

    def _block(message: str, returncode: int | None = None) -> dict[str, Any]:
        details: dict[str, Any] = {}
        if returncode is not None:
            details["returncode"] = returncode
        return _result(
            "playwright",
            "block",
            message,
            "Run: pip install playwright && playwright install chromium",
            details,
        )

    try:
        executable = _probe_playwright_subprocess()
        return _pass(executable)
    except subprocess.TimeoutExpired:
        try:
            executable = _probe_playwright_inprocess()
            return _pass(executable, fallback_used=True)
        except Exception:
            return _block("Playwright check failed: TimeoutExpired")
    except OSError as e:
        try:
            executable = _probe_playwright_inprocess()
            return _pass(executable, fallback_used=True)
        except Exception:
            return _block(f"Playwright check failed: {type(e).__name__}")
    except subprocess.CalledProcessError as e:
        stderr = str(e.stderr or "").strip() or "Playwright/Chromium unavailable"
        return _block(stderr, e.returncode)


def _probe_playwright_subprocess() -> str:
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from playwright.sync_api import sync_playwright; "
                    "p=sync_playwright().start(); "
                    "print(p.chromium.executable_path); "
                    "p.stop()"
                ),
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise e
    return (result.stdout or "").strip()


def _probe_playwright_inprocess() -> str:
    from playwright.sync_api import sync_playwright

    p = sync_playwright().start()
    try:
        return p.chromium.executable_path
    finally:
        p.stop()


def check_picgo() -> dict[str, Any]:
    required = _requires_picgo()
    picgo = shutil.which("picgo")
    if not picgo:
        status = "block" if required else "warn"
        reason = (
            "PicGo CLI missing and current config expects PicGo uploads"
            if required
            else "PicGo CLI missing; non-PicGo upload path may still work"
        )
        return _result(
            "picgo",
            status,
            reason,
            "Install with: npm install -g picgo",
            {"required": required},
        )

    try:
        result = subprocess.run(
            ["picgo", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        status = "block" if required else "warn"
        return _result(
            "picgo",
            status,
            f"PicGo exists but version check failed: {type(e).__name__}",
            "Reinstall or fix PATH for picgo",
            {"required": required},
        )

    if result.returncode != 0:
        status = "block" if required else "warn"
        stderr = (result.stderr or "").strip() or "PicGo version check failed"
        return _result(
            "picgo",
            status,
            stderr,
            "Reinstall with: npm install -g picgo",
            {"required": required, "returncode": result.returncode},
        )

    return _result(
        "picgo",
        "pass",
        "PicGo CLI is available",
        details={"required": required, "version": (result.stdout or "").strip()},
    )


def check_gemini_api_key() -> dict[str, Any]:
    env_val = os.getenv("GEMINI_API_KEY", "").strip()
    if env_val:
        return _result(
            "gemini_api_key",
            "pass",
            "GEMINI_API_KEY is set in environment",
        )

    env_json = _load_env_json()
    val = str(env_json.get("gemini_api_key", "")).strip()
    if val and not val.startswith("your-"):
        return _result(
            "gemini_api_key",
            "pass",
            "gemini_api_key is configured in ~/.claude/env.json",
        )

    legacy = Path("~/.nanobanana.env").expanduser()
    if legacy.exists():
        try:
            content = legacy.read_text(encoding="utf-8")
            if "GEMINI_API_KEY=" in content:
                maybe = content.split("GEMINI_API_KEY=", 1)[1].splitlines()[0].strip()
                if maybe:
                    return _result(
                        "gemini_api_key",
                        "pass",
                        "GEMINI_API_KEY is configured in legacy ~/.nanobanana.env",
                    )
        except OSError:
            pass

    return _result(
        "gemini_api_key",
        "warn",
        "GEMINI_API_KEY missing; Gemini fallback and --enhance unavailable",
        'Add "gemini_api_key" to ~/.claude/env.json or export GEMINI_API_KEY',
    )


def check_minimax_api_key() -> dict[str, Any]:
    env_val = os.getenv("MINIMAX_API_KEY", "").strip()
    if env_val:
        return _result(
            "minimax_api_key",
            "pass",
            "MINIMAX_API_KEY is set in environment",
        )

    env_json = _load_env_json()
    val = str(env_json.get("minimax_api_key", "")).strip()
    if val:
        return _result(
            "minimax_api_key",
            "pass",
            "minimax_api_key is configured in ~/.claude/env.json",
        )

    return _result(
        "minimax_api_key",
        "block",
        "MINIMAX_API_KEY missing",
        'Add "minimax_api_key" to ~/.claude/env.json or export MINIMAX_API_KEY',
    )


def check_ytdlp() -> dict[str, Any]:
    if check_command_exists("yt-dlp"):
        return _result("yt_dlp", "pass", "yt-dlp is available")
    return _result(
        "yt_dlp",
        "warn",
        "yt-dlp not found; YouTube ingestion will degrade",
        "Install with: pip install yt-dlp or brew install yt-dlp",
    )


def check_notebooklm_cli() -> dict[str, Any]:
    for cmd in ("notebooklm", "nlm", "notebooklm-mcp"):
        if check_command_exists(cmd):
            flavor = "mcp-compat" if cmd == "notebooklm-mcp" else "research-cli"
            return _result(
                "notebooklm_cli",
                "pass",
                f"NotebookLM CLI is available ({cmd})",
                details={"command": cmd, "flavor": flavor},
            )
    return _result(
        "notebooklm_cli",
        "warn",
        "NotebookLM CLI not found; long-form research ingestion will degrade",
        (
            "Install with: uv tool install notebooklm-cli "
            "(or: pip install notebooklm-cli); command is usually `nlm`. "
            "If you only need MCP compatibility, install `notebooklm-mcp-cli`."
        ),
    )


def check_gh() -> dict[str, Any]:
    if check_command_exists("gh"):
        return _result("gh", "pass", "GitHub CLI is available")
    return _result(
        "gh",
        "warn",
        "gh CLI not found; some source verification paths will degrade",
        "Install from: https://cli.github.com/",
    )


def check_docker() -> dict[str, Any]:
    if check_command_exists("docker"):
        return _result("docker", "pass", "Docker is available")
    return _result(
        "docker",
        "warn",
        "Docker not found; container-based verification fallback unavailable",
        "Install Docker Desktop or Docker Engine",
    )


def check_env_json() -> dict[str, Any]:
    """Verify ~/.claude/env.json (if present) is valid JSON.

    The original ``_load_env_json`` swallows ``JSONDecodeError`` and returns
    an empty dict, which means a typo in env.json silently degrades every
    downstream check (no API keys, no S3, no PicGo override) without any
    user-visible signal. This explicit check surfaces it.
    """
    env_json = Path("~/.claude/env.json").expanduser()
    if not env_json.exists():
        return _result(
            "env_json",
            "pass",
            "~/.claude/env.json not present (optional file)",
        )
    try:
        size = env_json.stat().st_size
        if size == 0:
            return _result(
                "env_json",
                "warn",
                "~/.claude/env.json is empty",
                "Populate from env.example.json or delete the file",
            )
        json.loads(env_json.read_text(encoding="utf-8"))
        return _result(
            "env_json",
            "pass",
            "~/.claude/env.json parses as valid JSON",
        )
    except json.JSONDecodeError as exc:
        return _result(
            "env_json",
            "block",
            f"~/.claude/env.json has invalid JSON (line {exc.lineno}, col {exc.colno}): {exc.msg}",
            "Fix the JSON syntax error; otherwise every downstream check silently uses empty config",
        )
    except OSError as exc:
        return _result(
            "env_json",
            "warn",
            f"~/.claude/env.json could not be read: {exc}",
            "Check file permissions",
        )


def check_plugin_root() -> dict[str, Any]:
    """Verify CLAUDE_PLUGIN_ROOT env var (when set) resolves to a real dir.

    Claude Code sets this automatically when the plugin is invoked; manual
    shell runs may not. Missing is fine (script-relative fallback works);
    set-but-broken (typo in path, stale checkout) silently fails downstream
    callers that join paths onto it.
    """
    root_env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not root_env:
        return _result(
            "plugin_root",
            "warn",
            "CLAUDE_PLUGIN_ROOT not set; scripts will use script-relative fallbacks",
            "Claude Code sets this automatically — only matters for direct shell runs",
        )
    root_path = Path(root_env).expanduser()
    if not root_path.exists():
        return _result(
            "plugin_root",
            "block",
            f"CLAUDE_PLUGIN_ROOT points to non-existent path: {root_path}",
            "Unset CLAUDE_PLUGIN_ROOT or correct it",
        )
    if not root_path.is_dir():
        return _result(
            "plugin_root",
            "block",
            f"CLAUDE_PLUGIN_ROOT is not a directory: {root_path}",
            "Unset CLAUDE_PLUGIN_ROOT or correct it",
        )
    return _result(
        "plugin_root",
        "pass",
        f"CLAUDE_PLUGIN_ROOT → {root_path}",
        details={"path": str(root_path)},
    )


# Hosts probed by check_network_reachability(). Single source so tests
# can patch a deterministic list.
_NETWORK_PROBE_TARGETS = {
    "minimax": "https://api.minimaxi.com/",
    "gemini": "https://generativelanguage.googleapis.com/",
}
_NETWORK_PROBE_TIMEOUT_SEC = 3.0


def _probe_url(url: str, timeout: float = _NETWORK_PROBE_TIMEOUT_SEC) -> tuple[bool, str]:
    """HEAD-probe a URL. Returns ``(reachable, detail)``.

    "Reachable" means we got any HTTP response — including 4xx/5xx —
    because that proves DNS resolved and the host accepted a connection.
    Only transport errors (connect timeout, DNS failure) count as
    unreachable.
    """
    import urllib.error
    import urllib.request

    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, f"HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        return True, f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        return False, f"{type(reason).__name__}: {reason}"
    except TimeoutError as exc:
        return False, f"TimeoutError: {exc}"
    except OSError as exc:
        return False, f"OSError: {exc}"


def check_network_reachability() -> dict[str, Any]:
    """Probe Minimax / Gemini hosts. Only enabled with doctor's --network flag.

    Conditional on the matching API key being configured — if no Minimax
    key is set we don't probe Minimax (irrelevant noise).
    """
    env = _load_env_json()
    has_minimax = bool(env.get("minimax_api_key")) or bool(os.environ.get("MINIMAX_API_KEY"))
    has_gemini = bool(env.get("gemini_api_key")) or bool(os.environ.get("GEMINI_API_KEY"))

    targets: list[tuple[str, str]] = []
    if has_minimax:
        targets.append(("minimax", _NETWORK_PROBE_TARGETS["minimax"]))
    if has_gemini:
        targets.append(("gemini", _NETWORK_PROBE_TARGETS["gemini"]))

    if not targets:
        return _result(
            "network_reachability",
            "warn",
            "no API keys configured — nothing to probe",
            "Set minimax_api_key / gemini_api_key first",
            details={"probed": 0},
        )

    successes: dict[str, str] = {}
    failures: dict[str, str] = {}
    for name, url in targets:
        ok, detail = _probe_url(url)
        if ok:
            successes[name] = detail
        else:
            failures[name] = detail

    details = {"probed": len(targets), "successes": successes, "failures": failures}

    if failures:
        return _result(
            "network_reachability",
            "warn",
            (
                f"{len(failures)}/{len(targets)} endpoint(s) unreachable: "
                + ", ".join(f"{k}={v}" for k, v in failures.items())
            ),
            "Check network connection / firewall / corporate proxy settings",
            details=details,
        )
    return _result(
        "network_reachability",
        "pass",
        f"all {len(targets)} endpoint(s) reachable",
        details=details,
    )


def run_all_checks(include_network: bool = False) -> list[dict[str, Any]]:
    checks = [
        check_plugin_root(),
        check_env_json(),
        check_python_dependencies(),
        check_gemini_api_key(),
        check_minimax_api_key(),
        check_playwright(),
        check_picgo(),
        check_ytdlp(),
        check_notebooklm_cli(),
        check_gh(),
        check_docker(),
    ]
    if include_network:
        checks.append(check_network_reachability())
    return checks


def _render_check(result: dict[str, Any]) -> str:
    icon = {"pass": "✅", "warn": "⚠️ ", "block": "❌"}.get(result["status"], "•")
    lines = [f"{icon} {result['name']}: {result['message']}"]
    if result.get("fix"):
        lines.append(f"   Fix: {result['fix']}")
    return "\n".join(lines)


def render_human_report(results: list[dict[str, Any]]) -> int:
    print("=" * 70)
    print("🚀 article-craft Dependency Check")
    print("=" * 70)
    print()

    worst = 0
    for result in results:
        print(_render_check(result))
        print()
        if result["status"] == "warn":
            worst = max(worst, 1)
        elif result["status"] == "block":
            worst = max(worst, 2)

    print("=" * 70)
    if worst == 0:
        print("✅ All dependencies are ready!")
        print("=" * 70)
        print("\n🎉 You can now use article-craft skill")
        print("   Example: /article-craft 写一篇关于Python的技术文章\n")
    elif worst == 1:
        print("⚠️  Some optional dependencies are missing")
        print("=" * 70)
        print("\nThe main pipeline can still run with degraded functionality.\n")
    else:
        print("❌ Required dependencies are missing")
        print("=" * 70)
        print("\nPlease fix the blocking items above before running the full pipeline.\n")
    return worst


def install_missing_python_dependencies() -> bool:
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-q", "-r", str(REQUIREMENTS_FILE)]
        )
        return True
    except subprocess.CalledProcessError:
        return False


def main() -> int:
    results = run_all_checks()
    status = render_human_report(results)

    python_result = next((r for r in results if r["name"] == "python_dependencies"), None)
    if python_result and python_result["status"] == "block":
        missing = python_result.get("details", {}).get("missing", [])
        if missing:
            print("📦 Attempting automatic Python dependency install...")
            if install_missing_python_dependencies():
                print("✅ Python dependencies installed. Re-run this command to verify everything.\n")
            else:
                print(f"❌ Auto-install failed. Run manually: pip install -r {REQUIREMENTS_FILE}\n")

    return status


if __name__ == "__main__":
    raise SystemExit(main())
