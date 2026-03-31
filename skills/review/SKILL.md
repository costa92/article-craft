---
name: article-craft:review
version: 1.2.0
description: "Quality gate for articles -- self-check rules plus content-reviewer scoring. Use after writing to ensure article meets quality standards."
---

# Article Review (Quality Gate)

Run self-check rules against the article, then optionally invoke the content-reviewer for scoring. This skill is the quality gate between writing and publishing.

**Invoke**: `/article-craft:review`

**Dependency**: requires the `/content-reviewer` skill for publish-mode scoring. If `/content-reviewer` is not available, the skill falls back to self-check only and warns the user.

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
# 统计 IMAGE 占位符数量（不含已替换的 CDN 图片）
grep -c '<!-- IMAGE:' /path/to/article.md

# 统计文章字数（不含 frontmatter）
wc -c /path/to/article.md  # 或目测章节长度
```

**If below minimum**:
- If < minimum: warn user, add `<!-- IMAGE: name - description (3:2) -->` + `<!-- PROMPT: ... -->` placeholders for missing images
- If article is short by design (e.g., quick notes): note it in the review, no enforcement

#### Rule 8: External Links for WeChat

WeChat does not support clickable external links. Replace external URLs with search guidance: `搜索「关键词」` or `在 GitHub 搜索 项目名`. Internal inline links (`[Name](url)`) are fine -- the WeChat converter auto-extracts them as footnote references.

#### Rule 9: Mermaid Code Block Residue

Verify that **no Mermaid code blocks** (```` ```mermaid ... ``` ````) remain. All flowcharts/sequence diagrams/gantt charts must have been rendered to PNG and replaced with `![description](CDN_URL)`.

#### Rule 10: References Inline (No Separate Section)

All reference links must be **inlined** at first mention using `[Name](url)` format. Do NOT create a standalone "参考资料" or "参考链接" section at the end. The WeChat converter auto-generates footnotes from inline links; a manual section causes duplication.

#### Rule 11: ASCII Diagram Check ⭐ CRITICAL

**Scan all code blocks for ASCII diagrams** — these must be converted to `<!-- IMAGE -->` placeholders.

Run this detection command:
```bash
Use Python regular expressions to scan for ASCII diagrams
```

For each match found:
1. Check if it's inside a code block (between ` ``` `)
2. If yes, verify it's **executable code** (bash/python/json/etc.)
3. If NOT executable code (e.g., ASCII flowchart, state machine, architecture diagram):
   - This is a **violation** — must convert to IMAGE placeholder
   - Extract the diagram description and content
   - Replace with: `<!-- IMAGE: name - description (16:9) -->` + `<!-- PROMPT: ... -->`

**Why critical**: ASCII diagrams render poorly on mobile, break visual consistency, and are unprofessional. All diagrams must be AI-generated images.

**Action**: If violations found, convert all ASCII diagrams to image placeholders before proceeding to content-reviewer.

**If after conversion attempt, ASCII diagrams still remain**:
- This is a **CRITICAL FAILURE**
- Report: "ASCII diagram conversion failed"
- **BLOCK the article from proceeding to content-reviewer**
- Require manual fixing or explicit user override

---

### Phase 2: Content-Reviewer Scoring (publish mode only)

**If mode is `draft`**: skip this phase. Report self-check results only.

**If mode is `publish`**:

1. Invoke `/content-reviewer` on the article file.
2. Check the score against the **55/70 threshold**.
3. **If score >= 55/70**: pass. Proceed to output.
4. **If score < 55/70**: auto-modify the article, then re-run `/content-reviewer`. Repeat for up to **3 rounds**.

   **Auto-modify strategy** (applied in order):
   1. **Rule-based fixes** — Apply self-check rules: grep for red-flag words and rewrite them; fix hook length if over 100 chars; fix forbidden closings
   2. **Dimension-targeted rewrites** — Read the reviewer's per-dimension scores. For any dimension scoring below 7/10, use the Edit tool to rewrite the weakest sections:
      - "AI 痕迹" low → diversify paragraph structure, add personal perspective, vary openings
      - "标题与 Hook" low → rewrite title per style-guide formula, shorten hook
      - "内容深度" low → add code examples, expand thin sections
      - "结构可读" low → split long paragraphs, add callouts, improve transitions
      - "代码质量" low → add error handling, comments, type hints to code blocks
      - "结尾行动力" low → replace generic closing with concrete next-step command
   3. **Never regenerate the entire article** — only edit specific sections identified by the reviewer
5. **After 3 failed rounds**: ask the user:
   ```
   Question: "The article scored [X]/70 after 3 revision rounds (threshold: 55/70). How to proceed?"
   Options:
     - Continue revising -- attempt another round of fixes
     - Publish anyway -- accept the current score and proceed
     - Abort -- stop the pipeline, return to manual editing
   ```

---

## Output: Score + Feedback Report

```markdown
## Review Results

### Self-Check
- Rule 1 (Red-Flag Words): PASS / FIXED (N violations rewritten)
- Rule 2 (Hook Length): PASS / FIXED
- Rule 3 (Closing): PASS / FIXED
- Rule 4 (Description): PASS / FIXED
- Rule 5 (Anti-AI Structure): PASS / FIXED
- Rule 6 (Chapter Depth): PASS / WARNING (section X is thin)
- Rule 7 (Duplicate Images): PASS
- Rule 8 (WeChat Links): PASS / FIXED
- Rule 9 (Mermaid Residue): PASS
- Rule 10 (References Inline): PASS / FIXED
- Rule 11 (ASCII Diagram Check): PASS / FIXED (N diagrams converted)

### Content-Reviewer Score (publish mode)
- Score: [X]/70
- Status: PASS (>= 55) / FAIL (< 55, round N/3)
- Key feedback: [reviewer's main points]
```

---

## Standalone Mode

When invoked directly (not as part of the orchestrator pipeline):

1. AskQuestion for the article file path if not provided.
2. AskQuestion for the mode:
   ```
   Question: "Review mode?"
   Options:
     - Publish -- full review with content-reviewer scoring (>= 55/70 required)
     - Draft -- self-check only, skip content-reviewer
   ```
3. Execute the review steps above.
4. Output the report.
