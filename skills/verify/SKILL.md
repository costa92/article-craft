---
name: article-craft:verify
version: 1.4.2
description: "Batch verify links, commands, and tool features with source trust tiers. Uses T0-T5 trust classification to focus verification effort."
allowed-tools:
  - Read
  - Bash
  - Grep
  - WebSearch
  - WebFetch
  - AskUserQuestion
---

# Pre-Writing Verification

Verify links, commands, and tool features in batch before writing an article. Ensures all referenced tools and URLs are accurate. Non-blocking -- continues even when some checks fail.

**Invoke**: `/article-craft:verify`

---

## Inputs

- **Topic**: the article subject (e.g., "Docker container networking")
- **Tool names**: list of tools/projects the article will reference

If invoked standalone (not after `article-craft:requirements`), use AskQuestion to collect:
1. "What is the article topic?" (free-form text)
2. "Which tools/projects will the article reference?" (free-form text, comma-separated)

---

## Verification Modes

Choose a mode based on the article's purpose. Default is **Standard**.

| Mode | When to use | What it checks | Speed |
|------|------------|----------------|-------|
| **Fast** | Drafts, personal notes, time-pressured | Non-whitelisted tools only; skip link checks | ~60% of Standard |
| **Standard** | Published blog posts, tutorials (default) | Core tools + main links + code completeness | Baseline |
| **Strict** | Official docs, enterprise content | All tools (including whitelisted) + all links + sandbox tests | ~140% of Standard |

User can specify mode explicitly (e.g., "verify in strict mode") or it defaults to Standard.

---

## Execution Steps

### Step 1: Feature Discovery (tool/project articles only)

For each tool the article covers, discover its full feature surface. Skip this step for pure concept articles (e.g., "microservices architecture").

**Path A -- Tool is installed locally:**
```bash
# Check installation and scan all subcommands (one bash call)
which TOOL 2>/dev/null && TOOL --version && TOOL --help
```
Then for unfamiliar subcommands:
```bash
TOOL subcommand --help
```

**Path B -- Tool is NOT installed locally (prefer Docker):**
```bash
# Spin up a temporary container, run feature discovery, then clean up
docker run --rm TOOL-IMAGE:latest sh -c "TOOL --help && TOOL subcommand --help"
```

**Path B fallback -- No Docker available:**
```bash
# GitHub README (most authoritative feature overview)
curl -s "https://api.github.com/repos/ORG/REPO/readme" | \
  python3 -c "import sys,json,base64; print(base64.b64decode(json.load(sys.stdin)['content']).decode())" | head -100

# Official docs CLI reference
curl -s "https://docs.TOOL.com/cli" | sed 's/<[^>]*>/ /g' | tr -s ' \n' | head -80

# Recent releases
gh api repos/ORG/REPO/releases --jq '.[0:3][] | "\(.tag_name): \(.name)"'
```

**Priority**: local `--help` > Docker temp env > GitHub README > official docs > WebSearch

**All methods fail**: If a tool cannot be verified through any path (not installed, no Docker, GitHub/docs unreachable, WebSearch unavailable), do NOT silently skip. Instead:
1. Mark the tool as `UNVERIFIED` in the verification report
2. Warn the user: "Tool [X] could not be verified through any method. Claims about its features may be inaccurate."
3. Ask the user whether to proceed with unverified claims or remove the tool from the article

**Blog/Changelog scan** (always, if tool has an official blog):
```bash
curl -s "https://TOOL-WEBSITE.com/blog" | \
  sed 's/<[^>]*>/ /g' | tr -s ' \n' | \
  grep -i "new\|launch\|release\|feature" | head -10
```

After discovery, compile a feature checklist: known features vs. newly discovered features. New features must be included in the article outline.

### Step 2: Batch Link Verification (one bash call)

Verify all URLs in a single bash invocation. Use HEAD first, fall back to GET on 405/000.

```bash
for url in \
  "https://url1.com" \
  "https://url2.com" \
  "https://url3.com"; do
  code=$(curl -sI -o /dev/null -w "%{http_code}" --max-time 10 "$url")
  if [ "$code" = "405" ] || [ "$code" = "000" ]; then
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url")
  fi
  [ "$code" != "200" ] && echo "FAIL $code $url"
done
# No output = all passed
```

**301 redirect handling:**
```bash
curl -sI -o /dev/null -w "%{http_code} %{redirect_url}" --max-time 10 URL
# 301 → follow the redirect, use the final URL in the article
```

In **Fast** mode: skip this step entirely.
In **Standard** mode: verify main documentation links; skip known-good domains (docs.docker.com, github.com, etc.).
In **Strict** mode: verify every link including supplementary references.

### Step 3: Command Verification (chain dependent commands)

Verify commands the article will demonstrate. Chain dependent commands with `&&` in a single bash call:

```bash
# Example: verify uv workflow
cd /tmp && rm -rf test-proj && mkdir test-proj && cd test-proj && \
  uv init --name test && uv add requests && \
  uv run python -c "import requests; print(requests.__version__)" && \
  uv tree
```

Independent commands can be verified in parallel bash calls.

**Whitelisted tools** (see `${CLAUDE_PLUGIN_ROOT}/skills/verify/trusted-tools.md`): basic commands can be trusted without verification. Only verify niche flags, version-specific features, or deprecated commands.

**Non-whitelisted tools**: must be verified through official docs or sandbox execution. If a command cannot be verified, mark it `[needs verification]` or remove it.

### Step 4: Project Disambiguation

If WebSearch returns multiple projects with the same name:
```
Found 3 projects named "XYZ":
1. owner1/xyz (1.2k stars, actively maintained) - CLI tool
2. owner2/XYZ (500 stars, 6 months stale) - Web framework
3. owner3/xyz-tool (50 stars, personal project) - Python scripts

Which one did you mean?
```

Never assume which project the user means. Always ask.

### Step 5: Save URL Cache (for screenshot_tool)

将 Step 2 的 URL 检查结果写入共享缓存,供 screenshot_tool.py 复用:

```bash
# 方式 A：逐步追加（每验证一个 URL 就写入）
SCRIPT="${CLAUDE_PLUGIN_ROOT}/scripts/write_verify_cache.py"

# Step 2 的 curl 检查结果追加到缓存：
# 例如从 Step 2 提取出 code 和 url 变量后：
python3 "$SCRIPT" --url "$url" --status "$code" --reason "checked"

# 方式 B：批量写入（Step 2 结果保存到文件后一次性处理）
# 将 Step 2 的 curl 输出保存到 /tmp/verify-results.txt
# 格式：每行 "CODE URL"（如 "200 https://..." 或 "404 https://..."）
python3 "$SCRIPT" --from-file /tmp/verify-results.txt
```

> screenshot_tool.py 会优先读取此缓存（路径 `~/.cache/article-craft/verify-cache.json`），避免对同一 URL 重复发起 HEAD 请求。

**Cache TTL (configurable)**:

| Mode | Default TTL | Rationale |
|---|---|---|
| Standard single-article run | **1 hour** | Single session won't cross boundary; freshness matters more |
| `--series FILE` | **24 hours** | Auto-extended so all articles in a multi-hour series share vetting |
| Custom | via `~/.claude/env.json` key `verify_cache_ttl_seconds` | Overrides both defaults; useful for CI / batch runs |

Behavior: `VerificationCache` in `scripts/config.py` reads `verify_cache_ttl_seconds` from env.json at load time. If unset, it falls back to 3600 (1h). Orchestrator detects `--series` and temporarily sets `VERIFY_CACHE_TTL_SECONDS=86400` in the environment for the duration of the run.

---

## Output: Inline Verification Report

Report **only failures and pending items**. Passing checks produce no output.

```markdown
## Verification Results

### Failures
- [URL] returned 404, replaced with [new URL]
- [command X] not found in official docs, removed

### Pending (needs user input)
- [Tool Y] advanced config options could not be verified, marked [needs verification]

(If nothing failed: "All checks passed.")
```

**This report is non-blocking.** The article-craft pipeline continues even if some checks fail. Failures are noted in the report for the author to address.

---

## Enforcement Rules

| Situation | Action |
|-----------|--------|
| Fabricated command/feature | Reject -- do not include in article |
| Unverified claim | Ask user or omit |
| Unverifiable workflow step | Mark or remove |
| 404 link | Remove or replace |
| Questionable content | Ask user -- never guess |

---

## Verification Philosophy

All technical content must satisfy at least one of:
1. **Official docs verified** (most reliable) -- found via WebSearch/WebFetch
2. **Trusted tools whitelist** (pre-verified) -- see `${CLAUDE_PLUGIN_ROOT}/skills/verify/trusted-tools.md`
3. **User-provided info** (needs confirmation) -- user explicitly provided and confirmed
4. **Stable knowledge-base info** (moderate trust) -- fundamental CS concepts, standard protocols, classic algorithms

Content that satisfies none of the above: mark as `[needs verification]`, ask the user, or remove. **Never fabricate or guess.**

Trust levels:
- **Trust**: basic concepts, algorithm principles, language syntax, classic design patterns, standard protocols (HTTP, TCP/IP)
- **Verify**: specific commands, API calls, config file formats, version-specific features
- **Never trust without verification**: tools released after 2024, new version features, rapidly changing tech

---

## Source Trust Engine

### Trust Tier Classification

Every URL source is classified into a trust tier before verification:

| Tier | Source Type | Trust Level | Verification Required |
|------|------------|-------------|----------------------|
| T0 | Official docs (docs.example.com, example.com/docs) | **Highest** | Skip link checks, verify commands only |
| T1 | GitHub official repo (owner/example) | **High** | Verify commands/features via --help |
| T2 | Official blog (blog.example.com) | **Medium-High** | Verify key claims, skip all links |
| T3 | Community docs (github.com/wiki, community.example.com) | **Medium** | Verify all critical links |
| T4 | Tutorial sites, blog posts | **Low-Medium** | Verify everything |
| T5 | Social media, forums | **Low** | Verify all, assume nothing |

### Auto-Detection Rules

Determine trust tier automatically:

```
URL: https://docs.docker.com/engine/reference/commandline/run
       ↓
Extract domain: docs.docker.com
       ↓
Pattern match:
  - docs.{tool}.com → T0 (official docs)
  - {tool}.com/docs → T0 (official docs path)
  - github.com/{owner}/{repo} → T1 if official, T3 if fork
  - blog.{tool}.com → T2 (official blog)
  - medium.com/@user → T4
  - stackoverflow.com → T4
```

**Override rules:**
- `/release` or `/changelog` path → T2 (official, but claims need verification)
- `/blog` path → T2
- `/en/` vs `/zh/` → same tier, verify content parity
- `/vN.N.N/` versioned docs → T0 but verify version match

### GitHub Repository Trust Scoring

For GitHub URLs, calculate a trust score:

| Metric | Score Weight | Good | Bad |
|--------|-------------|------|-----|
| Stars | 20% | >1k | <100 |
| Last commit | 20% | <3 months | >1 year |
| Open issues | 15% | <500 | >1000 |
| PR merge ratio | 15% | >70% | <50% |
| Owner type | 20% | org/owner verified | personal |
| Releases | 10% | has recent release | none |

```
Score = Stars_wt + Recency_wt + Issues_wt + PR_wt + Owner_wt + Release_wt
        = 20 + 20 + 15 + 15 + 20 + 10 = 100

High Trust:  >= 70
Medium:     40-69
Low:        < 40
```

**Quick check command:**
```bash
gh repo view {owner}/{repo} --json name,stargazerCount,pushedAt,openIssuesCount,owner --jq '.'
```

### Official Source Indicators

Detect if a source is official:

**Positive indicators:**
- URL contains official domain (docs.{tool}.com, {tool}.com/docs)
- GitHub owner matches tool name exactly
- README has "Official" badge
- Description contains "official"
- Repository is verified (GitHub check)

**Negative indicators:**
- URL is a Medium/Sponsored post
- Author bio mentions "affiliate" or "sponsored"
- Content is significantly older than tool version
- Tutorial duplicates official docs without adding value
