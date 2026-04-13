---
name: article-craft:lint
version: 1.3.4
description: "Check and auto-fix article style violations — red-flag words, hook length, closing patterns, AI traces. Use to clean up articles before review."
allowed-tools:
  - Read
  - Edit
  - Bash
  - Grep
  - AskUserQuestion
---

# Lint — Style Check & Auto-Fix

Scan an article for style violations and optionally auto-fix them. Faster than running the full review skill — focuses only on mechanical, rule-based issues.

**Invoke**: `/article-craft:lint [article-path] [--fix]`

---

## Modes

| Mode | Behavior |
|------|----------|
| **Report only** (default) | Scan and list all violations, no changes |
| **Auto-fix** (`--fix`) | Fix violations in-place using the Edit tool |

---

## Inputs

- **Article file path**: absolute path to the `.md` file to lint
- If not provided, use AskQuestion to ask for the path

---

## Checks (in order)

### Check 1: Red-Flag Words

```bash
grep -nE '无缝|赋能|一站式|综上所述|总而言之|值得注意的是|不难发现|深度解析|全面梳理|链路|闭环|抓手|底层逻辑|方法论|降本增效|实际上|事实上|显然|众所周知|不难看出' /path/to/article.md
```

Also scan for:
- "颠覆" / "极致" / "完美解决"
- "在当今快速发展的..." / "随着...的不断发展..."
- "让我们一起探索..."
- Unverified quantitative claims ("效率提升 300%")

**Auto-fix strategy**: Use the Edit tool to replace each match:
- "无缝" → rewrite sentence without the word (context-dependent)
- "赋能" → "支持" / "帮助" / remove
- "一站式" → "统一的" / "集成的"
- "综上所述" / "总而言之" → delete transition, start next sentence directly
- "值得注意的是" → delete, merge into next sentence
- "实际上" / "事实上" → delete (usually filler)
- "显然" / "众所周知" → delete (assertion without evidence)

### Check 2: Hook Length

Count Chinese characters in the first paragraph (after YAML frontmatter, excluding code blocks).

- **Pass**: ≤ 100 characters
- **Fail**: > 100 characters

**Auto-fix strategy**: Split the hook into two paragraphs — first paragraph ≤ 100 chars (pain point + solution), second paragraph (value proposition).

### Check 3: Forbidden Closings

Scan the last 3 paragraphs for:
- "希望本文对你有帮助"
- "如果有问题欢迎留言"
- "欢迎在评论区分享"
- "点个在看" / "转发给朋友"
- "你的点赞是我最大的动力"

**Auto-fix strategy**: Replace the closing with a concrete next-step action from the article content (e.g., a command to run, a link to explore).

### Check 4: Description Field

Check YAML frontmatter for `description` field:
- Exists?
- ≤ 120 characters?
- Not identical to title?

**Auto-fix strategy**: Generate a 1-2 sentence summary from the article's first section.

### Check 5: Consecutive Transition Words

Scan for 2+ consecutive paragraphs starting with the same transition:
- "此外" / "另外" / "同时" / "值得注意的是" / "除此之外"

**Auto-fix strategy**: Delete the transition word from the second occurrence — jump straight to the point.

### Check 6: Mermaid Code Block Residue

```bash
grep -n '```mermaid' /path/to/article.md
```

**Auto-fix strategy**: Cannot auto-fix (needs rendering to PNG). Report only — suggest user run images skill.

### Check 7: Standalone Reference Section

Check if article ends with a "参考资料" / "参考链接" / "References" section.

**Auto-fix strategy**: Delete the section. Inline links are already handled by the WeChat converter.

### Check 8: ASCII Diagram Residue

Scan all code blocks for box-drawing characters (`│ ├ └ ┌ ┐ ─ ▼ ▶ ←→ ──→ ←──`) that indicate an ASCII diagram rather than executable code.

```bash
grep -nE '│|├|└|┌|┐|─|▼|▶|←→|──→|←──' /path/to/article.md
```

Filter out matches inside executable code blocks (bash/python/json). Only flag code blocks that contain these characters AND are not runnable code.

**Auto-fix strategy**: Replace the ASCII code block with an `<!-- IMAGE -->` placeholder using the article's shared visual style prefix. The images skill will generate the actual image later.

---

## Output

### Report mode (no --fix)

```
## Lint Report: article.md

| # | Check | Status | Details |
|---|-------|--------|---------|
| 1 | Red-flag words | FAIL (3) | L12: "赋能", L45: "无缝", L67: "一站式" |
| 2 | Hook length | PASS | 87 chars |
| 3 | Forbidden closing | PASS | — |
| 4 | Description field | FAIL | Missing |
| 5 | Transition words | PASS | — |
| 6 | Mermaid residue | PASS | — |
| 7 | Reference section | FAIL | Found at L120 |

Total: 2 FAIL, 5 PASS
Run with --fix to auto-correct fixable violations.
```

### Fix mode (--fix)

Run each check. For each FAIL, apply the auto-fix strategy using the Edit tool. After all fixes, re-run all checks to verify. Report before/after:

```
## Lint Fix Report: article.md

| # | Check | Before | After | Action |
|---|-------|--------|-------|--------|
| 1 | Red-flag words | FAIL (3) | PASS | Rewrote 3 instances |
| 4 | Description | FAIL | PASS | Generated from first section |
| 7 | Reference section | FAIL | PASS | Deleted (inline links preserved) |

Fixed: 3 issues
Remaining: 0 issues (6 in Mermaid — manual fix needed)
```

---

## Standalone Mode

When invoked directly:
1. AskQuestion for the article file path if not provided
2. AskQuestion for mode: "Report only or auto-fix?"
3. Execute checks
4. Output report

---

## Integration with Review Skill

The lint skill is a **lightweight pre-check** — run it before the full review to eliminate mechanical issues. The review skill's Phase 1 (self-check) covers the same rules, but lint is faster because it skips Phase 2 (7-dim scoring) and the 3-round auto-revision loop.

Recommended flow:
```
/article-craft:lint article.md --fix    # Quick mechanical fixes (~10 seconds)
/article-craft:review article.md        # Full quality gate with scoring (~2 minutes)
```
