# Self-Check Rules

> Adapted from article-generator v3.3 for article-craft plugin
> Consolidated from SKILL.md (Phase C self-check) and writing-styles.md.

Run these checks after writing and before sending to the reviewer. Fix violations inline; do not leave them for the reviewer to catch.

---

## 1. Red-Flag Words (红旗词)

Search the article with Grep for any of these words. Every match must be rewritten:

```
无缝|赋能|一站式|综上所述|总而言之|值得注意的是|不难发现|深度解析|全面梳理|链路|闭环|抓手|底层逻辑|方法论|降本增效|实际上|事实上|显然|众所周知|不难看出
```

Also flag:
- "颠覆" / "极致" / "完美解决"
- "在当今快速发展的..." / "随着...的不断发展..."
- "让我们一起探索..."
- "效率提升 300%" or similar unverified quantitative claims

**Why**: These words trigger content-reviewer deductions in the "AI 痕迹" dimension and signal marketing fluff or AI-generated boilerplate.

> [!warning] `链路` 技术上下文不例外
> `链路` 即使在技术语境（"请求链路"、"调用链路"）中也禁止使用。
> 替换词：`请求处理流程` / `调用路径` / `处理通道` / `调用时序`。
> 此规则适用于**文章所有文本**，包括 Callout（`> [!tip]`、`> [!info]` 等）和系列预告区块。
> 同理，`极致`、`颠覆` 等词在 Callout 和下一篇预告中同样禁止。

---

## 2. Hook Length (opening paragraph)

The first paragraph (Hook) must be **100 characters or fewer** (Chinese characters, excluding code blocks).

It must contain three elements:
1. Pain point or scenario
2. Solution / tool name
3. Reading value

**Forbidden openers**:
- "在当今...的时代"
- "随着...的发展"
- "你是否也有这样的困扰？"
- Starting with a definition: "XXX 是一个..."

---

## 3. Closing Paragraph

The article must end with a concrete next-step action or a brief technical outlook (max 2 sentences).

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

## 4. Description Field

The YAML frontmatter must include a `description` field:
- **Max 120 characters** (Chinese)
- Used as the WeChat article summary
- Must be a meaningful abstract, not a copy of the title

---

## 5. Anti-AI Structure Rules

### Vary paragraph length
- Consecutive paragraphs must NOT use the same structure (e.g., "concept -> explain -> code" twice in a row).
- Mix structures: code-first with reverse explanation, Q&A style, experience-then-principle, comparison table then conclusion.

### Personal perspective (at least 2 per article)
Insert first-person observations at natural points:
- Bug/pitfall experience: "我在迁移旧项目时发现——"
- Choice rationale: "选 uv 而不是 poetry 的原因很简单——"
- Judgement: "这个功能设计得很克制，只做了该做的事"
- Real benchmarks: "本机实测，冷启动 2.1 秒"

### Diverse paragraph openings
- Never start 2 consecutive paragraphs with "此外" / "另外" / "同时" / "值得注意的是".
- Replace transition words with direct content: jump straight to the next point instead of "另外，还有一个功能...".

---

## 6. Chapter Depth

Every technical section must contain **at least 2 commands/code snippets plus explanatory text**.

A section with only 1 command and 1 sentence of explanation is too shallow and will be penalized by the reviewer.

---

## 7. Duplicate Image Check

Within the same section (same `##` heading), do not include two images that serve the same purpose (e.g., two versions of the same flow diagram, or two nearly identical screenshots).

---

## 8. External Links for WeChat

WeChat Official Accounts do not support clickable external links.

- Replace external URLs with search guidance: `搜索「关键词」` or `在 GitHub 搜索 项目名`.
- Internal inline links (`[Name](url)`) are fine -- the WeChat converter auto-extracts them as footnote references.

---

## 9. Mermaid Code Block Residue

After image processing, verify that **no Mermaid code blocks** remain in the article (```mermaid ... ```).

All flowcharts, sequence diagrams, gantt charts, etc. must have been rendered to PNG images and replaced with `![description](CDN_URL)`.

Render command reference: `npx mmdc -i file.mmd -o file.png -b transparent`

---

## 10. References Inline (No Separate Section)

All reference links must be **inlined** at the point of first mention using `[Name](url)` format.

**Do NOT** create a standalone "参考资料" or "参考链接" section at the end of the article. The WeChat converter auto-generates a footnote reference section from inline links; a manual section would cause duplication.

---

## 11. ASCII Diagram Residue (ASCII 流程图残留) — CRITICAL CHECK

Scan all code blocks (` ``` `) for box-drawing / arrow characters that indicate an ASCII diagram rather than executable code:

```bash
grep -nE '│|├|└|┌|┐|─|▼|▶|←|→|↑|↓' article.md
```

**If a code block contains these characters AND is not executable code (bash/python/json)**, it is an ASCII diagram that must be replaced with an `<!-- IMAGE -->` placeholder.

> [!note] 项目目录树也受此规则约束
> 用 `├──`、`└──` 等字符在代码块里展示项目结构，同样会触发此规则。
> **正确做法**：用 Markdown 列表替代：
> ```
> - `main.go` — HTTP server 入口
> - `mutate.go` — Mutating Webhook 处理逻辑
> - `deploy/` — K8s 部署清单
>   - `certificate.yaml`
> ```
> 不要把目录树放在任何代码块里，即使是 `text` 语言标识也不建议（`├` 字符会被 Rule 14 检测器标记）。

**Why**: ASCII diagrams render poorly on mobile, cannot be styled consistently, and miss the opportunity to use the article's shared visual style. All flowcharts, architecture diagrams, sequence diagrams, and state machines should be AI-generated images.

**Common ASCII characters to detect**:
- Box drawing: `│ ├ └ ┌ ┐ ─ ┬ ┴ ┼`
- Arrows: `→ ← ↑ ↓ ↔ ↕ ⇒ ⇐ ⇑ ⇓`
- Special: `▼ ▶ ◀ ▲ ◆ ◇ ■ □`

**Auto-fix process**:

1. Identify the ASCII diagram block
2. Extract the content and description
3. Replace with IMAGE placeholder:
   ```markdown
   <!-- IMAGE: name - description (ratio) -->
   <!-- PROMPT: [shared visual prefix], [describe the diagram content] -->
   ```

**Example**:
```
被检测的 ASCII 图：
┌─────────┐
│  State1 │ → State2 → State3
└─────────┘

替换为：
<!-- IMAGE: state-machine - 状态转移图 (16:9) -->
<!-- PROMPT: Code snippet style, architecture diagram, show State1 with arrow to State2 with arrow to State3 -->
```

**DO NOT** save the article if ASCII diagrams remain in non-executable code blocks.

---

## Quick Self-Check Grep Command

Run this in one shot to surface most violations:

```bash
grep -nE '无缝|赋能|一站式|综上所述|总而言之|值得注意的是|不难发现|深度解析|全面梳理|链路|闭环|抓手|底层逻辑|方法论|降本增效|实际上|事实上|显然|众所周知|不难看出|希望本文|希望对你|欢迎留言|点个在看|转发给朋友|在当今|随着.*发展|让我们一起' article.md
```

No output = all clear.
