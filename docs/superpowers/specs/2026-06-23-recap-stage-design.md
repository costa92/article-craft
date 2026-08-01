# Recap 收获复盘阶段：收获清单 + 兑现度复查

**Status**: designed (target v1.10.0)
**Date**: 2026-06-23
**Target version**: article-craft v1.10.0
**Author**: costa
**Based on**: 用户需求「写完文章后总结读者收获，再据此 review 文章是否兑现」+ 既有 review Phase 2 诊断性评分先例（v1.4.4）+ 项目 augmentation > gating 哲学

## 0. 问题陈述

现有 pipeline 在 `review` 之后直接 `publish`。review 检查的是**规则合规**（23 条 self-check）和**通用质量维度**（八维评分），但**没有一处回答「这篇文章到底给读者带来了什么、以及它是否真的兑现了这些承诺」**。

这导致两类问题：

1. **缺可见交付物**：作者发文前看不到一份「本文你会获得什么」的提炼清单，无法快速判断文章价值密度，也无法直接复用为公众号导语/朋友圈文案。
2. **缺兑现度校验**：文章可能在标题/Hook 里承诺了收获（钩子拉得很满），但正文并没有给出对应的具体内容/代码/数据 —— 即「挂羊头卖狗肉」。现有 review 不专门检查 **承诺 ↔ 兑现** 的一致性。

定位：这是一个 **读者价值复盘** 问题，正交于规则合规（review Phase 1）和通用质量（review Phase 2）。需要一个专门阶段：先提炼读者收获，再逐条复查正文是否兑现。

## 1. 设计目标

1. 新增独立阶段 `recap`（收获复盘），位于 `review` 之后、`publish` 之前（standard 模式）。
2. **Phase 1 生成收获清单**：从全文提炼 3–5 条具体读者收获 + 关键信息/结论 + 适合谁读，作为**可见交付物**。
3. **Phase 2 兑现度复查**：逐条判断正文是否真兑现（兑现/部分兑现/未兑现），算出兑现率，加一致性检查（收获 ↔ 标题钩子 + 开头 Hook）。
4. **交付物落点**：聊天里输出 + 边路 sidecar 文件（`_recap.md` 人读 + `_recap.json` 机读）。**绝不改文章正文**。
5. **诊断 + 用户决定**：兑现率低于阈值时用 AskUserQuestion（Publish anyway / Re-run write with hints / Abort），镜像 review Phase 2，符合 augmentation > gating。
6. **纯 prompt-first**：兑现度判断是 LLM 工作（与 review Phase 2 八维评分同性质），零新脚本；sidecar 用 Write 工具写。
7. quick / draft 模式跳过（与 review / publish 一致）。
8. 接入 pipeline 状态机：state 协议落盘 + upgrade 模式可检测。
9. 不破坏现有任何 skill、规则、管线；缺 sidecar 时降级（heuristic）。

## 2. 非目标（明确不做）

- ❌ 把收获清单**插入文章正文**（此时图片已生成，改正文有孤立 `<!-- IMAGE -->` 占位符 / CDN URL 的风险 —— 见 review 不变量）。仅聊天 + sidecar。
- ❌ 在 `review` skill 里加 Phase 3（用户明确选「独立新阶段」）。
- ❌ 新增 `scripts/recap.py`（可确定性部分太薄，为测试而测试；判断本身不可单测，与 Phase 2 一致）。
- ❌ 硬门禁阻断 publish（与项目「不新增硬门禁」坐标不一致）。改用诊断 + 用户决定。
- ❌ 把兑现度纳入 `WRITE_GATE_RULES` 或新增 self-check rule。
- ❌ 自动改写正文以「补齐」未兑现项（开放式自动修订不收敛，且会动已成稿 —— 见 review v1.4.4 取消 auto-revise 的教训）。回跳 write 由用户显式选择。

## 3. 架构

### 3.1 pipeline 位置

```
requirements → verify → [evidence] → write → screenshot → (share_card?)
  → images → verify-claims → review → 【recap】→ publish
```

- standard 模式：review PASS 后进入 recap。
- quick / draft 模式：recap `skipped`（reason: "mode skip"），与 review/publish 一致。

### 3.2 数据流

```
review 返回 PASS
  → recap 读 article.md（终稿，含图）
    → Phase 1：提炼收获清单
    → Phase 2：逐条兑现度复查 + 一致性检查 → 兑现率
      → 写 sidecar：_recap.md + _recap.json（与 article.md 同目录）
      → 聊天输出：收获清单 + 兑现度表 + verdict
        → verdict=PASS         → publish
        → verdict=NEEDS_REVISION → AskUserQuestion
             Publish anyway        → publish
             Re-run write w/ hints → 回跳 write（hints=未兑现/部分清单），recap_rerun_count++
             Abort                 → 停止
```

### 3.3 与现有阶段的正交关系

| 阶段 | 回答的问题 |
|------|-----------|
| review Phase 1 | 文章是否**违反规则**（23 条 self-check）？ |
| review Phase 2 | 文章**通用质量**如何（八维评分）？ |
| **recap** | 文章**给读者带来什么**、且**是否兑现了这些承诺**？ |

## 4. recap skill 详细设计（`skills/recap/SKILL.md`）

### 4.1 frontmatter

```yaml
---
name: article-craft:recap
version: <锁步当前 plugin 版本>
description: "收获复盘 — 提炼读者收获清单并复查正文兑现度。诊断性，不改正文。"
allowed-tools:
  - Read
  - Write
  - AskUserQuestion
---
```

> `Write` 仅用于落 sidecar；**刻意不声明 `Edit`**，从工具层面强约束「绝不改正文」。不声明 `Bash`：recap 无脚本，state 文件落盘是 orchestrator 的职责（它 bracket 每个阶段调 `pipeline_state.py`），不是 recap skill 自身的事。

### 4.2 输入

- **Article file path**：要复盘的 `.md` 绝对路径。
- **Mode**（recap 自身的参数，**不同于** pipeline 的 `--draft`）：`publish`（默认，做完整两 Phase）/ `draft`（只出收获清单，跳兑现度复查 —— 与 review skill 自身的 publish/draft 语义对齐）。
  - 注意区分：pipeline 处于 `--draft`/`--quick` 模式时 **整个 recap 阶段被 skip**（§3.1 / §5.6）；这里的 mode 是**标准模式下 recap 阶段内部**、或 standalone 调用 recap 时的子模式，与 review skill 的双模式设计完全平行。
- standalone 调用且无路径 → AskQuestion 索取。

### 4.3 Phase 1 — 生成收获清单（可见交付物）

读全文，提炼三块：

1. **本文你会获得**（3–5 条）：每条是读者读完能**做到/知道**的具体事，挂到对应章节标题。
   - 禁空话：「了解了 X 的重要性」「掌握了 X 的基本概念」这类不算一条有效收获。
   - 每条须可对应正文里的具体内容（代码/步骤/数据/结论）。
2. **关键信息/结论**：文章真正给出的事实、数据点、明确结论（区别于「收获」=能力/认知，这里=硬信息）。
3. **适合谁读**：1 行，目标读者画像。

### 4.4 Phase 2 — 兑现度复查（publish 模式）

draft 模式跳过本 Phase，只输出 Phase 1 清单。

对 Phase 1 每条「本文你会获得」逐条判级：

| 级别 | 判定标准 |
|------|---------|
| `兑现` | 正文有具体内容/代码/数据/锚点充分支撑该收获 |
| `部分兑现` | 提到了但单薄、无具体支撑（如只有结论无过程） |
| `未兑现` | 标题/Hook 承诺了但正文没给（挂羊头卖狗肉） |

**一致性检查**：收获清单是否跟标题钩子（Rule 19）+ 开头 Hook（Rule 2）对得上 —— 若标题/Hook 暗示的收获在清单/正文里找不到，记一条 `未兑现`。

**兑现率计算**：

```
兑现率 = (兑现数 × 1.0 + 部分兑现数 × 0.5) / 收获总数
```

**verdict 判定**：

- `PASS`：兑现率 ≥ **0.8** 且**无任何 `未兑现` 项**。
- `NEEDS_REVISION`：兑现率 < 0.8，**或**存在任一 `未兑现`（尤其标题/Hook 承诺的，无论率多高）。

### 4.5 输出

**聊天输出**（始终）：

```markdown
## 收获复盘 (Recap)

### 本文你会获得
1. <收获> — 见「<章节>」
2. ...

### 关键信息/结论
- <硬信息>

### 适合谁读
<画像>

### 兑现度 (publish 模式)
| # | 收获 | 级别 | 正文位置 | 说明 |
|---|------|------|---------|------|
| 1 | ... | 兑现 | L120「<章节>」| ... |
| 2 | ... | 部分兑现 | L88 | 只有结论缺过程 |

兑现率：X.XX（阈值 0.80）
Verdict：PASS / NEEDS_REVISION
```

**Sidecar**（与 article.md 同目录，用 Write 工具写）：

- `_recap.md`：上述聊天输出的人读副本。
- `_recap.json`：机读：

```json
{
  "article": "/abs/path/article.md",
  "generated_at": "2026-06-23T10:00:00Z",
  "takeaways": ["...", "..."],
  "key_info": ["..."],
  "audience": "...",
  "delivery": [
    {"takeaway": "...", "level": "兑现", "where": "L120", "note": "..."}
  ],
  "delivery_rate": 0.83,
  "verdict": "PASS"
}
```

### 4.6 verdict + 用户决定（NEEDS_REVISION）

镜像 review Phase 2 的 AskUserQuestion：

```
Question: "收获兑现率 {rate}（阈值 0.80）。recap 是诊断性的 —— 选择如何继续："
Options:
  - Publish anyway     — 接受现状，继续 publish
  - Re-run write with hints — 回跳 write，把未兑现/部分兑现清单作为 hints
  - Abort              — 停止，文章留在当前路径供手改
```

- 不嵌套自动修订循环；每轮都是新的显式用户决定。
- 「Re-run write with hints」→ orchestrator 回跳 write 阶段，hints = `delivery` 里所有 `未兑现`/`部分兑现` 条目。

### 4.7 不变量

- recap **只产出聊天 + sidecar**，绝不 Edit 文章正文。
- 绝不碰 `<!-- IMAGE: -->` / `<!-- PROMPT: -->` / `<!-- SCREENSHOT: -->` / `<!-- HARVEST: -->` / CDN image URL（图已生成，改正文会孤立占位符）。
- 不重新生成文章。
- mutation 只发生在用户选「Re-run write with hints」（且发生在 write，不在 recap）。

## 5. orchestrator 改动（`skills/orchestrator/SKILL.md`）

### 5.1 新增 Step 3.7.5 Recap（review 之后、publish 之前）

- standard 模式：review 返回 PASS（或用户「Publish anyway」）后调用 `article-craft:recap`（Skill 工具）。
- 传 article.md 绝对路径。
- 解析 recap 返回的 verdict：

| 返回值 | 含义 | orchestrator 动作 |
|--------|------|------------------|
| `PASS` | 兑现率 ≥ 0.8 无未兑现，或用户「Publish anyway」 | 继续 publish |
| `NEEDS_REVISION_RERUN_WRITE` | 用户选「Re-run write with hints」 | 回跳 Step 3.3 write，hints 输入；回跑后 screenshot/images/verify-claims/review/recap 正常续跑。`recap_rerun_count` 封顶 2，第 3 次 NEEDS_REVISION 时 AskUserQuestion 去掉 rerun 选项 |
| `ABORT` | 用户选「Abort」 | 停止 pipeline，summary 报告 "recap ABORT @ rate X" |

### 5.2 状态追踪行

在 Step 2 状态追踪块 `review` 之后、`publish` 之前加：

```
  recap:        pending
    └─ 收获清单 + 兑现度复查（诊断性）
```

### 5.3 State 写协议 payload 表

新增一行：

| Stage | Payload keys |
|-------|-------------|
| `recap` | `takeaways_count`, `delivery_rate`, `verdict`, `recap_sidecar` |

### 5.4 Summary 表

在 review 与 publish 之间加 recap 行：

```
│ recap        │ success  │ 兑现率 0.83 (PASS)            │
```

### 5.5 Rerun guard

state 文件追踪 `recap_rerun_count`；≥ 2 时下一轮 recap NEEDS_REVISION 的 AskUserQuestion 去掉「Re-run write with hints」，只留「Publish anyway / Abort」。与 review 的 `review_rerun_count` 同机制、独立计数。

### 5.6 模式跳过

quick / draft 模式：recap `skipped`（reason: "mode skip"），写 state 文件 + 在 chat tracker 标 skipped。

## 6. pipeline_state.py 改动

`recap` 是 standard 模式阶段，需注册进阶段表，否则 upgrade 模式的 `missing-stages` 检测不认识它。

- 把 `recap` 加入 standard 模式阶段序列（在 `review` 之后、`publish` 之前）。
- 启发式判定（无 state 文件时）：recap `done` ⇔ 文章同目录存在 `_recap.json`。
- `cleanup`：publish 成功后清 state 文件时，sidecar `_recap.md` / `_recap.json` 的去留 —— **保留**（它们是交付物，跟 `_evidence.json` 一样属 SIDECAR_FILES，随 publish 一并搬到 KB）。需在 `publish_plan.py` 的 `SIDECAR_FILES` 里加 `_recap.md` / `_recap.json`。

## 7. 牵动文件清单

| 文件 | 改动 |
|------|------|
| `skills/recap/SKILL.md` | **新建**：本 spec §4 |
| `commands/recap.md` | **新建**：顶层，读 recap SKILL.md（守 1:1 skill↔command 不变量、单前缀解析） |
| `skills/orchestrator/SKILL.md` | §5：Step 3.7.5 + 状态行 + payload 表 + summary 行 + rerun guard + 模式跳过 |
| `scripts/pipeline_state.py` | §6：注册 recap 阶段 + 启发式检测 |
| `scripts/publish_plan.py` | `SIDECAR_FILES` 加 `_recap.md` / `_recap.json` |
| `.claude-plugin/plugin.json` + `marketplace.json` + 全部 `skills/*/SKILL.md` | 版本锁步（`bump_version.py minor` → v1.10.0） |
| `CLAUDE.md` | pipeline 流程图 + recap 阶段说明 + skill 列表 + standalone 命令清单 |
| `tests/test_plugin_layout.py` | 无需改 —— 自动覆盖新 skill 的 1:1 映射 / 版本锁步 / 脚本引用 |

## 8. 测试策略

- **布局契约**：现有 `tests/test_plugin_layout.py` 自动校验 `skills/recap/` ↔ `commands/recap.md` 1:1、SKILL.md frontmatter 完整 + 版本锁步、引用脚本存在 —— 跑一遍即覆盖。
- **pipeline_state**：在 `tests/test_pipeline_state.py` 加用例：standard 模式 `missing-stages` 含 `recap`；`_recap.json` 存在时 recap 判 done；quick/draft 模式 recap 不在 missing。
- **publish sidecar**：在 `tests/test_publish_plan.py` 加用例：`_recap.md` / `_recap.json` 被识别为 sidecar 并随 publish 搬运。
- **兑现度判断本身不单测**（LLM 判断，与 review Phase 2 八维评分同性质，靠 dogfood 验证）。

## 9. 版本与发布

- `bump_version.py minor` → **v1.10.0**（新增用户可见阶段，minor 合适）。
- 一次 commit 内完成版本锁步（plugin.json / marketplace.json / 全部 SKILL.md frontmatter）。
- CLAUDE.md 同步更新 pipeline 描述与「Active rule count」无关（recap 不新增 rule）。
