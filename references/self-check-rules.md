# Self-Check Rules (canonical source)

> Single source for the rule definitions. The `write`, `lint`, and `review`
> skills reference rules by number from this file. SKILL.md files do NOT
> re-state rule bodies or re-type grep patterns — they read this file and
> run the patterns from it.
>
> **Active rule count: 23.** `scripts/review_selfcheck.py` implements
> `check_rule_1` through `check_rule_24` (highest ID is 24), but Rule 21 is a
> reserved slot, so 23 rules are active. See the dispatcher list at the bottom
> of that file. Reference entries below cover all 23 plus the `7b`
> degradation-aware variant of Rule 7. (URL fact-check, formerly Rule 21, is
> now handled by `verify_claims.py`.)
>
> Rules 18-22 added in v1.7+ based on first-round official-source research:
> GB 45438-2025 强制国标 + 网信办《标识办法》(cac.gov.cn) + microweixin.qq.com
> 公开课 + developers.weixin.qq.com 官方运营专员答复.
> Rule 23 added in v1.7.1+ based on `developers.weixin.qq.com`
> 《微信公众号推荐运营规范》(A 级，2024-05-10) + 微信珊瑚安全 2025-08-31
> 《关于进一步规范人工智能生成合成内容标识的公告》(B 级官方间接).
> Rule 24 added in v1.7.2+ — fills the blind spot exposed during dogfooding
> the LAT.md article: LLM-authored text confidently invents specific numbers
> that no other rule was catching. Warning-level by design — flags for
> author review, doesn't block publish.

## Who enforces what

| Rule | write (pre-save GATE) | lint (auto-fix) | review (Phase 1 block) |
|------|:---:|:---:|:---:|
| 1 Red-flag words        | ✓ | ✓ | ✓ |
| 2 Hook length           | ✓ | ✓ | ✓ |
| 3 Closing paragraph (CTA required) |   | ✓ | ✓ |
| 4 Description field + ≥3 zh tags   |   | ✓ | ✓ |
| 5 Anti-AI structure     |   | ✓ | ✓ |
| 6 Chapter depth         | ✓ |   | ✓ |
| 7 Duplicate images      |   |   | ✓ |
| 7b Min AI image count   |   |   | ✓ (degradation-aware) |
| 8 WeChat external links |   |   | ✓ |
| 9 Mermaid residue       |   | report | ✓ |
| 10 References inline    |   | ✓ | ✓ |
| 11 Placeholder residue  |   |   | ✓ GATE (detect-only, post-images) |
| 12 Template summaries   |   |   | ✓ |
| 13 Code block lang tag  | ✓ | ✓ default `text` | ✓ |
| 14 ASCII in code blocks | ✓ GATE (auto-convert) | report | ✓ detect-only |
| 15 Orphan PROMPT lines  |   | ✓ | ✓ |
| 16 PROMPT CJK render    | ✓ |   | ✓ |
| 17 Register naturalness |   |   | ✓ (tone-aware) |
| **18 AIGC label**       |   | ✓ (auto-append footer) | ✓ |
| **19 Title hook**       |   |   | ✓ |
| **20 Paragraph dedup**  |   |   | ✓ |
| **21** *(reserved for future use — formerly URL fact-check, now handled by `verify_claims.py`)* |   |   |   |
| **22 Personal voice density** |   |   | ✓ (soft warning) |
| **23 Anti-recommendation blacklist** |   |   | ✓ (error: AIGC reverse decl; warning: marketing headline) |
| **24 Fabricated-number detection** |   |   | ✓ (warning: unverified 数字 + 单位 claims) |

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

### Template-cadence detection

These patterns do not always fail an article alone, but repeated use strongly
correlates with AI-written rhythm and should be flagged by review:

- Roadmap filler: `本文将...` / `接下来我们将...` / `下面分别...`
- Empty judgement wrappers: `可以看到...` / `本质上...` / `从这个角度看...` / `某种意义上...`
- Mechanical sequencing: `首先...` / `其次...` / `最后...` when not describing an actual 3-step procedure

**Review heuristic**:

- Flag if any of the above appears 2+ times in body text
- Flag if adjacent paragraphs share the same starter class (e.g. transition-heavy or sequence-heavy)
- Flag if the article has fewer than 2 concrete anchors: numbers, version strings,
  command snippets, file paths, benchmark output, or exact error text
- Flag if any consecutive 3 body paragraphs contain 0 concrete anchors
- Flag if a section contains 2 consecutive summary-tone paragraphs with 0 concrete anchors

Concrete anchors are not a style flourish; they are evidence that the article is
grounded in something other than generic summary prose.

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

## Rule 11: Placeholder Residue (CRITICAL GATE — review stage)

**Severity**: FAIL (`is_gate=True`)
**Auto-fix**: no — the missing asset must be generated, not papered over
**Enforcer**: **review Phase 1 only** (post-images). NOT a write-stage gate.

### Why review-only

At **write** time the article is *supposed* to carry `<!-- IMAGE: -->` and
`<!-- SCREENSHOT: -->` placeholders — they are the handoff contract that the
screenshot/images stages consume. Gating on them at write would block every
legitimate draft. By the time **review** runs, those stages have already run,
so any *remaining* placeholder means an asset silently failed to generate and
the article would ship broken. That is what this rule catches.

### What `check_rule_11` flags

1. `<!-- IMAGE: ... -->` still present → run `/article-craft:images`.
2. `<!-- SCREENSHOT: ... -->` still present → run `/article-craft:screenshot`.
3. `IMAGE_PLACEHOLDER` (agent-generated non-standard format) → convert to the
   standard `<!-- IMAGE: name - desc (ratio) -->` or a CDN URL.
4. Broken local image refs `![...](images/…)` / `![...](placeholder-…)` whose
   file does not exist and is not a `cdn.`/`http` URL.

### Review behavior

On any match → FAIL, **block Phase 2**, surface via `AskUserQuestion`
(open article for manual fix / re-run the missing stage / abort). **Never**
insert new placeholders at review time — the images stage has already run, so a
fresh placeholder would be orphaned. (ASCII-diagram conversion is a *pre-images*
concern handled by Rule 14, not here.)

---

## Rule 12: Template Summary Detection

**Severity**: FAIL
**Auto-fix**: no — needs human rewrite (formulaic "本文将…" prose can only be replaced by actual reporting / opinion)
**Escalation**: review Phase 1 flags; user decides revision

### Why

LLM-generated articles default to a small set of summary openers: "本文从X
出发拆解Y", "下面章节将逐一介绍", "本文系统讲解从A到B". They feel safe
because they describe what the article does instead of doing it — and they're
exactly the cadence readers learn to skim past as "AI boilerplate".

### Canonical patterns

```
本文从.*出发.*拆解
本文将.*详细.*介绍
接下来.*我们将.*逐一
下面.*章节.*将.*逐一
本文.*完整.*梳理.*通过.*最后
本文.*系统.*讲解.*从.*到
```

(Source: `TEMPLATE_SUMMARY_PATTERNS` in `scripts/review_selfcheck.py`. Patterns
are regex `re.search` against each article line — matching is line-bounded.)

### Detection

Per line, scan against each pattern; first match per line is enough. Code
blocks are stripped before the check so legitimate code comments / docstrings
don't false-positive.

### Bad / Good

```
Bad : 本文从 Kubernetes 调度器的核心机制出发，详细拆解 ...
Good: 我们 etcd 翻车那次，最后定位到 scheduler 的一个 lease 续约 bug。下面
      这一段是当时的复盘记录。
```

Replacement strategy: lead with a concrete problem, an experience, or an
opinion — anything that proves the next 800 words won't be a Wikipedia
paraphrase.

---

## Rule 13: Code Block Language Identifier

**Severity**: FAIL
**Auto-fix**: context-dependent — `lint` can append a sensible default (`text`)
but the writer should provide the right tag (`bash`/`go`/`yaml`/etc.) for
syntax highlighting.
**Escalation**: write GATE flags missing tags at save; lint reports / auto-defaults;
review Phase 1 blocks if any remain.

### Why

Opening ` ``` ` without a language identifier ships an unhighlighted block.
Most renderers (公众号 / Obsidian / GitHub) require the tag to apply syntax
colors. Untagged blocks read as "raw text in a box" — visually identical to
ASCII art, which Rule 14 then incorrectly tries to filter as a diagram.

### Detection procedure

State-machine scan over `lines`:

1. Track in/out of code block via ` ``` ` fences.
2. Opening fence — capture text after the three backticks.
3. If empty after strip → violation on that line.
4. Closing fence has no language tag (it's bare ` ``` `) — skip.

### Auto-fix

When `lint` chooses to fill the gap, default to `text` (universally safe). The
writer should override with the real language when re-running the article.

### Bad / Good

```
Bad : ```
      $ kubectl get pods
      ```

Good: ```bash
      $ kubectl get pods
      ```
```

Common tags: `bash` `shell` `python` `go` `yaml` `json` `sql` `js` `ts`
`hcl` `dockerfile` `diff` `nginx` `text`.

---

## Rule 14: ASCII Diagram in Non-Executable Code Blocks

**Severity**: FAIL
**Auto-fix**: write auto-converts to `<!-- IMAGE: -->` placeholders; lint and
review detect-only.
**Enforcer**: **write Step 6 pre-save GATE** (auto-convert before the images
stage) + lint (report) + review Phase 1 (detect-only). This is the rule the
write gate uses to force ASCII diagrams into IMAGE placeholders *before* images
runs — converting at review time would orphan the placeholder.

### Why

Even with a language tag, putting an ASCII flowchart inside a code block
(commonly `text` / `markdown` / no language) bypasses the renderer's image
treatment — the reader sees a wall of box-drawing characters that won't
zoom, won't theme, and look broken on mobile. Always convert to a real
generated image.

### Detection procedure

For each closed code block:

1. Count box-drawing characters `│├└┌┐─┬┴┤┼╔╗╚╝║═╭╮╯╰` (`_BOX_CHARS`).
2. Count arrow characters `▼▶◄◀←→↑↓►` (`_ARROW_CHARS`).
3. Flag if **(box ≥ 5)** OR **(box ≥ 2 AND arrow ≥ 2)**.
4. If the block's language is in `_EXECUTABLE_LANGS` (`bash` `python` `go` `yaml`
   `json` `sql` `dockerfile` and 30+ others) → **skip** the flag (those chars
   are likely string-literal content, not a diagram).

### Auto-convert template (write GATE)

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

> **Note**: this rule scans **code blocks only** and skips `_EXECUTABLE_LANGS`,
> so a real `bash`/`python` snippet with `│`/`→` in a string literal does not
> false-positive. It is the single ASCII check in the system — there is no
> separate "body-wide ASCII" rule.

---

## Rule 15: Orphan PROMPT Comments

**Severity**: FAIL
**Auto-fix**: yes — delete the orphan line
**Escalation**: review Phase 1 deletes via `Edit`; lint reports.

### Why

`<!-- PROMPT: ... -->` is the second half of a two-line image directive —
`<!-- IMAGE: slug - desc (ratio) -->` directly above it. After the `images`
stage runs, the `IMAGE:` line is replaced with the rendered URL, and any
**stray `PROMPT:` line that wasn't paired with an `IMAGE:`** becomes a
visible HTML comment in the published article. Style: looks broken.

Common causes:

- Hand-edited the `IMAGE:` line away but forgot to delete the `PROMPT:` below
- Generated image was rejected and the `IMAGE:` placeholder was removed but
  the prompt kept "for next time" — never cleaned up before publish

### Detection procedure

For each `<!-- PROMPT:` line:

1. Look backward up to 2 non-empty lines.
2. If the most recent non-empty line is `<!-- IMAGE:` → paired (no violation).
3. Otherwise → orphan, flag for deletion.

### Auto-fix

Delete the orphan line. Safe because the orphan provides no rendered output
anyway — it's dead text the renderer will print verbatim.

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

## Rule 17: Register Naturalness (tone-aware)

**Goal:** match author voice to declared tone tier. Detect AI-typical
register problems (uniform formality, low first-person density, no strong
opinion, mechanical sentence cadence) at thresholds calibrated per tier.

**Tone tiers** (set via frontmatter `tone:` or `--tone` CLI flag, default
from writing style):

- `neutral` — standard technical blog (default for Style A/C/E)
- `casual` — mainstream Chinese tech blog (default for Style B/D/F)
- `opinionated` — strong personal-color (default for Style G/H)

**Sub-checks:**

| # | Metric | neutral | casual | opinionated | Severity |
|---|--------|---------|--------|-------------|----------|
| A | First-person markers per 800 chars (我用/踩坑/实测...) | ≥ 2 | ≥ 3 | ≥ 6 | warning |
| B | Strong-opinion sentences (我赌/真香/别学...) | (skipped) | (info) | ≥ 1 (error) | varies |
| C | Summary-phrase ceiling (在某种意义上/可以看到/...) | ≤ 3 | ≤ 2 | 0 | warning |
| D | Sentence-length coefficient of variation | (skipped) | ≥ 0.30 | ≥ 0.45 | warning |

> **v1.1 calibration (2026-05-08)**: tightened `neutral.max_summary_phrases`
> from 5 → 3 (caught a synthetic AI-flavor article that was passing v1) and
> `casual.first_person_per_800w` from 4 → 3 (real casual blogs hover at 2–3,
> not 4+). See `CHANGELOG.md` for the calibration data trail.

**Skipped if:** body has < 200 Chinese characters (sample too small).

**Skipped sub-check D if:** body has < 10 sentences after filtering
fragments and outliers.

**Pass criteria (Rule 17 in isolation):** no `error`-severity violation.
`warning`-severity violations don't block Rule 17 from returning `passed=True`.

**Why warnings don't block Rule 17 alone:**

Rule 17 is **detection-only with three signal levels** by design:

- `error` (only sub-check B at opinionated tone): the article violates a
  structural requirement of its declared tier. Rule 17 returns
  `passed=False` and review skill records it as a hard failure.
- `warning`: the article has a register issue worth flagging but not so
  severe it would justify rejection on its own. Rule 17 lets it through.
- `info`: advisory only, no blocking pressure.

The `review` skill aggregates Rule 17's warnings into the 7-dimension
AI-trace score (Phase 2). An article that ships 3 warnings from Rule 17
typically loses 4–6 points on the AI-trace dimension, pushing the
combined 7-dim score below the 55/70 threshold and triggering revision.

**Calibration note:** if you run lint/review on an article and Rule 17
reports `passed=True` with multiple warnings, that is **not a green
light to publish**. It means "Rule 17 alone wouldn't reject this, but
the warnings still feed the 7-dim score." Watch for the combined score.
A v2 calibration may upgrade severity for *severe* sub-check violations
(e.g., 2× ceiling overrun on summary phrases) to `error`; pending more
real-world data.

**Threshold source:** `scripts/config.py TONE_THRESHOLDS`. v1 starting
values calibrated against a 4-article pilot (2026-05-08). v2 target:
re-run on 20 published articles before further tuning.

**Auto-fix:** none — Rule 17 is detection only. The `lint` skill's
tone-aware rewrite map (`TONE_LEXICAL_REWRITES`) addresses register at
the lexical level, but the structural / opinion / cadence dimensions
require author judgement.

**Examples:** see `skills/write/style-guide.md` § Tone: <tier>.

---

## Rule 18: AIGC 显式标识（A 级合规，强制）

**Severity**: FAIL
**Auto-fix**: yes（自动追加文末小字脚注）
**Escalation**: lint 自动追加；review Phase 1 阻断；write 阶段不强制（允许 writer 先写正文，由 lint/review 兜底）。

### 法律依据（A 级官方一手）

- **GB 45438-2025** 网络安全技术 人工智能生成合成内容标识方法（强制性国标，2025-09-01 生效）
  - 官方原文：[openstd.samr.gov.cn](https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=F32EA2A561F1886CD8D606513512D547&refer=outter)
  - 要求**显式 + 隐式**双标识
- **网信办《人工智能生成合成内容标识办法》14 条**（2025-09-01 生效）
  - 官方原文：[cac.gov.cn](https://www.cac.gov.cn/2025-03/14/c_1743654684782215.htm)
  - 第十条禁止删除、篡改、伪造或隐匿标识

### 显式标识形式

article-craft 默认采用**A 方案**（文末小字脚注 + 公众号后台勾选）：

**文末必须含**（精确匹配以下任一变体）：

- `本文由 AI 辅助创作`  ← **推荐默认**（只声明 AI 参与，不替作者声称人工核对）
- `本文 AI 辅助创作`
- `本文由 AI 辅助生成`
- `本文使用 AI 工具辅助写作`
- `AI 辅助起稿`
- `本文 AI 辅助起稿 + 人工核实改写`  ← **仅当作者确实逐条核对过数据/事实时**才用

> **诚实标识原则**：默认标识不要写「人工核实改写」——那是在替作者声称一次不一定发生的
> 人工核对。源转述类文章（视频/论文/官方文档总结）更诚实的措辞：
> `本文由 AI 辅助归纳，数据与观点以原始来源为准，未逐条二次核实`。

**正则模式**：

```
本文.*?AI.*?(辅助|协助|帮助).*?(起稿|创作|生成|写作|改写)
|AI 辅助.*?(起稿|创作|改写)
```

格式建议（写在文末 `---` 分割线之下，作为脚注）：

```markdown
---

> 本文由 AI 辅助创作，关键数据与事实请以原始来源为准。
```

### 后台勾选（publish skill 提醒）

publish skill 在发布前必须打印提醒：

```
⚠ 发布前请在公众号后台勾选「创作来源 → 内容由 AI 生成」（4 选 1 单选，发布后不可改）。
  这是 GB 45438-2025 强制要求的隐式标识（功能名："创作来源"，B 级官方间接证据）。
```

### Auto-fix

lint 时如未检测到 AIGC 标识：自动在文末追加（在最后一行 `---` 之后或文档末尾）。
auto-fix **只追加诚实默认标识**，不替作者声称人工核对：

```markdown

---

> 本文由 AI 辅助创作，关键数据与事实请以原始来源为准。
```

### Why

GB 45438-2025 + 网信办标识办法是 A 级官方法规，2025-09-01 已生效。**违反即违法**，不是行业经验。article-craft 作为 AI 辅助创作工具，必须强制 AIGC 标识。

---

## Rule 19: 标题钩子规则 + 长度约束

**Severity**: FAIL
**Auto-fix**: no（标题改写需作者判断）
**Escalation**: review Phase 1 警告（不阻断 publish，但显著扣分）。

### Title 长度

- **硬上限**：64 字（微信公众平台技术上限，业界实测，B 级证据）
- **推荐 ≤ 28 字**：信息流卡片显示更完整（业界实测，无官方文档）

超 28 字 → warning；超 64 字 → FAIL。

### Title 钩子类型（必须命中至少 1）

公众号高 CTR 标题的三大类公式（业界实证，B 级）：

| 钩子类型 | 信号 | 示例 |
|---------|------|------|
| **数字钩子** | 数字 + 工具/动作 | `5 分钟用 Docker 部署 Web 应用` / `10 个 Cursor 隐藏快捷键` |
| **反差钩子** | 颠覆 / 反认知 / 反转 | `为什么我不再用 TypeScript` / `Rust 比 Go 慢？我跑了 100 万次` |
| **痛点钩子** | 痛点 + 后果 + 方案 | `用 ChatGPT 写代码的人注意！这 3 个陷阱让项目暴雷` |
| **故事钩子** | 场景 + 反常 + 悬念 | `被字节裁员后，我用一个开源项目月入 5 万` |
| **悬念钩子** | "为什么"、"怎么"、"竟然" | `为什么我们 etcd 翻车那次让 K8s 集群宕了 3 小时` |

**0 命中 → warning**（不 FAIL，因为某些题材确实没法挂钩子，但要求作者警觉）。

### 黑名单词（标题党降权风险）

```
震惊|重磅|解密|厉害了|XX死了|XX崩了|官方通知|紧急|必看|逆天|疯狂|爆炸
```

含黑名单词 → warning（不 FAIL，部分场景如"XX 崩了"是真实事故描述）。

### Detection

```bash
# 标题长度（取 frontmatter title 字段或 H1）
python3 -c "
import re, sys, yaml
content = open(sys.argv[1]).read()
fm_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
if fm_match:
    fm = yaml.safe_load(fm_match.group(1)) or {}
    title = fm.get('title', '')
else:
    h1 = re.search(r'^# (.+)$', content, re.MULTILINE)
    title = h1.group(1) if h1 else ''
print(f'len={len(title)} title={title}')
" article.md
```

### Why

- ≤28 字：来自调研报告 §1.4 业界实测（信息流卡片折叠保护）
- 钩子公式：来自调研报告 §4.1（高 CTR 标题三大模式，B 级业界经验）
- 黑名单词：来自调研报告 §1.6（微信 2024-05 公告"严查标题党"，A 级官方公告 + 业界经验补充）

---

## Rule 20: 段落相似度去重 + 模板雷同检测

**Severity**: FAIL
**Auto-fix**: no（重复段落删除需作者判断保留哪一份）
**Escalation**: review Phase 1 阻断。

### 触发场景

LLM 生成长文时偶尔会发生**上下文跳跃事故**：同一节内容（H2 标题相同或语义相近 + 首段类似 + 块内容高度相似）出现两次。实测 4000+ 字长文有概率触发同 H2 标题或同首句的重复段落。

### Detection

对文章里所有 `## ` 标题段执行两两相似度比对：

1. **H2 标题相似度**：用 `difflib.SequenceMatcher.ratio()`
2. **首段相似度**：H2 下第一段首句相似度
3. **块内容相似度**：H2 整段内容相似度

任一对 H2 段满足：
- 标题 ≥ 0.85 **OR** 首句 ≥ 0.85 **AND** 内容 ≥ 0.7 → 视为重复，FAIL

### Why

文章 3 事故是真实 LLM 生成 bug，非合规问题。这条 Rule 是工程质量改进，与 WeChat 算法无关，但能防止 article-craft 输出明显的 LLM 上下文事故。

---

## Rule 22: 个人化注入软检测（warning）

**Severity**: WARNING（不 FAIL，软警告）
**Auto-fix**: no
**Escalation**: review Phase 1 warning，不阻断 publish。

### 触发阈值

每篇文章应满足：

| 维度 | 阈值 | 检测 |
|------|------|------|
| 个人经历关键词 | ≥ 2 处 | grep "我"(含跟动词的复合) / "去年" / "上周" / "试过" / "踩过" / "踩坑" |
| 具体数字（非代码块） | ≥ 1 处 | 实测耗时、版本号、行数、报错码等 |
| 主观判断 | ≥ 1 处 | "我推荐" / "我不推荐" / "我觉得" / "我赌" / "我选" |

**注意**：调研报告中 ≥ 3 处分散是过度推论（仅 4 篇样本），改为 ≥ 2 处 + ≥ 1 处具体数字 + ≥ 1 处主观判断的组合，分布更现实。

### Why

调研 §7.4 把"主观判断密度"列为 AI 味识别核心特征——但调研没给具体阈值。4 篇实测显示个人经历密度大体足够（"我"出现 5-33 次/篇），但主观判断（"我推荐/不推荐"）4 篇中 3 篇为 0。这条 Rule 是触发作者对"我自己的判断"的觉察，不是硬约束。

---

## Rule 23: 反推荐特征词黑名单（v1.7.1+，A/B 级官方依据）

**Severity**: 分两级
- **ERROR**（阻断）：AIGC 反向声明
- **WARNING**（不阻断）：标题营销词头部

**Auto-fix**: no
**Escalation**: review Phase 1 ERROR 阻断 publish；WARNING 仅警告

### 检测项 ① AIGC 反向声明（ERROR）

文中出现以下表述触发 error：

| 表述 | 例子 |
|---|---|
| 直接否认 AI | "非 AI 生成"、"非 AI 创作"、"非机器生成" |
| 完全人工声明 | "完全人工撰写"、"纯手写"、"纯手工创作" |
| 强否定 | "本文完全由人工"、"100% 人工原创" |
| 弱化否认 | "没有借助 AI"、"未使用 AI 辅助"、"无 AI 参与" |

**为什么阻断**：违反微信珊瑚安全 2025-08-31 公告"不得删除、篡改、伪造或隐匿平台添加的 AI 标识"。article-craft 生成的内容客观上是 AI 辅助，反向声明 = 伪造非 AI 标识。

### 检测项 ② 标题营销词头部（WARNING）

标题（frontmatter `title` 或正文首个 `#`）匹配以下头部触发 warning：

`震惊` / `重磅` / `紧急` / `速看` / `必看` / `爆` / `独家解密` / `内部消息` / `不看后悔` / `错过.*?(后悔|遗憾)` / `(最|超|秒).*?震撼`

**为什么 warning 而非 error**：依据《微信公众号推荐运营规范》"通过捏造或扭曲事实的内容以吸引眼球博取流量"将不被推荐。匹配命中**可能**导致不被推荐，但并非确定（个例可能合理使用，如"重磅功能更新"的真实场景），所以软警告即可。

### 依据

- **微信珊瑚安全 2025-08-31**《关于进一步规范人工智能生成合成内容标识的公告》（B 级，多家媒体引用原文：财联社 cls.cn/detail/2131444、光明网 m.gmw.cn/2025-08/31/content_1304131434.htm、腾讯新闻 news.qq.com/rain/a/20250831A02WGT00）
- **《微信公众号推荐运营规范》** developers.weixin.qq.com/community/develop/doc/000cac23600b40d219814a85467809 （A 级官方一手，2024-05-10）
- **公众号文章推荐功能官方 Q&A** developers.weixin.qq.com/community/develop/doc/0000a4c99dccb8f21d816ffe661009 （A 级官方一手置顶帖）

### 触发后修复

**反向声明**：
1. 删除该句反向声明
2. 检查 Rule 18 是否已通过（应该已经有 AIGC 显式声明）
3. 若文章是非 AI 创作（手写历史文章），添加 frontmatter `ai_assisted: false` 跳过 Rule 18，并删除任何 article-craft 自动注入的痕迹

**营销标题**：
1. 改为知识传递钩子（如"我用半年踩出的 X：3 个反直觉决定"）
2. 改为经验分享钩子（如"3 个月跑通 X，这是我最后的方案"）
3. 改为个人观点钩子（如"为什么我不再用 X：3 个真实场景"）

参考 `skills/write/style-guide.md` 的 Title Hook Formulas 章节。

---

## Rule 24: 虚构数字检测（v1.7.2+，warning，不阻断）

**Severity**: WARNING（不阻断，仅警告）
**Auto-fix**: no（需作者人工核对来源）
**Escalation**: review Phase 1 warning，不阻断 publish。

### 检测项

扫描正文（非代码块、非 frontmatter）的"数字 + 单位"声明：

| 单位类别 | 例子 |
|---|---|
| 百分比 | `30%`、`80%` |
| 倍数 | `1.3 倍`、`10-20 倍` |
| 时间 | `20 分钟`、`6 周`、`200ms` |
| 金额 | `$15/M tokens`、`100 美元` |
| 数量 | `7 起`、`12 篇`、`500 文件` |
| 性能 | `50K tokens`、`200 tps` |

未命中下列豁免条件之一即标 warning。

### 6 种豁免机制

| 豁免 | 条件 | 例子 |
|---|---|---|
| 1. backtick 包围 | 数字被反引号包住 | `30%` |
| 2. markdown link | 同行含 `[..](http..)` | "按 [pricing](https://...) 是 $15/M" |
| 3. frontmatter 白名单 | `verified_numbers: ['22条', '14个']` | "有 22 条规则" |
| 4. 前置 hedge（句子内）| 约/大概/我估计/我赌/可能 等 + 数字（≤5 字间隔）| "我估计大概 30% 的项目" |
| 5. 后置 hedge | 数字+单位 后紧跟 左右/上下/前后 等 | "20 分钟左右" |
| 6. 年份 / 中文模糊量词 | `2026 年`、"几起"、"数个" | "2026 年发布" |

### Why warning 而非 error

虚构数字检测的天然 FP 率高——同样写"30%"，可能是 LLM 编的、也可能是作者自己测的。**Rule 24 不能机械阻断 publish**，只能提醒作者"这里有未标注的数字，请核对"。

### Why exists

第一轮微信调研推翻了 10 条 CSDN 循环引用的伪事实（`40/30/20/10` 权重、`30 天保护期`、`1.3 倍加成`、`0.89% 打开率` 等），但 v1.7.1 没有一条规则检测"AI 自己编的数字"——Rule 22 数主观判断密度，Rule 23 抓反向声明，都不验证数字真伪。

发现这个盲区是 dogfooding LAT.md 文章时——文章鼓吹"凭什么相信一个数据"，自己却塞了 15+ 个无出处数字。这是 LLM 写作的最大失败模式：**自信地编数字让文章看起来更可信**。Rule 24 是给作者的 sanity check，让 AI 写作流程能拦下"听起来合理的瞎编"。

### 修复 4 选 1

数字 X 被 Rule 24 命中后，作者可选：

| 选项 | 操作 |
|---|---|
| (a) 加 backtick | 把数字包进反引号：`X` |
| (b) 加 link | 同段落给出 `[来源](url)` |
| (c) 加 hedge | 改为"约 X" / "我估计 X" / "X 左右" |
| (d) 白名单 | frontmatter 加 `verified_numbers: ['X']` 显式标记已核实 |

---

## Appendix: Quick-scan grep

For a one-shot sweep of the most common violations before running individual rules:

```bash
grep -nE '无缝|赋能|一站式|综上所述|总而言之|值得注意的是|不难发现|深度解析|全面梳理|链路|闭环|抓手|底层逻辑|方法论|降本增效|实际上|事实上|显然|众所周知|不难看出|希望本文|希望对你|欢迎留言|点个在看|转发给朋友|在当今|随着.*发展|让我们一起' article.md
```

Supplemental anti-template sweep:

```bash
grep -nE '本文将|接下来我们将|下面分别|可以看到|本质上|从这个角度看|某种意义上|首先|其次|最后' article.md
```

No output = most common low-hanging violations are clear. This is a **convenience
scan**, not a replacement — run each rule's canonical grep for precise location
and fix mapping.
