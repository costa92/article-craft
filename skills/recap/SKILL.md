---
name: article-craft:recap
version: 1.10.1
description: "收获复盘 — 提炼读者收获清单并复查正文兑现度。诊断性，只写 sidecar，不改正文。"
allowed-tools:
  - Read
  - Write
  - Bash
  - AskUserQuestion
---

# Recap — Reader takeaways + delivery check

Run **after review, before publish** (standard mode). Answers: “what does the
reader get?” and “did the body actually deliver?”

**Invoke**: `/article-craft:recap [article-path] [--mode publish|draft]`

**Invariants**
- **Never Edit the article body.** No `Edit` tool on purpose.
- Never touch `<!-- IMAGE: -->` / `<!-- PROMPT: -->` / `<!-- SCREENSHOT: -->` /
  `<!-- HARVEST: -->` / CDN image URLs.
- Sidecar only: `_recap.md` + `_recap.json` next to the article.
- If frontmatter already has `takeaways:` (from review Phase 2.0), reuse them as
  the primary list; still re-check delivery against the body.
- draft mode (recap’s own flag): harvest list only, skip delivery scoring.
- Pipeline `--draft` / `--quick`: orchestrator **skips** this whole stage.

---

## Inputs

- **Article file path** (absolute)
- **Mode**: `publish` (default) or `draft` (list only)

Standalone without path → AskUserQuestion for the path.

---

## Phase 1 — Harvest list (always)

1. Read the article (final text, post-review).
2. Optional scaffold:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/review_selfcheck.py \
     /ABSOLUTE/PATH/article.md --extract-headings
   ```
3. If frontmatter has `takeaways:`, start from that list; otherwise extract
   3–5 **具体** reader gains (can do / now knows / changed judgment).  
   Ban empties: “了解了 X 的重要性”, “掌握了基本概念”.
4. Also list **关键信息/结论** (commands, numbers, hard claims) and **适合谁读**
   (one line).

---

## Phase 2 — Delivery check (`publish` mode only)

For each takeaway, grade against the body:

| Level | Meaning |
|-------|---------|
| `兑现` | Body has code/data/steps that fully support it |
| `部分兑现` | Mentioned but thin |
| `未兑现` | Title/hook/section promised it; body did not |

Also check title + opening hook consistency (Rule 19 / Rule 2 intent).

```
delivery_rate = (兑现×1.0 + 部分兑现×0.5) / N
```

**Verdict**
- `PASS`: rate ≥ **0.80** and **zero** `未兑现`
- `NEEDS_REVISION`: rate < 0.80 **or** any `未兑现`

On `NEEDS_REVISION`, AskUserQuestion:

```
收获兑现率 {rate}（阈值 0.80）。recap 是诊断性的 —— 如何继续？
- Publish anyway — 接受现状，继续 publish
- Re-run write with hints — 回跳 write，hints=未兑现/部分兑现清单
- Abort — 停止，文章留在当前路径
```

Do **not** auto-rewrite the body inside recap.

---

## Outputs

### Chat (always)

```markdown
## 收获复盘 (Recap)

### 本文你会获得
1. ... — 见「章节」
2. ...

### 关键信息/结论
- ...

### 适合谁读
...

### 兑现度 (publish 模式)
| # | 收获 | 级别 | 位置 | 说明 |
|---|------|------|------|------|
| 1 | ... | 兑现 | L.. | ... |

兑现率：X.XX（阈值 0.80）
Verdict：PASS / NEEDS_REVISION
```

### Sidecar (same directory as article.md)

Write with the **Write** tool only:

**`_recap.json`**
```json
{
  "article": "/abs/path/article.md",
  "generated_at": "ISO-8601",
  "takeaways": ["..."],
  "key_info": ["..."],
  "audience": "...",
  "delivery": [
    {"takeaway": "...", "level": "兑现", "where": "L120", "note": "..."}
  ],
  "delivery_rate": 0.83,
  "verdict": "PASS"
}
```

**`_recap.md`**: human copy of the chat block above.

Optional: if review did not write `takeaways:` and Phase 1 produced a solid
list, you **may** persist them with the deterministic helper (still no body edit):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/review_selfcheck.py \
  /ABSOLUTE/PATH/article.md \
  --write-takeaways '["...","..."]'
```

Prefer leaving frontmatter to review when both run in the standard pipeline.

---

## Return values (for orchestrator)

| Return | Meaning | Orchestrator |
|--------|---------|--------------|
| `PASS` | rate ok / or user chose Publish anyway | continue publish |
| `NEEDS_REVISION_RERUN_WRITE` | user chose re-write | jump to write with hints; cap 2 recap reruns |
| `ABORT` | user chose Abort | stop pipeline |

---

## Standalone

1. Resolve article path.
2. Resolve mode (default publish).
3. Run Phase 1 (+ Phase 2 if publish).
4. Write sidecars; print chat report.
