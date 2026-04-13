---
name: article-craft:review
version: 1.3.4
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

Read the article file, then check each rule below. Fix violations inline using the Edit tool before proceeding. Do not leave violations for the reviewer to catch.

Reference: `${CLAUDE_PLUGIN_ROOT}/references/self-check-rules.md`

#### Rule 1: Red-Flag Words

Search the article with Grep for these patterns:

```bash
Search the article with Python regular expressions for red-flag words
```

Also flag:
- "颠覆" / "极致" / "完美解决"
- "在当今快速发展的..." / "随着...的不断发展..."
- "让我们一起探索..."
- Unverified quantitative claims like "效率提升 300%"

Every match must be rewritten. These words trigger deductions in the "AI 痕迹" scoring dimension.

#### Rule 2: Hook Length

The first paragraph (after frontmatter) must be **100 characters or fewer** (Chinese characters, excluding code blocks). It must contain:
1. Pain point or scenario
2. Solution / tool name
3. Reading value

Forbidden openers: "在当今...的时代", "随着...的发展", "你是否也有这样的困扰？", starting with a definition "XXX 是一个..."

#### Rule 3: Closing Paragraph

The article must end with a concrete next-step action or brief technical outlook (max 2 sentences).

Forbidden closings:
- "希望本文对你有帮助"
- "如果有问题欢迎留言"
- "欢迎在评论区分享"
- "点个在看" / "转发给朋友"
- "你的点赞是我最大的动力"
- "如果这篇文章对你有帮助"

Good examples:
- "装好 uv 后，在现有项目里跑一次 `uv pip install -r requirements.txt`，体感一下速度差异。"
- "uv 的 workspace 功能还在快速迭代，monorepo 支持值得关注。"

#### Rule 4: Description Field

The YAML frontmatter must include a `description` field:
- Max 120 characters (Chinese)
- Must be a meaningful abstract, not a copy of the title
- Used as the WeChat article summary

#### Rule 5: Anti-AI Structure

- **Vary paragraph length**: consecutive paragraphs must not use the same structure (e.g., "concept -> explain -> code" twice in a row). Mix: code-first with reverse explanation, Q&A style, experience-then-principle, comparison table then conclusion.
- **Personal perspective** (at least 2 per article): first-person observations such as bug/pitfall experience, choice rationale, judgement, real benchmarks.
- **Diverse paragraph openings**: never start 2 consecutive paragraphs with "此外" / "另外" / "同时" / "值得注意的是". Replace transition words with direct content.

#### Rule 6: Chapter Depth

Every technical section must contain **at least 2 commands/code snippets plus explanatory text**. A section with only 1 command and 1 sentence is too shallow.

#### Rule 7: Duplicate Image Check

Within the same section (same `##` heading), do not include two images that serve the same purpose.

#### Rule 7b: Minimum AI Image Count

Verify the article meets the minimum AI image count based on word count:

| 文章字数 | 最少 AI 图片数（IMAGE 占位符） |
|---------|--------------------------|
| ≤ 1500 字 | 1 张（封面） |
| 1500-3000 字 | 2 张（封面 + 1 节奏图） |
| > 3000 字 | 3 张（封面 + 2 节奏图） |

> SCREENSHOT 占位符不计入此数量（截图由 screenshot skill 处理）

**How to check**:
```bash
# 统计已生成的 AI 图片数量（CDN 链接）
grep -cE '!\[[^]]*\]\(https?://[^)]*cdn' /path/to/article.md

# 统计未解析的 IMAGE 占位符（images stage 失败的残留）
grep -c '<!-- IMAGE:' /path/to/article.md

# 统计文章字数（不含 frontmatter）
wc -c /path/to/article.md
```

**Degradation detection (CRITICAL)**:
Before enforcing the minimum, check for **unresolved `<!-- IMAGE: -->` placeholders** in the article body. If any exist, this means the `images` stage **partially or fully failed** (graceful degradation path in orchestrator).

```
unresolved_placeholders = grep -c '<!-- IMAGE:' article.md

if unresolved_placeholders > 0:
    # Images stage degraded — DO NOT add more placeholders
    → Rule 7b result: WARNING (not FAIL)
    → Message: "images stage degraded — {N} unresolved placeholders.
                Re-run `/article-craft:images` to retry generation."
    → Skip any placeholder injection
```

**If below minimum AND no unresolved placeholders** (clean state):
- **DO NOT** add placeholders automatically — see Rule 11 orphan-image warning above. review runs **after** images stage; any new `<!-- IMAGE: -->` it inserts will never be generated.
- Instead: mark Rule 7b as **WARNING** with actionable message: "Article has {N} AI images but needs {M}. To add more: edit the article to insert `<!-- IMAGE: -->` + `<!-- PROMPT: -->` placeholders, then re-run `/article-craft:images`."
- If article is short by design (e.g., quick notes): note it in the review, no enforcement

#### Rule 8: External Links for WeChat

WeChat does not support clickable external links. Replace external URLs with search guidance: `搜索「关键词」` or `在 GitHub 搜索 项目名`. Internal inline links (`[Name](url)`) are fine -- the WeChat converter auto-extracts them as footnote references.

#### Rule 9: Mermaid Code Block Residue

Verify that **no Mermaid code blocks** (```` ```mermaid ... ``` ````) remain. All flowcharts/sequence diagrams/gantt charts must have been rendered to PNG and replaced with `![description](CDN_URL)`.

#### Rule 10: References Inline (No Separate Section)

All reference links must be **inlined** at first mention using `[Name](url)` format. Do NOT create a standalone "参考资料" or "参考链接" section at the end. The WeChat converter auto-generates footnotes from inline links; a manual section causes duplication.

#### Rule 11: ASCII Diagram Check ⭐ CRITICAL (detect-only)

**Scan all code blocks for ASCII diagrams** — these must be converted to `<!-- IMAGE -->` placeholders **before reaching review**.

Run this detection command:
```bash
grep -nE '│|├|└|┌|┐|─|▼|▶|←|→|↑|↓' /path/to/article.md
```

For each match found:
1. Check if it's inside a code block (between ` ``` `)
2. If yes, verify it's **executable code** (bash/python/json/etc.)
3. If NOT executable code (e.g., ASCII flowchart, state machine, architecture diagram) → **FAIL**

> **Why review does NOT auto-convert**: By the time review runs, the `images` stage has already generated and uploaded all `<!-- IMAGE: -->` placeholders. Any new placeholder review inserts here would be **orphaned** (never generated, article ships broken). ASCII-to-IMAGE conversion is the responsibility of `write` Step 6 (pre-save GATE check) — if a diagram survives into review, write's GATE failed and the problem is structural, not cosmetic.

**Action when violations found**:
- Do **NOT** auto-convert to placeholders (that would create orphans)
- Mark Rule 11 as **FAIL — escalate**
- Report: "ASCII diagram survived write's pre-save GATE. Manual fix required: convert to `<!-- IMAGE: -->` placeholder and re-run `/article-craft:images`, or replace with inline description"
- **BLOCK the article from proceeding to Phase 2 scoring**
- Use AskUserQuestion to offer: (a) open the article for manual fix, (b) re-run write stage, (c) abort

**Why critical**: ASCII diagrams render poorly on mobile and break visual consistency — but more importantly, any fix attempted by review at this point will create orphan placeholders because images stage is upstream.

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
