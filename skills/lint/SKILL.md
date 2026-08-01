---
name: article-craft:lint
version: 1.10.0
description: "Check and auto-fix article style violations using canonical self-check rules. Use to clean up articles before review."
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

## Checks

Canonical source: **`${CLAUDE_PLUGIN_ROOT}/references/self-check-rules.md`**.

Lint runs the **auto-fixable subset** of the canonical rules. Read that file
for each rule's body, grep pattern, and fix mapping — do not re-type them here.

**Rule scope for lint:**

| Rule(s) | lint behavior |
|---------|---------------|
| 1, 2, 3, 4, 5, 10 | `--fix` applies the canonical auto-fix mapping from `references/self-check-rules.md` |
| 9, 11 | report only; do not auto-fix |

**Out of scope for lint** (flag in report, do not attempt): rules 6 (chapter
depth — needs content), 7 / 7b (image count — needs images stage), 8 (WeChat
external links — context-dependent).

**Execution:**

1. Read the article with the Read tool.
2. For each rule above, run the canonical grep / inspection from rules.md.
3. Record violations with line numbers.
4. If `--fix`:
   - Apply the rule's auto-fix mapping from rules.md via the Edit tool.
   - For Rule 5, run:
     ```bash
     python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lint_article.py --article /ABSOLUTE/PATH/article.md --fix
     ```
     This removes the safest mechanical AI-style filler:
     `本文将...` / `接下来我们将...` / `下面分别...` /
     `可以看到...` / `本质上...` / `从这个角度看...` /
     paragraph starters like `首先...` / `其次...` / `另外...`,
     rewrites red-flag words like `赋能` / `一站式` / `链路`,
     removes engagement closings like `希望本文对你有帮助`,
     deletes a trailing standalone `## 参考资料` section,
     and reports Rule-5-style high-risk sections such as
     `总览: 连续 3 段缺少具体锚点`
   - Never touch handoff-contract comments (`<!-- IMAGE: -->`, `<!-- PROMPT: -->`,
     `<!-- SCREENSHOT: -->`, `<!-- HARVEST: -->`) or CDN image URLs.
   - After all fixes, re-run every check to verify.
5. Emit the report (see Output section).

---

## Output

Report rows use the canonical rule numbers from `references/self-check-rules.md`
(1, 2, 3, 4, 5, 9, 10, 11). Do not renumber or rename them.

### Report mode (no --fix)

```
## Lint Report: article.md

| Rule | Name | Status | Details |
|------|------|--------|---------|
| 1  | Red-flag words        | FAIL (3) | L12: "赋能", L45: "无缝", L67: "一站式" |
| 2  | Hook length           | PASS | 87 chars |
| 3  | Closing paragraph     | PASS | — |
| 4  | Description field     | FAIL | Missing |
| 5  | Transition words      | PASS | — |
| 9  | Mermaid residue       | PASS | — |
| 10 | References inline     | FAIL | Standalone section at L120 |
| 11 | ASCII diagrams        | PASS | — |

Total: 2 FAIL, 6 PASS
Run with --fix to auto-correct fixable violations.
```

### Fix mode (--fix)

Apply the canonical auto-fix mapping per rules.md for each FAIL; re-run every
check to verify. Report before/after:

```
## Lint Fix Report: article.md

| Rule | Name | Before | After | Action |
|------|------|--------|-------|--------|
| 1  | Red-flag words    | FAIL (3) | PASS | Applied rules.md auto-fix mapping (3 instances) |
| 5  | Anti-AI structure | FAIL     | PASS | Removed roadmap filler / empty judgement wrappers / paragraph starters |
| 3  | Closing paragraph | FAIL     | PASS | Removed engagement-style closing and kept concrete ending |
| 4  | Description field | FAIL     | PASS | Generated from first section |
| 10 | References inline | FAIL     | PASS | Deleted standalone section (inline links preserved) |

Fixed: 3 rules
Remaining: 0 (Mermaid rule 9 is report-only — run /article-craft:images)
```

If `lint_article.py` detects high-risk sections that cannot be safely auto-fixed,
append them after the fix report as a review queue, for example:

```markdown
### High-Risk Sections
- 总览: 连续 3 段缺少具体锚点
- 判断: 连续 2 段总结腔且缺少锚点
```

### Tone resolution

`lint_article.py` automatically resolves the tone tier from article frontmatter
(`tone: neutral|casual|opinionated`). Without explicit `--tone` override on the
CLI, the script reads frontmatter, falls back to writing-style default
(`STYLE_TO_TONE_DEFAULT`), and finally to `neutral`.

To force-override, pass `--tone={neutral,casual,opinionated}` on the CLI.

### Inline disable

To exempt a region from lint (e.g., a quoted sentence using a red-flag word
intentionally):

````markdown
<!-- lint:disable rule1 rule5 -->
"This product 赋能 millions of developers" - 引用某 CEO 原话
<!-- lint:enable rule1 rule5 -->
````

Special rule_id `all` disables every rule in the region. An unmatched
`<!-- lint:disable -->` at end of file produces a warning but does not
abort the lint run.

Available rule_ids: `rule1` (red-flag words), `rule3` (closing patterns),
`rule5` (anti-AI structure / cadence). Use `all` to disable all rules.

---

## Standalone Mode

When invoked directly:
1. AskQuestion for the article file path if not provided
2. AskQuestion for mode: "Report only or auto-fix?"
3. Execute checks
4. Output report

---

## Integration with Review Skill

The lint skill is a **lightweight pre-check** — run it before the full review to eliminate mechanical issues. The review skill's Phase 1 (self-check) covers the same rules, but lint is faster because it skips Phase 2 (8-dim diagnostic scoring).

Recommended flow:
```
/article-craft:lint article.md --fix    # Quick mechanical fixes (~10 seconds)
/article-craft:review article.md        # Full quality gate with scoring (~2 minutes)
```
