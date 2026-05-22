---
name: article-craft:publish
version: 1.7.4
description: "Place article in knowledge base and optimize for distribution. Use after review to save the article to its final location."
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - AskUserQuestion
---

# Publish

Place a reviewed article into the knowledge base at the correct category directory, and optionally optimize for WeChat distribution. This is the final step in the article-craft pipeline.

**Invoke**: `/article-craft:publish`

---

## Inputs

- **Article file path**: absolute path to the `.md` file to publish
- **Review score** (optional): passed from `article-craft:review` if run in pipeline
- **`--output DIR`** (optional): explicit output directory. If provided, **bypass KB auto-detection entirely** and save the article under `DIR`. Use this when:
  - You are inside an Obsidian KB but want a one-off scratch article saved elsewhere
  - You want to publish to a custom location that doesn't match the `02-技术/` convention
  - You are publishing programmatically and want deterministic output

If invoked standalone (file path not provided), use AskQuestion:
```
Question: "Which article file should I publish?"
(free-form input: provide the absolute path to the .md file)
```

---

## Execution Steps

### Step 0: Pre-publish placeholder gate (v1.4.20+)

Before any directory matching or file movement, refuse to publish if the
article still contains unresolved `<!-- IMAGE: -->`, `<!-- PROMPT: -->`,
`<!-- SCREENSHOT: -->`, or `<!-- HARVEST: -->` placeholders. This catches
the silent-failure case where image generation ran with `--no-upload` (or
upload itself failed), leaving an article that *looks* finished in stdout
but still has raw placeholders that downstream readers will see as broken
HTML comments.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/pipeline_state.py check-publish-ready \
    --article /ABSOLUTE/PATH/article.md
```

Exit codes:

| Code | Meaning | Action |
|------|---------|--------|
| 0 | Clean — all placeholders resolved | Continue to Step 1 |
| 1 | Unresolved placeholders detected | **BLOCK publish.** Print the structured report (placeholder counts per kind) to the user and exit. |
| 2 | Article path doesn't exist | Fail with a clear "file not found" error |

The script emits a JSON line on stdout (machine-readable) plus a
human-readable summary on stderr listing how many of each placeholder
kind remain. **Do not override this gate** — re-run image generation or
manually replace placeholders, then re-invoke publish.

### Step 1: Preview the Publish Move (`--dry-run`)

Directory matching, collision detection, and Style H sidecar collection are
all owned by `scripts/publish_plan.py`. It is a **single command**: run it
with `--dry-run` to preview the plan (no filesystem changes), review the
result, then run it again **with the same arguments minus `--dry-run`** to
execute. The KB top-level directory name is **not** hardcoded — the script
reads `config.kb_category_root()` (env.json `kb_category_root`, default
`02-技术`), so a fork with a differently-named KB works unchanged.

Two modes, selected by presence of `--output`:

**Mode A — Explicit output** (`--output DIR` passed):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/publish_plan.py --dry-run \
    --article /ABSOLUTE/PATH/article.md \
    --output-dir /ABSOLUTE/PATH/DIR
```

Skips KB detection and directory matching entirely. If `DIR` doesn't exist
the script exits 1 with `error_code: output_dir_not_found`.

**Mode B — Auto-detect KB** (no `--output`):

Check if the current working directory (or a known parent) is an Obsidian
knowledge base by looking for the category-root directory (default `02-技术/`,
or whatever `kb_category_root` is set to). Also check for `.obsidian/` or
sibling numbered directories (`01-工作/`, `03-创作/`).

- **KB detected** — pass its root so the script can match a subdirectory:
  ```bash
  python3 ${CLAUDE_PLUGIN_ROOT}/scripts/publish_plan.py --dry-run \
      --article /ABSOLUTE/PATH/article.md \
      --kb-root /ABSOLUTE/PATH/KB_ROOT
  ```
- **KB not detected** — omit `--kb-root`; the script falls back to the
  article's own directory as the auto target.

`--dry-run` prints a JSON plan payload on stdout and **creates nothing** on
disk:

| Field | Meaning |
|-------|---------|
| `target_dir` | Proposed destination directory |
| `target_file` | Proposed file path. For `collision.status: rename` this name carries a placeholder timestamp — the **exact** timestamp is finalized when the real run executes, so report it as "a timestamped name", not verbatim. |
| `collision.status` | `none` / `identical` (same content) / `rename` (differing content → timestamped) |
| `sidecars` | Style H sidecars (`_evidence.json`, `_harvest_menu.md`) found next to the article |
| `auto_meta.strategy` | How the directory was chosen — see Step 2 |

### Step 2: Review the Proposed Directory

In auto mode, inspect `auto_meta.strategy` from the plan:

- **`matcher`** — `SmartDirectoryMatcher` found a learned/keyword match. Trust it.
- **`directory_fallback`** — no match; the script picked the deepest existing
  subdirectory. Treat as a guess.
- **`fallback`** — nothing matched; the script will use
  `{kb_category_root}/{kb_uncategorized_dir}` (default `02-技术/未分类`).

For `directory_fallback` / `fallback`, do a semantic match yourself using the
table below, then use an explicit `--output-dir` in Step 3 so the article
lands in the right place (substitute your configured `kb_category_root` for
`02-技术`):

| Article Topic | Target Directory | Examples |
|---------------|-----------------|----------|
| AI tools/products | `02-技术/AI-生态/工具/` | Cursor, Windsurf review |
| AI model evaluation | `02-技术/AI-生态/模型评测/` | GPT-5, Claude 4 comparison |
| AI Agent | `02-技术/AI-生态/Agent/` | Agent architecture, MCP protocol |
| Claude Code | `02-技术/AI-生态/Claude-Code/` | Claude Code tips, skills, plugins |
| Ollama | `02-技术/AI-生态/Ollama/` | Local model deployment |
| RAG | `02-技术/AI-生态/RAG/` | Retrieval-augmented generation |
| Go language | `02-技术/基础设施/Go/` | Go tutorials, source analysis |
| Cloudflare | `02-技术/基础设施/Cloudflare/` | CDN, Workers, Pages |
| Docker/K8s etc. | `02-技术/基础设施/<tool>/` | Auto-create subdirectory |
| Obsidian | `02-技术/工作流/Obsidian/` | Obsidian plugins, workflows |
| n8n | `02-技术/工作流/n8n/` | Workflow automation |
| New topic | `02-技术/<new-dir>/` | Auto-create |

When the topic is genuinely ambiguous, ask the user before applying.

### Step 3: Execute the Publish Move

Once the target directory is confirmed, run the script **again without
`--dry-run`** — keep the explicit `--output-dir` you settled on (use it even
for an accepted auto match, so the executed run targets exactly the directory
you reviewed and does not re-resolve):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/publish_plan.py \
    --article /ABSOLUTE/PATH/article.md \
    --output-dir /ABSOLUTE/PATH/CONFIRMED_DIR
```

The executed run creates the directory (`mkdir -p` semantics), copies the
article to `target_file`, and copies any Style H sidecars. It returns the plan
plus a `copied_sidecars` list. Behaviour notes:

- **Collision** — when a differing file already exists, the script writes to a
  timestamped name (e.g. `article_20260322120000.md`); it never silently
  overwrites. When content is identical it re-copies in place (a harmless
  no-op). Surface `collision.status` to the user in the summary.
- **Style H sidecars** — `_evidence.json` / `_harvest_menu.md` next to the
  article are copied automatically so a future
  `/article-craft --upgrade` can resume HARVEST operations. Non-Style-H
  articles have no sidecars and this is a silent no-op.
- **Never copied**: `.article-craft-state.json` — that file is
  per-pipeline-run and the orchestrator deletes it on publish success (v1.4.2
  cleanup rule). The script's `SIDECAR_FILES` list deliberately excludes it.

### Step 3.5: 微信发布前合规 + 推荐池命中 checklist（v1.7.1+，A 级证据）

依据：
- **GB 45438-2025** 强制国标 + 网信办《标识办法》14 条（2025-09-01 已生效）
- **微信珊瑚安全 2025-08-31** 公告（B 级官方间接，多家媒体引用原文）
- **《微信公众号推荐运营规范》** developers.weixin.qq.com 官方知识库（A 级官方一手，2024-05-10）
- **公众号文章推荐功能官方 Q&A 置顶帖** developers.weixin.qq.com（A 级官方一手）

#### Step 3.5.0: 自动跑 Rule 4 tags 自检（v1.7.4+，先于 checklist）

发 checklist 之前，**先自动跑一次 Rule 4 检测**（tags ≥3 + 中文 tags ≥3），如果不通过则在 checklist 中标黄警告并给出建议补丁。

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/review_selfcheck.py \
  /ABSOLUTE/PATH/article.md --rules 4 --json
```

解析返回 JSON：

| 状态 | 处理 |
|---|---|
| `passed: true` | checklist 中 tags 项标 ✅ "已自动通过" |
| `passed: false` + tags <3 | checklist 中 tags 项标 ⚠️，建议作者补 1-2 个中文 tag（基于 title + description 推断） |
| `passed: false` + 中文 tag <3 | checklist 中 tags 项标 ⚠️，建议把英文 tag 改为中文（例如 `MCP` → `MCP工具`、`AI` → `AI工具` 这种带中文锚的形式） |

**为什么提到 publish 阶段也跑**：4 篇实测发现 write 阶段生成的 frontmatter 默认只 2 个 tag，全英文。这是 LLM 的默认偏差。在 publish 阶段最后自检一次是最低成本的兜底防护——如果不达标，作者可以在发布前编辑 frontmatter 补足。

依据：4 篇实测全部命中 Rule 4 失败（tags=2，中文 tag=1）。

publish 完成后、用户实际发布到公众号**前**，必须打印这条 checklist：

```
─────────────────────────────────────────────────────────────
📋 微信发布前 checklist（6 项必须人工确认）

【合规项】不做会被平台自动加标识 + 触发流量限制

  [ ] 后台「创作来源 → 内容由 AI 生成」（4 选 1 单选）
      ⚠ 发布后不可修改、不可删除
      依据：GB 45438-2025 + 珊瑚安全 2025-08-31 公告

  [ ] 文末已包含 AIGC 显式声明
      （Rule 18 自动检查，应该已通过）

  [ ] 文中无「非 AI 生成 / 完全人工 / 纯手写」反向声明
      （Rule 23 自动检查，应该已通过）
      依据：珊瑚安全公告"不得删除/篡改/伪造平台标识"

【推荐池命中项】不满足则不进推荐池，未关注用户读不到

  [ ] 文章字数 ≥ 300 → 后台点亮「原创」声明
      依据：明月清风官方答复（2020-06-15）300 字门槛

  [ ] 后台「允许平台推荐」开关 **保持开启状态**（默认 ON）
      ⚠ 一旦勾选「不允许推荐」无法撤回（不可逆操作）
      依据：《推荐运营规范》"将无法重新选择允许平台推荐"

  [ ] 单发未分组（不要用「分组群发」功能）
      依据：《推荐运营规范》"分组群发的内容将不会被推荐"

【看一看 NLP 匹配项】tags 不达标会拉低长尾推荐池命中

  [ ] frontmatter tags ≥ 3 个 且 ≥ 3 个中文 tag
      （Rule 4 自动检查 — Step 3.5.0 已跑过, 见上方警告/建议）
      依据：4 篇实测全部因 tags=2 / 中文 tag=1 命中 Rule 4 失败
      建议格式：tags: [Kubernetes, Docker, 容器运维, AI工具, 实战教程]
      ⚠ 全英文 tags（如 [MCP, AI, DevOps]）让看一看 NLP 算法
         无法匹配中文兴趣画像 — 必须改成含中文锚的形式

发布后 24h-7 天，去后台「内容分析 → 单篇群发」查看：
  • 推荐曝光 / 推荐阅读 → 是否进了推荐池
  • 送达 vs 阅读 → 标题钩子打开率（粉丝阅读率）
  • 分享 / 收藏 / 在看 → 朋友推荐池触发器（2025-03 扩测）
─────────────────────────────────────────────────────────────
```

**实施方式**：在 Step 5 完成摘要之后追加这段输出。即使是 `--output` 显式指定目录的 Mode A，也要打印——这些约束与文件路径无关，是发布动作本身的硬约束。

**例外**：如果 review skill 已确认文章 `wechat_target: false`（明确非公众号场景，如纯 blog 输出），可以跳过此 checklist。

**为什么 checklist 而不是自动化**：微信公众平台**没有公开 API**——「创作来源」「原创声明」「允许推荐」三项都必须在 mp.weixin.qq.com 后台 UI 人工操作，article-craft 只能提醒，不能代为执行。

### Step 4: WeChat Distribution (optional)

If the user wants to publish to WeChat, invoke `/wechat-seo-optimizer` for title and abstract optimization.

```
Question: "Optimize for WeChat distribution?"
Options:
  - Yes -- run SEO optimizer for title and abstract, then convert to WeChat format
  - No -- keep as Markdown only
```

If yes:
1. Invoke `/wechat-seo-optimizer` on the published article.
2. The WeChat converter will save the HTML to `03-创作/已发布/<YYYY-MM>/` (e.g., `03-创作/已发布/2026-03/`).

### Step 5: Completion Summary

Output a summary table with all relevant information:

```markdown
## Publish Complete

| Item | Value |
|------|-------|
| **File path** | `/absolute/path/to/02-技术/.../article.md` |
| **KB directory** | `02-技术/<matched-subdirectory>/` |
| **Sidecars** | `_evidence.json`, `_harvest_menu.md` (copied / none) |
| **Image status** | N/M uploaded (or "no images" / "N placeholders remaining") |
| **Review score** | X/70 (PASS/FAIL) |
| **WeChat** | optimized / skipped |
```

Always include the **absolute file path** so other sessions can locate the article.

---

## Standalone Mode

When invoked directly (not as part of the orchestrator pipeline):

1. AskQuestion for the article file path if not provided.
2. Read the article to extract title and tags for directory matching.
3. Execute Steps 1-5 above.
4. If review score is not available (article was not reviewed), note it in the summary:
   ```
   | **Review score** | not reviewed (run `/article-craft:review` first) |
   ```

---

## Reference

- Knowledge base directory rules: `${CLAUDE_PLUGIN_ROOT}/references/knowledge-base-rules.md`
- SmartDirectoryMatcher source: `${CLAUDE_PLUGIN_ROOT}/scripts/utils.py`
- WeChat HTML output location: `03-创作/已发布/<YYYY-MM>/`
