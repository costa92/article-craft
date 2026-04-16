---
name: article-craft:review
version: 1.4.3
description: "Quality gate for articles — built-in self-check rules + embedded content scoring. All-in-one review without external dependencies."
allowed-tools:
  - Read
  - Edit
  - Bash
  - Grep
  - AskUserQuestion
---

# Article Review (Quality Gate)

Run self-check rules against the article, then perform built-in content scoring. This skill is the quality gate between writing and publishing — **no external dependencies required**.

**Invoke**: `/article-craft:review`

**Features**:
- Phase 1: 11 self-check rules (embedded)
- Phase 2: 7-dimension content scoring (embedded)
- Self-contained: no external skill installation needed

---

## Inputs

- **Article file path**: absolute path to the `.md` file to review
- **Mode**: `publish` (default) or `draft`

If invoked standalone (file path not provided), use AskQuestion:
```
Question: "Which article file should I review?"
(free-form input: provide the absolute path to the .md file)
```

---

## Execution Steps

### Phase 1: Self-Check (all 11 rules)

Canonical source: **`${CLAUDE_PLUGIN_ROOT}/references/self-check-rules.md`**.

Read that file first. It contains every rule body, canonical grep pattern,
severity, auto-fix mapping, and escalation semantics. Do **not** re-type the
rules here — the review skill's job is to apply them, not re-state them.

**Execution order for review (Phase 1 enforcer):**

1. **Rule 11 first** (ASCII diagrams) — run the canonical grep. On violation:
   mark FAIL, **block Phase 2**, and trigger `AskUserQuestion` with options:
   (a) open article for manual fix, (b) re-run `/article-craft:write`, (c) abort.
   Review is **detect-only** for Rule 11 — never insert placeholders (the images
   stage has already run; new placeholders would be orphaned).

2. **Rule 7b second** (min AI image count) — run the degradation detection
   block from rules.md 7b **before** the threshold check. If unresolved
   `<!-- IMAGE: -->` placeholders exist, downgrade to WARNING and skip any
   injection attempt. Never add placeholders here (same orphan risk as Rule 11).

3. **Rules 1, 2, 3, 4, 5, 8, 10** — apply the canonical grep / inspection,
   fix violations in place with Edit. Use the auto-fix mapping in rules.md
   where it exists; otherwise rewrite per the rule body.

4. **Rules 6, 7, 9** — detect only; these are write-owned (6) or already
   handled upstream (7, 9). Report PASS / WARNING without auto-fix.

**General rules for Phase 1:**

- Never touch handoff-contract comments (`<!-- IMAGE: -->`, `<!-- PROMPT: -->`,
  `<!-- SCREENSHOT: -->`, `<!-- HARVEST: -->`) or CDN image URLs during any fix.
- A rule marked WARNING in rules.md must not block Phase 2 (only FAIL does).
- Record every fix for the Phase 2 AI 痕迹 dimension input.

---

### Phase 2: Built-in Content Scoring (publish mode only)

**If mode is `draft`**: skip this phase. Report self-check results only.

**If mode is `publish`**: Perform 7-dimension scoring directly.

#### 7-Dimension Scoring (Embedded)

Score each dimension 0-10, total 70 points. Pass threshold: **55/70**.

| # | Dimension | Weight | Scoring Criteria |
|---|-----------|--------|----------------|
| 1 | **AI 痕迹** | 10 | 多样化段落结构、个人视角、开场变化 |
| 2 | **标题与 Hook** | 10 | 标题公式符合、Hook 痛点清晰、100字内 |
| 3 | **内容深度** | 10 | 每章 ≥2 代码块、技术细节充分 |
| 4 | **结构可读** | 10 | 段落长度合理、过渡自然、层次清晰 |
| 5 | **代码质量** | 10 | 可运行、有注释、错误处理 |
| 6 | **结尾行动力** | 10 | 具体下一步行动、非模板化结尾 |
| 7 | **图片配置** | 10 | 节奏图匹配、内容相关、非装饰 |

#### Scoring Execution

1. Read article and analyze each dimension
2. Score each 0-10 based on criteria
3. Sum total (70 max); record as `score_0`
4. **If score >= 55**: pass. Proceed to output.
5. **If score < 55**: auto-modify and re-score. Repeat up to **3 rounds**, with oscillation guard.

**Auto-modify strategy**:
1. Score-based fixes — For dimensions <7/10, fix corresponding issues
2. Re-score after each modification; call the result `score_{round}`
3. Never regenerate entire article — only edit weak sections
4. **Preserve handoff contracts** — never touch `<!-- IMAGE: -->`, `<!-- PROMPT: -->`, `<!-- SCREENSHOT: -->` comments or CDN image URLs during auto-modify. Revisions must not orphan existing images (see Rule 11 warning above).

**Oscillation guard** — after each round, compare `score_{round}` to `score_{round-1}`:
- If `score_{round} > score_{round-1}` and still < 55: continue to next round
- If `score_{round} <= score_{round-1}`: **break the loop immediately**, do not burn the remaining rounds. The revision is not improving things, likely oscillating between conflicting fixes (e.g., fixing "AI 痕迹" introduces a red-flag word, which the next round fixes by reintroducing AI-pattern phrasing). Jump to the user-decision step.

6. **After loop ends** (3 rounds exhausted OR oscillation detected): ask the user:
   ```
   Question: "The article scored {current}/70 after {N} rounds (threshold: 55/70).
              {If oscillation: 'Score stopped improving at round {N}.'}
              How to proceed?"
   Options:
     - Continue revising -- attempt another round (ignores oscillation guard)
     - Publish anyway -- accept current score
     - Abort -- stop pipeline
   ```

**Why embedded**: No external dependencies. Self-contained scoring.

---

## Output: Score + Feedback Report

```markdown
## Review Results

### Phase 1: Self-Check (11 rules)
- Rule 1 (Red-Flag Words): PASS / FIXED (N violations rewritten)
- Rule 2 (Hook Length): PASS / FIXED
- Rule 3 (Closing): PASS / FIXED
- Rule 4 (Description): PASS / FIXED
- Rule 5 (Anti-AI Structure): PASS / FIXED
- Rule 6 (Chapter Depth): PASS / WARNING (section X is thin)
- Rule 7 (Duplicate Images): PASS
- Rule 7b (Minimum AI Image Count): PASS / WARNING (need N more images)
- Rule 8 (WeChat Links): PASS / FIXED
- Rule 9 (Mermaid Residue): PASS
- Rule 10 (References Inline): PASS / FIXED
- Rule 11 (ASCII Diagram Check): PASS / FIXED (N diagrams converted)

### Phase 2: Built-in Scoring (7 dimensions)
| Dimension | Score | Status |
|-----------|-------|-------|
| AI 痕迹 | X/10 | PASS/FAIL |
| 标题与 Hook | X/10 | PASS/FAIL |
| 内容深度 | X/10 | PASS/FAIL |
| 结构可读 | X/10 | PASS/FAIL |
| 代码质量 | X/10 | PASS/FAIL |
| 结尾行动力 | X/10 | PASS/FAIL |
| 图片配置 | X/10 | PASS/FAIL |
| **Total** | **X/70** | **PASS (>=55)** |

Key feedback: [main points for improvement]
```

---

## Standalone Mode

When invoked directly (not as part of the orchestrator pipeline):

1. AskQuestion for the article file path if not provided.
2. AskQuestion for the mode:
   ```
   Question: "Review mode?"
   Options:
     - Publish -- full review with embedded 7-dim scoring (>= 55/70 required)
     - Draft -- self-check only, skip scoring phase
   ```
3. Execute the review steps above.
4. Output the report.
