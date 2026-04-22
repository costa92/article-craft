# Self-Check Rules (canonical source)

> Single source for all 11 rules. The `write`, `lint`, and `review` skills
> reference rules by number from this file. SKILL.md files do NOT re-state
> rule bodies or re-type grep patterns — they read this file and run the
> patterns from it.

## Who enforces what

| Rule | write (pre-save GATE) | lint (auto-fix) | review (Phase 1 block) |
|------|:---:|:---:|:---:|
| 1 Red-flag words        | ✓ | ✓ | ✓ |
| 2 Hook length           | ✓ | ✓ | ✓ |
| 3 Closing paragraph     |   | ✓ | ✓ |
| 4 Description field     |   | ✓ | ✓ |
| 5 Anti-AI structure     |   | ✓ | ✓ |
| 6 Chapter depth         | ✓ |   | ✓ |
| 7 Duplicate images      |   |   | ✓ |
| 7b Min AI image count   |   |   | ✓ (degradation-aware) |
| 8 WeChat external links |   |   | ✓ |
| 9 Mermaid residue       |   | report | ✓ |
| 10 References inline    |   | ✓ | ✓ |
| 11 ASCII diagrams       | ✓ GATE (auto-fix) | report | detect-only, block |

## Rule schema

Every rule below has this structure:

- **Severity**: `FAIL` (blocks) / `WARNING` (reports only)
- **Auto-fix**: `yes` + mapping table / `no` / `context-dependent`
- **Escalation**: what each enforcer does on FAIL
- **Canonical grep**: the single regex — SKILL.md reads it from this file
- **Good / Bad examples**: where useful

---

## Rule 1: Red-Flag Words

**Severity**: FAIL
**Auto-fix**: yes (mapping below)
**Escalation**: write fixes inline before save; lint `--fix` applies the mapping;
review Phase 1 fixes via Edit and counts violations toward the "AI 痕迹" scoring dimension.

**Canonical grep**:

```
无缝|赋能|一站式|综上所述|总而言之|值得注意的是|不难发现|深度解析|全面梳理|链路|闭环|抓手|底层逻辑|方法论|降本增效|实际上|事实上|显然|众所周知|不难看出
```

**Contextual flags** (no regex — match by meaning):

- "颠覆" / "极致" / "完美解决"
- "在当今快速发展的..." / "随着...的不断发展..."
- "让我们一起探索..."
- Unverified quantitative claims like "效率提升 300%"

**Auto-fix mapping**:

| Match | Rewrite |
|-------|---------|
| 无缝 | rewrite sentence without the word (context-dependent) |
| 赋能 | 支持 / 帮助 / remove |
| 一站式 | 统一的 / 集成的 |
| 综上所述 / 总而言之 | delete transition, start next sentence directly |
| 值得注意的是 | delete, merge into next sentence |
| 实际上 / 事实上 | delete (usually filler) |
| 显然 / 众所周知 | delete (assertion without evidence) |
| 链路 | 请求处理流程 / 调用路径 / 处理通道 / 调用时序 |

> [!warning] `链路` 技术上下文不例外
> 即使在技术语境（"请求链路"、"调用链路"）中也禁止使用。此规则适用于**文章所有文本**，
> 包括 Callout（`> [!tip]`、`> [!info]` 等）和系列预告区块。
> 同理，`极致`、`颠覆` 等词在 Callout 和下一篇预告中同样禁止。

**Why**: These words trigger content-reviewer deductions in the "AI 痕迹" dimension
and signal marketing fluff or AI-generated boilerplate.

---

## Rule 2: Hook Length

**Severity**: FAIL
**Auto-fix**: yes (split into two paragraphs)
**Escalation**: write enforces before save; lint splits automatically; review reports.

The first paragraph (Hook, after YAML frontmatter) must be **100 Chinese characters
or fewer** (excluding code blocks).

It must contain three elements:

1. Pain point or scenario
2. Solution / tool name
3. Reading value

**Forbidden openers**:

- "在当今...的时代"
- "随着...的发展"
- "你是否也有这样的困扰？"
- Starting with a definition: "XXX 是一个..."

**Auto-fix strategy**: split the hook into two paragraphs — first paragraph ≤ 100
chars (pain + solution), second paragraph (value proposition).

---

## Rule 3: Closing Paragraph

**Severity**: FAIL
**Auto-fix**: yes (replace with a concrete next-step from article content)
**Escalation**: lint rewrites; review rewrites.

The article must end with a concrete next-step action or a brief technical outlook
(max 2 sentences).

**Forbidden closings**:

- "希望本文对你有帮助"
- "如果有问题欢迎留言"
- "欢迎在评论区分享"
- "点个在看" / "转发给朋友"
- "你的点赞是我最大的动力"
- "如果这篇文章对你有帮助"

**Good examples**:

- "装好 uv 后，在现有项目里跑一次 `uv pip install -r requirements.txt`，体感一下速度差异。"
- "uv 的 workspace 功能还在快速迭代，monorepo 支持值得关注。"

---

## Rule 4: Description Field

**Severity**: FAIL
**Auto-fix**: yes (generate from first section)
**Escalation**: lint generates; review generates.

The YAML frontmatter must include a `description` field:

- **Max 120 characters** (Chinese)
- Used as the WeChat article summary
- Must be a meaningful abstract, not a copy of the title

**Auto-fix strategy**: generate a 1–2 sentence summary from the article's first
section, keeping key nouns and removing marketing tone.

---

## Rule 5: Anti-AI Structure

**Severity**: WARNING (hard to fully auto-detect)
**Auto-fix**: partial (transition words yes; structure rotation no)
**Escalation**: lint deletes repeated transitions; review flags structural issues
in Phase 2 scoring.

### Vary paragraph length

Consecutive paragraphs must **not** use the same structure (e.g., "concept → explain →
code" twice in a row). Mix structures:

- Code-first with reverse explanation
- Q&A style
- Experience-then-principle
- Comparison table then conclusion

### Personal perspective (at least 2 per article)

Insert first-person observations at natural points:

- Bug/pitfall experience: "我在迁移旧项目时发现——"
- Choice rationale: "选 uv 而不是 poetry 的原因很简单——"
- Judgement: "这个功能设计得很克制，只做了该做的事"
- Real benchmarks: "本机实测，冷启动 2.1 秒"

### Diverse paragraph openings

Never start 2 consecutive paragraphs with the same transition word.

**Canonical list (5 words)**:

```
此外|另外|同时|值得注意的是|除此之外
```

**Auto-fix strategy (lint)**: delete the transition word from the second occurrence
and jump straight to the point.

---

## Rule 6: Chapter Depth

**Severity**: FAIL (pre-save GATE in write)
**Auto-fix**: no (needs content generation)
**Escalation**: write MUST pass this before save — each `##` technical section
must have at least 2 code blocks plus explanatory text. Review flags violations
but cannot fix them.

A section with only 1 command and 1 sentence of explanation is too shallow and
will be penalized by the reviewer.

**How to check**:

```bash
python3 -c "
import re, sys
body = open(sys.argv[1]).read()
sections = re.split(r'^## ', body, flags=re.M)
for s in sections[1:]:
    title = s.split('\n', 1)[0]
    n_code = len(re.findall(r'^```', s, flags=re.M)) // 2
    if n_code < 2:
        print(f'SHALLOW: {title} (code blocks: {n_code})')
" article.md
```

**Write's responsibility**: for pure-opinion/comparison sections where code doesn't
fit naturally (e.g. "为什么选 X 而不是 Y"), pad with a cost-comparison code block,
a CLI example, or a config fragment.

---

## Rule 7: Duplicate Image Check

**Severity**: WARNING
**Auto-fix**: no (needs human judgement)
**Escalation**: review flags.

Within the same section (same `##` heading), do not include two images that serve
the same purpose (e.g., two versions of the same flow diagram, or two nearly
identical screenshots).

---

## Rule 7b: Minimum AI Image Count (degradation-aware)

**Severity**: WARNING (never FAIL — injecting placeholders post-hoc would orphan them)
**Auto-fix**: no (any placeholder added here would never be generated)
**Escalation**: review reports count + actionable message; never inserts placeholders.

### Threshold table

| 文章字数 | 最少 AI 图片数（IMAGE 占位符） |
|---------|-------------------------------|
| ≤ 1500 字 | 1 张（封面） |
| 1500–3000 字 | 2 张（封面 + 1 节奏图） |
| > 3000 字 | 3 张（封面 + 2 节奏图） |

> `SCREENSHOT` 占位符 / HARVEST 远端图**不计入此数量**（都由 screenshot skill 处理）。

### How to check

```bash
# Count rendered AI images (CDN links)
grep -cE '!\[[^]]*\]\(https?://[^)]*cdn' article.md

# Count unresolved IMAGE placeholders (images-stage failures)
grep -c '<!-- IMAGE:' article.md

# Count article body length (excluding frontmatter)
wc -c article.md
```

### Degradation detection (CRITICAL — runs first)

Before enforcing the minimum, check for **unresolved `<!-- IMAGE: -->` placeholders**:

```
unresolved = grep -c '<!-- IMAGE:' article.md

if unresolved > 0:
    # images stage degraded — DO NOT add more placeholders
    result: WARNING (not FAIL)
    message: "images stage degraded — N unresolved placeholders.
              Re-run /article-craft:images to retry generation."
    skip placeholder injection
```

### Clean-state handling

If the article is below minimum **and** has no unresolved placeholders:

- **DO NOT** insert `<!-- IMAGE: -->` placeholders automatically — review runs
  **after** the images stage, so any new placeholder would be orphaned (never
  generated, ships broken).
- Mark as **WARNING** with actionable message: "Article has N AI images but
  needs M. To add more: edit the article to insert `<!-- IMAGE: -->` + `<!-- PROMPT: -->`
  placeholders, then re-run `/article-craft:images`."
- For articles short by design (quick notes, news briefs): note in review, no enforcement.

---

## Rule 8: External Links for WeChat

**Severity**: FAIL
**Auto-fix**: context-dependent (can't always guess the right search term)
**Escalation**: review rewrites where obvious; otherwise flags.

WeChat Official Accounts do not support clickable external links in body text.

- Replace external URLs with search guidance: `搜索「关键词」` or `在 GitHub 搜索 项目名`.
- Internal inline links (`[Name](url)`) are **fine** — the WeChat converter auto-extracts
  them as footnote references.

**Good example**:

- Bad: `详见官方文档 https://docs.example.com/getting-started`
- Good: `详见官方文档（搜索「Example getting started」）`
- Also good: `详见 [官方入门文档](https://docs.example.com/getting-started)` (inline link, converter handles it)

---

## Rule 9: Mermaid Code Block Residue

**Severity**: FAIL
**Auto-fix**: no (needs PNG rendering)
**Escalation**: lint reports; review blocks.

After image processing, verify that **no Mermaid code blocks** remain:

```bash
grep -n '```mermaid' article.md
```

All flowcharts, sequence diagrams, gantt charts, etc. must have been rendered to
PNG images and replaced with `![description](CDN_URL)`.

Render command reference:

```bash
npx mmdc -i file.mmd -o file.png -b transparent
```

---

## Rule 10: References Inline (No Separate Section)

**Severity**: FAIL
**Auto-fix**: yes (delete the standalone section)
**Escalation**: lint deletes; review deletes.

All reference links must be **inlined** at the point of first mention using
`[Name](url)` format.

**Do NOT** create a standalone "参考资料" or "参考链接" section at the end of
the article. The WeChat converter auto-generates a footnote reference section
from inline links; a manual section causes duplication.

---

## Rule 11: ASCII Diagram Check (three-role split)

**Severity**: FAIL
**Auto-fix**: depends on enforcer — see escalation below
**Escalation**: three roles, three behaviors.

### Why the split

By the time `review` runs, the `images` stage has already generated and uploaded
all `<!-- IMAGE: -->` placeholders. Any new placeholder inserted at review time
would be **orphaned** — never generated, article ships broken. ASCII-to-IMAGE
conversion is therefore a **pre-images** responsibility.

### Canonical grep

```
│|├|└|┌|┐|─|▼|▶|←|→|↑|↓
```

12 single characters. Do **not** use combined sequences like `──→` or `←──` — the
single-character grep already matches those.

### Enforcer responsibilities

| Enforcer | When | Action |
|----------|------|--------|
| **write Step 6 (pre-save GATE)** | before save, before images | **Auto-convert** ASCII diagrams to `<!-- IMAGE: -->` + `<!-- PROMPT: -->`. Re-grep; block save until clean. |
| **lint** | standalone, before images | **Report only**. Do not auto-fix (lint may run anywhere in the pipeline). User decides. |
| **review Phase 1** | after images | **Detect only**. On match → FAIL, block Phase 2, surface via AskUserQuestion (open article for manual fix / re-run write / abort). Never insert placeholders. |

### Detection procedure (same for all enforcers)

1. Run the canonical grep.
2. For each match: check if it's inside a code block (between ` ``` `).
3. If inside, verify the code block is **executable code** (bash/python/json/yaml/etc.).
4. If NOT executable code (ASCII flowchart, state machine, architecture diagram) → violation.

### Auto-convert template (write only)

```markdown
<!-- IMAGE: slug - description (ratio) -->
<!-- PROMPT: [shared visual prefix], [describe the diagram content in English] -->
```

Example:

```
Detected ASCII:
┌─────────┐
│  State1 │ → State2 → State3
└─────────┘

Converted to:
<!-- IMAGE: state-machine - 状态转移图 (16:9) -->
<!-- PROMPT: Code snippet style, architecture diagram, show State1 with arrow to State2 with arrow to State3 -->
```

### 项目目录树也受此规则约束

用 `├──`、`└──` 等字符在代码块里展示项目结构，同样会触发此规则。**正确做法**：用
Markdown 列表替代：

```
- `main.go` — HTTP server 入口
- `mutate.go` — Mutating Webhook 处理逻辑
- `deploy/` — K8s 部署清单
  - `certificate.yaml`
```

不要把目录树放在任何代码块里，即使 `text` 语言标识也不建议（`├` 字符会被规则检测器标记）。

---

## Rule 16: PROMPT Text-Rendering Risk (Gemini can't render Chinese)

**Severity**: FAIL
**Auto-fix**: enforced at write stage; review flags survivors
**Escalation**: write rewrites the prompt; review blocks if CJK remains.

### Why

Gemini's image models (including `gemini-3-pro-image-preview` and
`gemini-2.5-flash-image`) **cannot reliably render CJK characters**. Chinese
glyphs come out distorted, miss strokes, or are pure gibberish. English short
labels are also unreliable. Any `<!-- PROMPT: -->` that asks Gemini to render
specific readable text — especially Chinese — will produce an unusable image
that has to be regenerated.

The rule catches this **before** the image is generated, so you don't waste
an API call and end up with a broken article.

### Canonical detection

```bash
# CJK characters inside any <!-- PROMPT: --> line
grep -nE '<!-- PROMPT:.*[\x{4e00}-\x{9fff}]' article.md

# Common "render this exact text" instructions in English
grep -niE '<!-- PROMPT:.*\b(text|title|headline|caption|label|logo|slogan|copy|heading|sign|quote|saying)\s*[:=]?\s*["""]'  article.md
```

Whitelist: if the prompt explicitly contains
`No readable text anywhere` / `no letters` / `no labels`, the English
instruction form is considered defused.

### Fix — visual substitution

Instead of asking Gemini to render text, describe the visual shape of a text
artifact:

| Subject | ❌ Bad PROMPT | ✅ Good PROMPT |
|---------|--------------|---------------|
| Menu | `menu showing "招牌菜 ¥68"` | `silhouette of a folded menu with price-column layout lines and food-icon shapes` |
| Newspaper | `newspaper headline "XX 突破"` | `silhouette of a newspaper front page showing only masthead frame and column block patterns` |
| Poster | `poster titled "越界"` | `silhouette of a vehicle-launch poster with abstract light streaks and product-shape composition` |
| Calligraphy | `calligraphy saying "静"` | `calligraphy scroll with abstract brush-stroke marks, no characters` |
| Magazine | `magazine cover "慢生活 VOL.08"` | `silhouette of a magazine cover showing layout grid and cover-photo shape` |

And append this hard constraint at the end of every prompt where it fits:

```
No readable text anywhere, no letters, no numbers, no labels, no captions, no logos.
```

### The self-contradiction case

If the **article itself discusses text-rendering ability** (e.g. a GPT-Image-2
review, a nano-banana text-rendering test, an Imagen benchmark), never use a
`<!-- IMAGE: -->` + Gemini prompt to illustrate that ability. You are using a
model that cannot render text to "prove" another model can — the final image
will visually contradict the claim. Use one of these instead:

1. `<!-- SCREENSHOT: -->` of the target model's actual output page
2. Manually inserted real screenshot URLs (`![](https://…/real_output.png)`)
3. A Markdown table comparing before/after
4. A pure-abstract Gemini prompt (silhouettes, color blocks, icons, no chars)

---

## Appendix: Quick-scan grep

For a one-shot sweep of the most common violations before running individual rules:

```bash
grep -nE '无缝|赋能|一站式|综上所述|总而言之|值得注意的是|不难发现|深度解析|全面梳理|链路|闭环|抓手|底层逻辑|方法论|降本增效|实际上|事实上|显然|众所周知|不难看出|希望本文|希望对你|欢迎留言|点个在看|转发给朋友|在当今|随着.*发展|让我们一起' article.md
```

No output = most common low-hanging violations are clear. This is a **convenience
scan**, not a replacement — run each rule's canonical grep for precise location
and fix mapping.
