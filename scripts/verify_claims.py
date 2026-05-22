#!/usr/bin/env python3
"""
verify_claims.py — post-write claim verification for article-craft.

Scans an article.md for executable claims (shell commands in bash/sh code
blocks) and checks whether each named tool is actually available on PATH.
This is the post-write counterpart to the `verify` stage, which only vets
user-provided source URLs before writing begins.

Scope (MVP):
- Walk all fenced code blocks where the language is bash / sh / shell / zsh
- Pull the first non-comment token of each logical command (skip pipes, &&
  chains, subshells, assignments, obvious shell built-ins)
- Run `command -v TOOL` to check existence
- Return a structured JSON report

Intentionally out of scope for now: flag-level validation, API-endpoint
probes, version-string checks. These would require executing the articles
or making live API calls, which is too invasive for a default stage.

CLI:
  python3 verify_claims.py scan --article /abs/article.md [--json]
  python3 verify_claims.py --help

Exit codes:
  0  — no unknown commands (or --json always returns 0)
  1  — at least one command not found on PATH
  2  — invalid usage / file not found
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

SHELL_LANGS = {"bash", "sh", "shell", "zsh"}

# ─── B9 (v1.7+): GitHub URL 真实性校验 ────────────────────────────────
#
# 4 月草稿事故："Top 10 AI DevOps MCP Servers" 文章里出现了 AI 幻觉链接
# `aws-lab/aws-mcp-server`（真实是 `awslabs/mcp`）、`Flux瞻新世纪/flux-mcp-server`
# （仓库名混入中文，明显幻觉）。Rule P1-17/P1-18 把这两类拦下来。
#
# 检查路径：从文章 markdown 中提取所有 `github.com/<org>/<repo>` URL：
#   1. 仓库路径包含 CJK 字符 → 直接 block（明显 AI 幻觉，零成本检测）
#   2. HEAD 请求验证仓库是否存在（5 秒超时，404 → block）

# https://github.com/<org>/<repo> 或 github.com/<org>/<repo>，含 inline link 和裸 URL
_GITHUB_URL_RE = re.compile(
    r"https?://(?:www\.)?github\.com/([A-Za-z0-9_.\-一-鿿]+)/([A-Za-z0-9_.\-一-鿿]+)(?:/[^\s)\]\"']*)?",
    re.IGNORECASE,
)

# CJK Unicode block — 任意 CJK 字符出现在 org/repo 即视为 AI 幻觉
_CJK_RE = re.compile(r"[一-鿿]")

# 跳过：trailing 标点 + GitHub Pages / Wiki / Issues 等子页面（不影响仓库存在性判断）
def _normalize_github_path(org: str, repo: str) -> tuple[str, str]:
    org = org.strip().rstrip(".,;:!?)")
    repo = repo.strip().rstrip(".,;:!?)")
    # repo 可能带 `.git` 后缀（如 `git clone` URL）
    if repo.endswith(".git"):
        repo = repo[:-4]
    return org, repo

# Commands that don't need PATH resolution — shell built-ins, common standard
# utilities that are effectively always present, and article-craft-internal
# placeholders.
SHELL_BUILTINS = {
    "cd", "echo", "export", "if", "then", "fi", "else", "elif",
    "for", "while", "do", "done", "case", "esac", "in",
    "return", "exit", "break", "continue", "set", "unset",
    "source", "alias", "unalias", "shift", "test", "[",
    "read", "eval", "exec", "trap", "wait", "true", "false",
    "pushd", "popd", "dirs", "local", "declare", "typeset",
    "function", "select", "time", "type", "which", "command",
}

UBIQUITOUS_TOOLS = {
    # Core Unix
    "ls", "cat", "grep", "sed", "awk", "find", "cut", "sort", "uniq",
    "head", "tail", "wc", "tr", "tee", "xargs", "basename", "dirname",
    "touch", "mkdir", "rm", "cp", "mv", "ln", "chmod", "chown", "stat",
    "printf", "env", "sleep", "kill", "ps", "id", "whoami", "pwd", "cd",
    "clear", "history", "type", "which", "command", "hash",
    # Network
    "curl", "wget", "ssh", "scp", "rsync", "tar", "zip", "unzip", "gzip",
    "gunzip", "nc", "netcat", "ping", "traceroute", "dig", "nslookup",
    "ip", "ifconfig", "ss", "route",
    # Git
    "git", "diff", "patch", "merge", "rebase", "cherry-pick", "stash",
    "branch", "checkout", "clone", "fetch", "pull", "push", "log", "show",
    "blame", "tag", "bisect",
    # Editors
    "vim", "vi", "nano", "emacs", "less", "more", "most", "code", "subl",
    # Python
    "python", "python3", "pip", "pip3", "pipx", "pyenv", "uv", "poetry",
    "pipreqs", "pip-tools", "setuptools", "wheel",
    # Node
    "node", "npm", "npx", "yarn", "pnpm", "bun", "corepack",
    # Go
    "go", "gofmt", "go", "mod", "gotip",
    # Rust
    "cargo", "rustc", "rustup", "clippy", "cargo-watch",
    # JavaScript / TypeScript
    "tsc", "tsx", "esbuild", "vite", "webpack", "rollup", "parcel",
    "ts-node", "nodemon", "deno",
    # Ruby
    "ruby", "gem", "bundle", "rake", "rbenv", "rvm",
    # Java / JVM
    "java", "javac", "jar", "gradle", "mvn", "ant", "sbt", "kotlin", "scala",
    # C / C++
    "gcc", "g++", "clang", "clang++", "cmake", "make", "ninja", "meson",
    # Containers
    "docker", "podman", "buildah", "skopeo", "ctr", "nerdctl", "docker-compose",
    "dockerfile",
    # Kubernetes
    "kubectl", "helm", "kustomize", "k9s",
    # Cloud CLIs
    "aws", "gcloud", "az", "doctl", "linode-cli", "terraform", "packer",
    # Databases
    "psql", "mysql", "mariadb", "mongosh", "redis-cli", "sqlite3",
    # Build / CI
    "make", "cmake", "ninja", "meson", "premake", "xmake",
    "gitlab-runner", "jenkins", "travis", "circleci",
    # Testing
    "pytest", "unittest", "jest", "mocha", "ava", "tap", "cypress",
    "playwright", "selenium", "puppeteer",
    # Linters / formatters
    "black", "ruff", "flake8", "pylint", "mypy", "eslint", "prettier",
    "rustfmt", "gofmt",
    # Package managers
    "apt", "apt-get", "yum", "dnf", "pacman", "brew", "choco", "scoop",
    # Misc dev tools
    "jq", "yq", "rg", "fd", "fzf", "delta", "bat", "exa", "lsd",
    "httpie", "http", "xh",
    "watch", "tmux", "screen", "byobu",
    "strace", "ltrace", "ldd", "nm", "objdump", "readelf",
    "shellcheck", "shfmt", "hadolint", "dockle",
    "trivy", "grype", "syft",
    "asciinema", "livestream", "streamlink",
    "youtube-dl", "yt-dlp", "ffmpeg", "ImageMagick", "convert",
    "pandoc", "groff", "tex", "latex", "PlantUML", "mermaid", "dot", "graphviz",
    "ansible", "ansible-playbook", "ansible-vault",
    "vagrant", "terraform", "packer", "consul", "nomad",
    "vault", "ots", "1password", "bitwarden",
    "sops", "gpg", "age", "minisign",
    "direnv", "asdf", "rtx", "mise",
}

PLACEHOLDERS = {"TOOL", "YOUR_", "EXAMPLE_", "SOMETHING", "X", "Y"}


# ─── B8 Phase 1: per-tool flag whitelists ────────────────────────────────
#
# Curated (NOT exhaustive) — the goal is to catch typos like `--mesage`
# instead of `--message`, not to validate every possible flag. Unknown
# flags emit a WARNING in the report (not an error) so authors using
# uncommon-but-valid flags just see noise they can ignore.
#
# Coverage rule: at minimum, the canonical `--help` + `--version` /
# `-h` + `-v` plus the 20-50 most common subcommand flags per tool. If
# a flag here doesn't match the live tool, fix the schema in a follow-up
# PR — the warning surface is the canary.
#
# Long flags only — short flags are too ambiguous (e.g. `-a` means
# different things to git / docker / curl) to validate without
# subcommand context, which is out of scope for Phase 1.
TOOL_FLAG_SCHEMA: dict[str, set[str]] = {
    "git": {
        # Global / top-level
        "--help", "--version", "--git-dir", "--work-tree", "--namespace",
        "--bare", "--no-replace-objects", "--literal-pathspecs", "--no-pager",
        # commit / log / diff / show metadata
        "--message", "--amend", "--no-edit", "--allow-empty", "--allow-empty-message",
        "--signoff", "--no-signoff", "--no-verify", "--verify",
        "--author", "--date", "--cleanup", "--squash", "--fixup",
        # push / pull / fetch
        "--set-upstream", "--upstream", "--force", "--force-with-lease",
        "--no-force-with-lease", "--mirror", "--tags", "--no-tags", "--follow-tags",
        "--prune", "--no-prune", "--push", "--no-push", "--delete",
        "--all", "--unshallow", "--depth", "--shallow-since", "--shallow-exclude",
        "--filter", "--single-branch", "--no-single-branch", "--recurse-submodules",
        # branch / checkout / switch / restore
        "--track", "--no-track", "--set-upstream-to", "--unset-upstream",
        "--list", "--remote", "--contains", "--merged", "--no-merged",
        "--create", "--orphan", "--detach",
        "--staged", "--worktree", "--source", "--patch",
        # reset / revert / rebase / merge
        "--soft", "--hard", "--mixed", "--keep", "--abort", "--continue", "--skip",
        "--interactive", "--root", "--onto", "--strategy", "--strategy-option",
        "--no-ff", "--ff-only", "--ff", "--squash", "--no-commit", "--rebase",
        "--no-rebase",
        # diff / log formatting
        "--cached", "--no-color", "--color", "--stat", "--numstat", "--shortstat",
        "--name-only", "--name-status", "--patch-with-stat", "--summary",
        "--word-diff", "--no-renames", "--find-renames", "--diff-filter",
        "--unified", "--no-pager",
        # log / show
        "--oneline", "--graph", "--decorate", "--no-decorate", "--all", "--branches",
        "--tags", "--remotes", "--first-parent", "--no-merges", "--merges",
        "--since", "--until", "--author", "--committer", "--grep",
        # diff/show toggles
        "--check", "--full-index", "--binary", "--exit-code", "--quiet", "--verbose",
        # clone / init
        "--branch", "--origin", "--upload-pack", "--template", "--shared", "--reference",
        # config
        "--global", "--local", "--system", "--worktree", "--file", "--blob",
        "--get", "--get-all", "--get-regexp", "--add", "--unset", "--unset-all",
        "--type", "--null", "--name-only", "--show-origin", "--show-scope",
        # remote
        "--add", "--remove", "--set-head", "--add-remote", "--set-url",
        # tag
        "--annotate", "--sign", "--no-sign", "--message", "--cleanup", "--force",
        "--delete", "--list", "--contains", "--no-contains", "--points-at",
        # generic toggles
        "--dry-run", "--prune-tags",
    },

    "docker": {
        "--help", "--version", "--config", "--debug", "--host", "--log-level",
        "--tls", "--tlscacert", "--tlscert", "--tlskey", "--tlsverify",
        # run / exec / build
        "--rm", "--detach", "--interactive", "--tty", "--name", "--volume",
        "--mount", "--publish", "--publish-all", "--expose", "--env", "--env-file",
        "--workdir", "--user", "--entrypoint", "--cmd", "--label", "--label-file",
        "--network", "--network-alias", "--ip", "--ip6", "--dns", "--dns-search",
        "--add-host", "--restart", "--privileged", "--cap-add", "--cap-drop",
        "--security-opt", "--ulimit", "--memory", "--memory-swap", "--cpus",
        "--cpu-shares", "--cpuset-cpus", "--cpuset-mems", "--shm-size",
        "--gpus", "--device", "--read-only", "--tmpfs", "--init", "--platform",
        # build
        "--file", "--tag", "--target", "--build-arg", "--no-cache", "--pull",
        "--cache-from", "--cache-to", "--push", "--load", "--output", "--secret",
        "--ssh", "--progress",
        # image / push / pull
        "--all-tags", "--all", "--disable-content-trust", "--quiet",
        "--digests", "--filter", "--format", "--no-trunc",
        # compose-like
        "--project-name", "--file", "--profile", "--env-file", "--scale",
        "--build", "--no-build", "--remove-orphans", "--abort-on-container-exit",
        "--exit-code-from", "--timeout",
        # ps / inspect / logs
        "--all", "--size", "--latest", "--last", "--no-trunc",
        "--follow", "--since", "--until", "--tail", "--timestamps",
        # generic toggles
        "--dry-run", "--force", "--quiet", "--verbose",
    },

    "kubectl": {
        "--help", "--kubeconfig", "--context", "--cluster", "--user", "--namespace",
        "--server", "--token", "--username", "--password", "--client-certificate",
        "--client-key", "--certificate-authority", "--insecure-skip-tls-verify",
        "--cache-dir", "--v", "--vmodule", "--log-flush-frequency",
        # get / describe / explain
        "--output", "--watch", "--watch-only", "--no-headers", "--show-labels",
        "--show-kind", "--all-namespaces", "--field-selector", "--selector",
        "--label-columns", "--sort-by", "--chunk-size", "--allow-missing-template-keys",
        # apply / create / delete / patch
        "--filename", "--recursive", "--kustomize", "--dry-run", "--force",
        "--prune", "--prune-allowlist", "--prune-whitelist", "--server-side",
        "--field-manager", "--validate", "--cascade", "--grace-period",
        "--ignore-not-found", "--now", "--wait", "--timeout",
        "--from-file", "--from-literal", "--from-env-file", "--type", "--patch",
        # exec / attach / port-forward / logs / cp
        "--container", "--stdin", "--tty", "--pod-running-timeout",
        "--address", "--port", "--container", "--no-preserve",
        "--follow", "--previous", "--since", "--since-time", "--tail",
        "--prefix", "--timestamps", "--max-log-requests",
        # rollout / scale / autoscale
        "--replicas", "--current-replicas", "--resource-version",
        "--max", "--min", "--cpu-percent",
        "--revision", "--to-revision", "--keep-annotations",
        # config / cluster-info
        "--minify", "--flatten", "--raw", "--merge",
        # generic toggles
        "--dry-run", "--force", "--quiet", "--verbose", "--client", "--short",
    },

    "uv": {
        "--help", "--version", "--quiet", "--verbose", "--no-color",
        "--color", "--native-tls", "--offline", "--cache-dir", "--no-cache",
        "--config-file", "--directory", "--project",
        # pip / sync / lock / add / remove
        "--all-extras", "--extra", "--no-dev", "--dev", "--group",
        "--editable", "--no-editable", "--upgrade", "--upgrade-package",
        "--reinstall", "--reinstall-package", "--refresh", "--refresh-package",
        "--index", "--default-index", "--index-strategy", "--keyring-provider",
        "--system", "--python", "--no-deps", "--no-binary", "--only-binary",
        "--prerelease", "--resolution", "--no-build", "--no-build-isolation",
        "--no-sources", "--frozen", "--locked", "--no-sync",
        # build / publish
        "--out-dir", "--sdist", "--wheel", "--check-url",
        "--repository", "--repository-url", "--username", "--password",
        "--token",
        # run
        "--with", "--with-editable", "--with-requirements",
        # tool
        "--from", "--editable", "--upgrade", "--reinstall",
        # python
        "--preview", "--no-default-groups",
        # generic toggles
        "--dry-run", "--force",
    },

    "npm": {
        "--help", "--version", "--global", "--save", "--save-dev", "--save-peer",
        "--save-optional", "--save-bundle", "--save-prod", "--no-save",
        "--save-exact", "--no-package-lock", "--package-lock-only",
        "--legacy-peer-deps", "--strict-peer-deps", "--no-optional",
        "--include", "--omit", "--workspace", "--workspaces", "--include-workspace-root",
        "--prefix", "--cache", "--registry", "--scope", "--access",
        "--tag", "--otp", "--force", "--dry-run", "--ignore-scripts",
        "--audit", "--no-audit", "--audit-level", "--fund", "--no-fund",
        "--prefer-offline", "--prefer-online", "--offline",
        "--production", "--dev", "--depth", "--all", "--long", "--parseable",
        "--global-style", "--legacy-bundling",
        "--json", "--silent", "--quiet", "--loglevel", "--verbose", "--timing",
        # publish / view / search / outdated / audit
        "--filter", "--workspaces-update", "--install-strategy",
    },

    "curl": {
        "--help", "--version", "--verbose", "--silent", "--show-error",
        "--output", "--remote-name", "--remote-name-all", "--remote-header-name",
        "--remote-time", "--write-out", "--include", "--head", "--data",
        "--data-binary", "--data-raw", "--data-urlencode", "--form", "--form-string",
        "--user", "--user-agent", "--referer", "--header", "--cookie",
        "--cookie-jar", "--request", "--max-time", "--connect-timeout",
        "--retry", "--retry-delay", "--retry-max-time", "--retry-connrefused",
        "--retry-all-errors", "--fail", "--fail-with-body", "--location",
        "--location-trusted", "--max-redirs", "--proxy", "--proxy-user",
        "--socks5", "--socks5-hostname", "--insecure", "--cacert", "--capath",
        "--cert", "--cert-type", "--key", "--key-type", "--ciphers",
        "--tls-max", "--tlsv1", "--tlsv1.2", "--tlsv1.3", "--ssl-reqd",
        "--http1.0", "--http1.1", "--http2", "--http2-prior-knowledge",
        "--http3", "--ipv4", "--ipv6", "--resolve", "--alt-svc",
        "--range", "--continue-at", "--limit-rate", "--max-filesize",
        "--upload-file", "--basic", "--digest", "--ntlm", "--negotiate",
        "--bearer", "--oauth2-bearer",
        "--no-buffer", "--progress-bar", "--no-progress-meter", "--no-keepalive",
        "--compressed", "--trace", "--trace-ascii", "--dump-header",
        "--config", "--parallel", "--parallel-max",
    },

    "python3": {
        "--help", "--version", "--module", "--check-hash-based-pycs",
        "--no-site", "--no-user-site", "--unbuffered", "--inspect", "--isolated",
        "--optimize", "--quiet", "--verbose", "--bytes-warning",
        "--ignore-environment", "--debug", "--dont-write-bytecode",
        "--skip-source-first-line", "--implementation", "--build-backend",
    },
}

# Allow flags ending in `=value` — split on `=` before validating.
_FLAG_RE = re.compile(r"^(--[a-z][a-z0-9-]*)(?:=.*)?$")

# Fragments matching these patterns describe a tool (CLI help output), not actual
# command invocations. The first token is a noun in a description sentence,
# not a executable.  These are safe to skip — not real commands.
_HELP_DESCRIBE_RE = re.compile(
    r"^[A-Za-z_][\w]*\s*(?:—|--)\s+[a-z]", re.IGNORECASE
)
# Single-word fragments that are clearly description nouns, not commands.
# E.g. "drawer" in "a searchable drawer", "palace" in "a searchable palace".
_HELP_NOUN_RE = re.compile(
    r"^(?:a|an|the|some|your|my|this|that|its)\s+\w", re.IGNORECASE
)


def _iter_shell_blocks(text: str):
    for m in re.finditer(r"```([^\n`]*)\n(.*?)```", text, re.DOTALL):
        lang = m.group(1).strip().split()[0].lower() if m.group(1).strip() else ""
        if lang not in SHELL_LANGS:
            continue
        yield m.group(2)


def _iter_commands(block: str):
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        for fragment in re.split(r"[|&;]{1,2}|\$\(|`", line):
            fragment = fragment.strip()
            if not fragment:
                continue
            yield fragment


def _extract_tool(fragment: str) -> str | None:
    tokens = fragment.split()
    if not tokens:
        return None
    head = tokens[0]
    while head in {"sudo", "env"} and len(tokens) > 1:
        tokens = tokens[1:]
        head = tokens[0]
    if "=" in head and not head.startswith("="):
        return None
    head = head.strip("()[]{}<>")
    if not head or not re.match(r"^[A-Za-z_][A-Za-z0-9_.+\-]*$", head):
        return None
    if head in SHELL_BUILTINS:
        return None
    # Skip description nouns: "drawer" in "a searchable drawer",
    # "palace" in "mempalace — a searchable palace"
    if _HELP_DESCRIBE_RE.match(fragment) or _HELP_NOUN_RE.match(fragment):
        return None
    return head


def _extract_tool_and_flags(fragment: str) -> tuple[str | None, list[str]]:
    """Return (tool, [long_flags_used]).

    Skips `sudo` / `env` prefixes the same way ``_extract_tool`` does, so
    flag attribution lands on the actual command.
    Only LONG flags (``--name``) are returned — short flags collide too
    much across tools (e.g. ``-a`` is "all" for git, "addr" for some
    others) to validate without subcommand context (B8 Phase 2+).
    """
    tokens = fragment.split()
    if not tokens:
        return None, []
    # Strip prefixes the same way _extract_tool does.
    while tokens and tokens[0] in {"sudo", "env"} and len(tokens) > 1:
        tokens = tokens[1:]
    if not tokens:
        return None, []
    tool = _extract_tool(" ".join(tokens))
    if tool is None:
        return None, []

    flags: list[str] = []
    for tok in tokens[1:]:
        # Strip URL trailing punctuation that might glue onto a flag
        # (e.g. `--help.`).
        tok = tok.rstrip(",;.")
        m = _FLAG_RE.match(tok)
        if m:
            flags.append(m.group(1))
    return tool, flags


def _check_flags(tool: str, flags: list[str]) -> list[str]:
    """Return the subset of ``flags`` that aren't in the tool's schema.

    Tools not in :data:`TOOL_FLAG_SCHEMA` get an empty list (no validation
    — Phase 1 scope). De-duplicated and order-preserved.
    """
    schema = TOOL_FLAG_SCHEMA.get(tool)
    if schema is None:
        return []
    seen: set[str] = set()
    unknown: list[str] = []
    for flag in flags:
        if flag in schema:
            continue
        if flag in seen:
            continue
        seen.add(flag)
        unknown.append(flag)
    return unknown


def _classify(tool: str) -> str:
    if tool in UBIQUITOUS_TOOLS:
        return "ubiquitous"
    if tool in PLACEHOLDERS or tool.isupper():
        return "placeholder"
    return "candidate"


def _check_github_url(org: str, repo: str, timeout: float = 5.0) -> tuple[bool, str]:
    """HEAD check whether a GitHub repo exists. Returns (exists, reason).

    Uses urllib (stdlib) to avoid adding requests dependency. GitHub redirects
    HEAD on `github.com/<org>/<repo>` to canonical URL; 200 / 301 / 302 → exists.
    404 → does not exist. Network/timeout errors are reported but don't block
    (don't crash review on flaky network).
    """
    url = f"https://github.com/{org}/{repo}"
    req = urllib.request.Request(
        url,
        method="HEAD",
        headers={"User-Agent": "article-craft/verify-claims/1.7"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return (200 <= resp.status < 400), f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, "404 Not Found (仓库不存在 / 可能是 AI 幻觉链接)"
        # 403 / 429 等可能是 rate limit，不当作不存在
        return True, f"HTTP {e.code} (assume exists — not 404)"
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return True, f"network error: {type(e).__name__} (skipped check)"


def scan_github_urls(text: str, skip_network: bool = False) -> dict:
    """Scan all github.com URLs in text. Returns structured report.

    Two checks:
    - **CJK in path**: 仓库 org/repo 含中文 → 直接 block（零成本，明显 AI 幻觉）
    - **HEAD 存在性**: 404 → block；其他 HTTP 错误（网络/限流）不 block

    `skip_network=True` 用于离线场景或测试，只做 CJK 检查。
    """
    seen: dict[tuple[str, str], dict] = {}
    for m in _GITHUB_URL_RE.finditer(text):
        org, repo = _normalize_github_path(m.group(1), m.group(2))
        if not org or not repo:
            continue
        key = (org.lower(), repo.lower())
        if key in seen:
            continue
        seen[key] = {"org": org, "repo": repo, "full_match": m.group(0)[:80]}

    cjk_violations = []
    network_violations = []
    network_warnings = []
    checked_ok = []

    for (org, repo), info in sorted(seen.items()):
        # Check 1: CJK in org/repo
        if _CJK_RE.search(org) or _CJK_RE.search(repo):
            cjk_violations.append({
                "org": info["org"], "repo": info["repo"],
                "fragment": info["full_match"],
                "reason": "仓库名含中文字符（明显 AI 幻觉，零成本检测）",
            })
            continue  # CJK 已经 block，不必走 HEAD

        # Check 2: HEAD 真实性
        if skip_network:
            checked_ok.append({"org": info["org"], "repo": info["repo"], "checked": False})
            continue

        exists, reason = _check_github_url(info["org"], info["repo"])
        if not exists:
            network_violations.append({
                "org": info["org"], "repo": info["repo"],
                "fragment": info["full_match"],
                "reason": reason,
            })
        elif "skipped" in reason or "assume exists" in reason:
            network_warnings.append({
                "org": info["org"], "repo": info["repo"],
                "reason": reason,
            })
        else:
            checked_ok.append({"org": info["org"], "repo": info["repo"], "checked": True})

    return {
        "total_urls": len(seen),
        "cjk_block": cjk_violations,
        "url_404": network_violations,
        "network_warnings": network_warnings,
        "checked_ok": checked_ok,
    }


def scan_article(article_path: Path, skip_network: bool = False) -> dict:
    text = article_path.read_text(encoding="utf-8", errors="replace")
    seen: dict[str, dict] = {}
    # Per-tool flag aggregation across all uses in the article. We collect
    # flags for ANY tool in TOOL_FLAG_SCHEMA, even ubiquitous ones (git
    # is ubiquitous — its flag schema is the whole point).
    flag_uses: dict[str, list[tuple[str, str]]] = {}  # tool → [(flag, fragment)]

    for block in _iter_shell_blocks(text):
        for fragment in _iter_commands(block):
            tool, flags = _extract_tool_and_flags(fragment)
            if tool is None:
                continue
            kind = _classify(tool)
            if tool not in seen:
                seen[tool] = {"kind": kind, "first_fragment": fragment[:80]}
            if tool in TOOL_FLAG_SCHEMA and flags:
                flag_uses.setdefault(tool, []).extend(
                    (f, fragment[:80]) for f in flags
                )

    report = {
        "article": str(article_path),
        "total_tools": len(seen),
        "checked": [],
        "skipped_ubiquitous": [],
        "skipped_placeholder": [],
        "missing": [],
        "flag_warnings": [],
        "github_urls": scan_github_urls(text, skip_network=skip_network),
    }
    for tool, info in sorted(seen.items()):
        if info["kind"] == "placeholder":
            report["skipped_placeholder"].append(tool)
            continue
        if info["kind"] == "ubiquitous":
            report["skipped_ubiquitous"].append(tool)
        else:
            present = shutil.which(tool) is not None
            entry = {"tool": tool, "present": present, "fragment": info["first_fragment"]}
            report["checked"].append(entry)
            if not present:
                report["missing"].append(tool)

    # B8 Phase 1: per-tool flag validation. Always runs for tools in the
    # schema, regardless of ubiquitous / placeholder classification.
    for tool in sorted(flag_uses.keys()):
        seen_flags: set[str] = set()
        deduped: list[tuple[str, str]] = []
        for flag, frag in flag_uses[tool]:
            if flag in seen_flags:
                continue
            seen_flags.add(flag)
            deduped.append((flag, frag))
        unknown = _check_flags(tool, [f for f, _ in deduped])
        for flag in unknown:
            fragment = next((frag for f, frag in deduped if f == flag), "")
            report["flag_warnings"].append(
                {
                    "tool": tool,
                    "flag": flag,
                    "fragment": fragment,
                }
            )

    return report


def cmd_scan(args) -> int:
    article = Path(args.article).resolve()
    if not article.exists():
        sys.stderr.write(f"error: article not found: {article}\n")
        return 2
    report = scan_article(article, skip_network=args.skip_network)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"📋 verify_claims: {article}")
        print(f"   total tools found: {report['total_tools']}")
        print(f"   checked: {len(report['checked'])}")
        print(f"   skipped (ubiquitous): {len(report['skipped_ubiquitous'])}")
        print(f"   skipped (placeholders): {len(report['skipped_placeholder'])}")
        if report["checked"]:
            print()
            for entry in report["checked"]:
                mark = "✅" if entry["present"] else "❌"
                print(f"   {mark} {entry['tool']:20s}  {entry['fragment']}")
        if report["missing"]:
            print()
            print(f"⚠️  {len(report['missing'])} tool(s) NOT on PATH: {', '.join(report['missing'])}")
            print("   → Options: mark [需要验证] in the article, replace with a real tool, or")
            print("             delete the command if the article's point doesn't need it.")
        if report.get("flag_warnings"):
            print()
            print(f"⚠️  {len(report['flag_warnings'])} unknown flag(s) — possibly typos or "
                  "schema gaps (info only, won't block):")
            for w in report["flag_warnings"]:
                print(f"   ? {w['tool']:10s} {w['flag']:30s}  {w['fragment']}")
            print("   → If valid, ignore — the schema is curated, not exhaustive.")
            print("     If a typo, fix the article. Schema gaps: PR welcome.")

        # B9 (v1.7+): GitHub URL 真实性 + CJK 幻觉检测
        gh = report.get("github_urls", {})
        if gh.get("total_urls", 0) > 0:
            print()
            print(f"🔗 GitHub URL 检查：{gh['total_urls']} 个 URL")
            print(f"   ✅ 通过：{len(gh.get('checked_ok', []))}")
            print(f"   ❌ CJK 幻觉：{len(gh.get('cjk_block', []))}")
            print(f"   ❌ 404 不存在：{len(gh.get('url_404', []))}")
            print(f"   ⚠ 网络警告（不阻断）：{len(gh.get('network_warnings', []))}")

            for v in gh.get("cjk_block", []):
                print(f"   ❌ [CJK] {v['org']}/{v['repo']}")
                print(f"      → {v['reason']}")
                print(f"      fragment: {v['fragment']}")
            for v in gh.get("url_404", []):
                print(f"   ❌ [404] {v['org']}/{v['repo']}")
                print(f"      → {v['reason']}")
                print(f"      fragment: {v['fragment']}")

    # Exit code:
    # - missing-on-PATH tools → 1（保留原行为）
    # - CJK 幻觉链接 → 1（block，B9）
    # - 404 GitHub URL → 1（block，B9）
    # - 网络警告 / flag warnings → 不影响 exit code
    gh = report.get("github_urls", {})
    if (
        report["missing"]
        or gh.get("cjk_block")
        or gh.get("url_404")
    ):
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="verify_claims", description="post-write claim verification")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("scan", help="scan article for shell commands and check PATH")
    sp.add_argument("--article", required=True, help="absolute path to article.md")
    sp.add_argument("--json", action="store_true", help="emit JSON instead of human report")
    sp.add_argument(
        "--skip-network",
        action="store_true",
        help="skip GitHub URL HEAD checks (offline / test mode). CJK 检查仍生效。",
    )
    sp.set_defaults(func=cmd_scan)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
