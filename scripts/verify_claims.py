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
from pathlib import Path

SHELL_LANGS = {"bash", "sh", "shell", "zsh"}

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
    for m in re.finditer(r"```(\w+)\n(.*?)```", text, re.DOTALL):
        lang = m.group(1).lower()
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


def _classify(tool: str) -> str:
    if tool in UBIQUITOUS_TOOLS:
        return "ubiquitous"
    if tool in PLACEHOLDERS or tool.isupper():
        return "placeholder"
    return "candidate"


def scan_article(article_path: Path) -> dict:
    text = article_path.read_text(encoding="utf-8", errors="replace")
    seen: dict[str, dict] = {}
    for block in _iter_shell_blocks(text):
        for fragment in _iter_commands(block):
            tool = _extract_tool(fragment)
            if tool is None:
                continue
            kind = _classify(tool)
            if tool not in seen:
                seen[tool] = {"kind": kind, "first_fragment": fragment[:80]}
    report = {
        "article": str(article_path),
        "total_tools": len(seen),
        "checked": [],
        "skipped_ubiquitous": [],
        "skipped_placeholder": [],
        "missing": [],
    }
    for tool, info in sorted(seen.items()):
        if info["kind"] == "placeholder":
            report["skipped_placeholder"].append(tool)
            continue
        if info["kind"] == "ubiquitous":
            report["skipped_ubiquitous"].append(tool)
            continue
        present = shutil.which(tool) is not None
        entry = {"tool": tool, "present": present, "fragment": info["first_fragment"]}
        report["checked"].append(entry)
        if not present:
            report["missing"].append(tool)
    return report


def cmd_scan(args) -> int:
    article = Path(args.article).resolve()
    if not article.exists():
        sys.stderr.write(f"error: article not found: {article}\n")
        return 2
    report = scan_article(article)
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
    return 1 if report["missing"] else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="verify_claims", description="post-write claim verification")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("scan", help="scan article for shell commands and check PATH")
    sp.add_argument("--article", required=True, help="absolute path to article.md")
    sp.add_argument("--json", action="store_true", help="emit JSON instead of human report")
    sp.set_defaults(func=cmd_scan)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
