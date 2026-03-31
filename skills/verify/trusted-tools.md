# Trusted Tools Whitelist

> Ported from article-generator v3.3 verification-checklist.md

These widely-used tools have stable APIs and extensive official documentation. Their **basic commands** can be trusted without WebSearch verification.

---

## Development Tools

- Docker, Kubernetes (kubectl), Git
- npm, yarn, pnpm, pip, uv, cargo, Maven, Gradle
- Node.js, Python, Go, Rust, Java, TypeScript, Ruby

## OS & Package Managers

- apt, yum, dnf, brew, pacman, apk, snap

## Common CLI Tools

- curl, wget, ssh, scp, rsync
- grep, sed, awk, tar, gzip
- jq, make, cmake

---

## When to Verify Anyway

Even for whitelisted tools, verification is required when:

- **Niche flags or options** -- e.g., `docker run --gpus`, `git worktree`
- **Version-specific features** -- e.g., "Docker 24.0+ only", "Python 3.12+ syntax"
- **Deprecated commands** -- e.g., `docker-compose` (v1) vs `docker compose` (v2)
- **Post-2023 new features or parameters** -- always check official docs
- **Any command you are unsure about** -- when in doubt, verify

## Verification Cache (Session-Level)

Within the same session:
- Already-verified tool/command combinations do not need re-verification
- But a new parameter combination (e.g., `--gpus` after verifying basic `docker run`) still needs checking

## Verification Priority

1. **High** (must verify): specific commands, parameters, config items, API calls
2. **Medium** (should verify): workflow steps, best practices, performance tips
3. **Low** (can trust): fundamental concepts, general principles, language basics
