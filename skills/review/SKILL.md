---
name: article-craft:review
version: 1.4.9
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

### Phase 2: Built-in Content Scoring (publish mode only) — diagnostic

**If mode is `draft`**: skip this phase. Report self-check results only.

**If mode is `publish`**: score the article on 7 dimensions, surface actionable
feedback, let the user decide what to do. **No auto-modify loop.**

#### Why scoring-only

Prior versions (≤ v1.4.3) ran up to 3 rounds of auto-modify whenever `score < 55`,
with an "oscillation guard" to break early when revisions stopped improving. In
practice the auto-modify instruction — "for dimensions <7/10, fix corresponding
issues" — was too open-ended to reliably converge. Rounds often regressed one
dimension while fixing another (the very oscillation the guard detected), and
auto-modify risked editing the article after the images stage had shipped, which
could orphan `<!-- IMAGE: -->` placeholders or CDN URLs (see Rule 11 warning).

v1.4.4 reframes Phase 2 as **diagnostic only**: score it, tell the user
exactly what's weak and where, let them pick the fix. If they want review to
also edit, they invoke `/article-craft:review` with a targeted hint (e.g. the
"AI 痕迹" dimension) or re-run `/article-craft:write` on specific sections.

#### 7-Dimension Scoring (Embedded)

Score each dimension 0-10, total 70. Threshold: **55/70**.

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

1. Read the article.
2. For each dimension, assign a 0–10 score and a one-line justification citing
   specific line numbers or section headings where the deduction came from.
3. Sum to a `/70` total.
4. Build a per-dimension feedback list. For every dimension scoring `<7/10`, emit:
   - **What failed** (one line, concrete — e.g. "Section 「为什么选 uv」 has only 1 code block, Rule 6 wants ≥2")
   - **Where to fix** (file:line or section heading — actionable)
   - **Suggested action** (e.g. "re-run /article-craft:write on this section with depth=deep", or "replace 综上所述 in L47")

5. **Return verdict based on score, not auto-edit:**
   - `score >= 55` → return **PASS** with full scorecard
   - `score < 55` → return **NEEDS_REVISION** with scorecard + actionable feedback list + AskUserQuestion

#### NEEDS_REVISION prompt

Use AskUserQuestion with these options:

```
Question: "Article scored {score}/70 (threshold: 55/70). Phase 2 is diagnostic
           — pick how to proceed:"
Options:
  - Publish anyway — accept current score and continue to publish stage
  - Abort — stop pipeline, keep article at current path for manual edit
  - Re-run write with hints — re-invoke /article-craft:write targeting the
    weakest dimension(s) listed above (user is shown which dimensions)
```

Do NOT embed an auto-revision loop. Each round of edits is a new, explicit user
decision. If the user picks "Re-run write with hints", the orchestrator drops
back to the write stage with the feedback list as input; it does not stay inside
review.

**Invariants** (apply to every path):

- Review never touches handoff-contract comments (`<!-- IMAGE: -->`,
  `<!-- PROMPT: -->`, `<!-- SCREENSHOT: -->`, `<!-- HARVEST: -->`) or CDN image
  URLs. Images have already been generated by the time review runs; any edit
  would risk orphaning them.
- Review never regenerates the whole article.
- Phase 2 outputs a scorecard + feedback list; mutations only happen if the
  user explicitly chose "Publish anyway" (no mutation) or "Re-run write with hints"
  (mutation happens in write, not review).

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

### Phase 2: Diagnostic Scoring (7 dimensions)
| Dimension | Score | Notes |
|-----------|-------|-------|
| AI 痕迹 | X/10 | L47 has "综上所述"; section 2 repeats "另外" 3× in a row |
| 标题与 Hook | X/10 | Hook is 118 chars (Rule 2 wants ≤100) |
| 内容深度 | X/10 | "为什么选 uv" section has only 1 code block (Rule 6 wants ≥2) |
| 结构可读 | X/10 | ... |
| 代码质量 | X/10 | ... |
| 结尾行动力 | X/10 | ... |
| 图片配置 | X/10 | ... |
| **Total** | **X/70** | **PASS (≥55) / NEEDS_REVISION (<55)** |

### Feedback (dimensions scoring <7/10 only)
For each weak dimension, print:
- **What failed**: one-line concrete issue
- **Where**: file:line or section heading
- **Suggested action**: e.g. "re-run /article-craft:write on section X",
  "delete L47 redundant sentence", "add a second code block to section Y"

### Verdict
- **PASS** — score ≥ 55, or score < 55 but user chose "Publish anyway"
- **NEEDS_REVISION_RERUN_WRITE** — user chose "Re-run write with hints"
  (orchestrator drops back to write stage with feedback as input)
- **ABORT** — user chose "Abort"
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
