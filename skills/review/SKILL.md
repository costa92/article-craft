---
name: article-craft:review
version: 1.6.24
description: "Quality gate for articles — canonical self-check rules + built-in content scoring. All-in-one review without external dependencies."
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
- Phase 1: all 17 rules from `references/self-check-rules.md` via `scripts/review_selfcheck.py`
- Phase 2: 7-dimension built-in content scoring
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

### Phase 1: Self-Check (17 rules via `scripts/review_selfcheck.py`)

Canonical source: **`${CLAUDE_PLUGIN_ROOT}/references/self-check-rules.md`** (rule bodies).
Canonical implementation: **`${CLAUDE_PLUGIN_ROOT}/scripts/review_selfcheck.py`** (executable).

Phase 1 **never** asks the agent to write greps by hand. The agent calls the
script once with `--json`, parses the structured result, and acts on it.
This guarantees write / lint / review all enforce the same rule definitions
and never drift apart.

#### How to invoke

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/review_selfcheck.py \
  /ABSOLUTE/PATH/article.md --json
```

Optional flags:
- `--rules 1,3,5` — run only the listed rule IDs (useful when re-checking after a targeted fix).
- `--write-gate` — pre-save GATE subset (rules 1/2/6/11/13/16); review never needs this, write does.
- (no flag) — runs all 17 rules.

Exit codes:
- `0` — every rule passed (article ready for Phase 2 scoring).
- `1` — at least one rule failed (parse JSON, act on it before unblocking Phase 2).
- `2` — file not found.

#### JSON shape

The script emits a JSON array, one entry per rule:

```json
[
  {
    "rule_id": 1,
    "rule_name": "红旗词汇",
    "passed": false,
    "is_gate": false,
    "details": "发现 4 个红旗词",
    "violations": [
      {"line": 13, "text": "...闭环...", "suggestion": "替换「闭环」为更自然的表达", "severity": "FAIL"}
    ],
    "skipped": false,
    "skip_reason": null,
    "meta": {}
  },
  ...
]
```

#### Acting on the JSON

After parsing, walk the array in this order:

1. **Rule 11 first** (`rule_id == 11`, `is_gate == true`) — if `passed == false`,
   mark FAIL, **block Phase 2**, and trigger `AskUserQuestion` with options:
   (a) open article for manual fix, (b) re-run `/article-craft:write`, (c) abort.
   Review is **detect-only** for Rule 11 — never insert placeholders (the images
   stage has already run; new placeholders would be orphaned).

2. **Rule 7b second** (`rule_id == 7` may include a `meta.degraded` field for
   unresolved placeholders — see rules.md Rule 7b). If unresolved
   `<!-- IMAGE: -->` placeholders exist, downgrade to WARNING and skip
   any injection attempt. Never add placeholders here (same orphan risk).

3. **Rules 1, 2, 3, 4, 5, 8, 10, 12, 15** — for any `passed == false`, fix the
   `violations[].line` in place with Edit. The `suggestion` field gives the
   per-violation auto-fix hint; the canonical mapping for prose rewrites is
   still in `references/self-check-rules.md` Rule 1 (red-flag word table).
   Re-run the script with `--rules <ids>` after edits to confirm.

4. **Rules 6, 7, 9, 11, 13, 14, 16, 17** — detect only at the review stage
   (these are owned by write or already handled upstream). Report
   PASS / WARNING; do **not** auto-fix. For Rule 6 (shallow chapters) and
   Rule 17 (register naturalness) the deductions flow into the Phase 2
   AI 痕迹 / 内容深度 dimensions, not into a fix loop.

**General rules for Phase 1:**

- Never touch handoff-contract comments (`<!-- IMAGE: -->`, `<!-- PROMPT: -->`,
  `<!-- SCREENSHOT: -->`, `<!-- HARVEST: -->`) or CDN image URLs during any fix.
- A rule marked WARNING in `references/self-check-rules.md` must not block Phase 2 (only FAIL does).
- Record every fix for the Phase 2 AI 痕迹 dimension input.
- **Never re-implement a rule via Bash grep when the script already has it.**
  If a rule is missing from `_RULE_DISPATCH` in `review_selfcheck.py`, that's
  a script bug — file it, don't paper over it in this SKILL.md.

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

## Output

```markdown
## Review Results

### Phase 1: Self-Check (17 rules)
- Rule  1: PASS / FIXED / WARNING
- Rule  2: PASS / FIXED / WARNING
- Rule  3: PASS / FIXED / WARNING
- Rule  4: PASS / FIXED / WARNING
- Rule  5: PASS / FIXED / WARNING
- Rule  6: PASS / FIXED / WARNING
- Rule  7: PASS / FIXED / WARNING
- Rule  8: PASS / FIXED / WARNING
- Rule  9: PASS / FIXED / WARNING
- Rule 10: PASS / FIXED / WARNING
- Rule 11: PASS / FIXED / WARNING
- Rule 12: PASS / FIXED / WARNING
- Rule 13: PASS / FIXED / WARNING
- Rule 14: PASS / FIXED / WARNING
- Rule 15: PASS / FIXED / WARNING
- Rule 16: PASS / FIXED / WARNING
- Rule 17: PASS / FIXED / WARNING

### Rules Index (Phase 1 reference)

> Names below mirror `_RULE_DISPATCH` in `scripts/review_selfcheck.py`. If
> they ever drift, the script is the source of truth — not this list.
> Full rule bodies and grep patterns live in `references/self-check-rules.md`.

- **Rule 1: 红旗词汇 (Red-Flag Words)** — detects 无缝/赋能/链路/实际上/综上所述 等套话；auto-fix per rule mapping.
- **Rule 2: Hook 长度 (Hook Length)** — opening paragraph ≤100 CJK chars + no template openers.
- **Rule 3: 结尾禁用词 (Forbidden Closings)** — bans 希望本文/点个在看/欢迎留言 等模板化结尾.
- **Rule 4: Description 字段 (Description Field)** — YAML frontmatter must include description ≤120 chars.
- **Rule 5: 反 AI 结构 (Anti-AI Structure)** — flags template cadence, missing personal/concrete anchors.
- **Rule 6: 章节深度 (Chapter Depth)** — each `##` section must have ≥N code blocks (N varies by writing style).
- **Rule 7: 重复图片 (Duplicate Images)** — flags two near-identical images in the same section.
- **Rule 8: WeChat 外链 (External Links)** — replaces bare URLs with search guidance for WeChat compat.
- **Rule 9: Mermaid 残留 (Mermaid Residue)** — blocks unrendered `\`\`\`mermaid` blocks (must be PNG'd).
- **Rule 10: 参考资料内联 (References Inline)** — bans standalone 参考资料 section; use inline `[Name](url)`.
- **Rule 11: 占位符残留 (Placeholder Residue) ⭐ GATE** — blocks unresolved `<!-- IMAGE: -->` / `<!-- SCREENSHOT: -->` / `<!-- HARVEST: -->`.
- **Rule 12: 模板化摘要 (Template Summaries)** — detects 本文从X出发拆解 / 本文将详细介绍 等开场套路.
- **Rule 13: 代码块语言标识 (Codeblock Language Tag)** — every fenced block must declare a language.
- **Rule 14: ASCII 图表残留 (ASCII in Code Blocks)** — flags box/arrow chars inside non-executable code blocks.
- **Rule 15: 孤立 PROMPT 注释 (Orphan PROMPT)** — deletes `<!-- PROMPT: -->` not paired with an `<!-- IMAGE: -->` above.
- **Rule 16: PROMPT 文字渲染风险 (PROMPT Text-Rendering Risk)** — blocks CJK or "render this text" instructions in PROMPT (Gemini can't render text).
- **Rule 17: Register Naturalness (tone-aware)** — checks first-person density, strong-opinion presence, summary-phrase ceiling, and sentence-length CV against tier-specific thresholds (`scripts/config.py TONE_THRESHOLDS`). The active tone is read from frontmatter `tone:` with style-default fallback.

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

### Feedback
For each weak dimension, print:
- **What failed**: one-line concrete issue
- **Where**: file:line or section heading
- **Suggested action**: one short action

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
     - Publish -- full review with built-in 7-dim scoring (>= 55/70 required)
     - Draft -- self-check only, skip scoring phase
   ```
3. Execute the review steps above.
4. Output the report.
