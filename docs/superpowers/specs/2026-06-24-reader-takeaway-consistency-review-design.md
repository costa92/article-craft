# 读者收获提炼 + 承诺-兑现一致性复查 — 设计文档

- **日期**: 2026-06-24
- **状态**: Draft（待实现）
- **影响范围**: `skills/review/SKILL.md`、`scripts/review_selfcheck.py`（或新辅助脚本）、`scripts/publish_plan.py`（sidecar 搬运）、`scripts/config.py`（开关）、`tests/`
- **设计哲学对齐**: augmentation > gating（软信号、不进 `WRITE_GATE_RULES`、不开自动重写循环），沿用 v1.8 body-form 软检查成例

## 1. 背景与动机

写完文章后，作者想知道「这篇到底给了读者什么」，并据此**反查文章质量**：标题/开头承诺的东西，正文是否真给到了。本质是一道「承诺 vs 兑现」一致性检查，能抓出 LLM 高发的失败模式——标题党、空洞章节、AI 水文（收获全是套话、无硬信息）。

现有 review skill 两段式：
- **Phase 1**：23 条规则脚本自检（`scripts/review_selfcheck.py`）。
- **Phase 2**：8 维诊断打分，`/80`，阈值 `63`，自 v1.4.4 起 diagnostic-only（不自动改）。

目前没有任何「读者视角收获提炼」环节，也没有 frontmatter `takeaways` 这类读者收获字段（Rule 4 的 `description` 是 ≤120 字的 meta 描述，维度不同）。本设计新增该能力。

## 2. 目标 / 非目标

**目标**
- 在 review 内，以读者视角提炼「这篇文章给读者的收获与关键信息」。
- 用该提炼反查文章：列出「承诺了但没兑现」的缺口，作为质量自检信号。
- 把提炼落成**可发布产物**（frontmatter + sidecar），供 publish / share-card 复用。

**非目标**
- 不新增 review 评分维度（不破坏 `/80` 与阈值 63）。
- 不进 `WRITE_GATE_RULES`，不阻断 save，不开自动重写循环。
- review 不在正文里插入可见的「本文要点」块（保持只读正文，避免孤儿化图片占位符）。
- 不复用 Rule 4 的 `description` 字段。

## 3. 总体设计

### 3.1 放置

在 review skill 新增 **Phase 0：读者收获提炼**，跑在 Phase 1 之前（站在「读者刚读完」的视角，先于机械规则）。

- `mode == draft` → 跳过 Phase 0（与 Phase 2 同样跳过）。
- `quick` 模式本就不跑 review，不受影响。
- 默认开启、不阻断。可经开关关闭（见 §3.5）。

产物两个去向：
1. 喂给「承诺-兑现一致性」软信号 → 并入 Phase 2 现有维度（§3.3）。
2. 落成可发布产物（§3.4）。

### 3.2 Phase 0 产出结构

以读者视角通读全文，产出结构化「收获总结」：

| 字段 | 内容 | 角色 |
|---|---|---|
| **核心收获** | 3–5 条：读者读完「能做什么 / 知道了什么 / 改变了什么判断」 | 兑现 |
| **关键信息点** | 文章实际交付的硬信息（命令、结论、数据、可复现步骤） | 兑现 |
| **隐含承诺** | 标题 + Hook + 各级 `##` 标题*承诺*要给的东西 | 承诺 |

「核心收获 / 关键信息点」是文章实际兑现的，「隐含承诺」是文章承诺的。

### 3.3 承诺-兑现一致性（「再次 review」）

对照「隐含承诺」与「核心收获 / 关键信息点」，识别缺口：**承诺了但正文没兑现 / 标题党 / 空洞章节**。

这**不是新维度**，而是把扣分流入 Phase 2 现有维度（沿用 v1.8 body-form 软检查把扣分流入「结构可读」的成例）：

| 缺口类型 | 流入维度 |
|---|---|
| 承诺的能力/结论正文没给 | 内容深度 |
| 标题 / Hook 承诺 > 正文兑现 | 标题与 Hook |
| 收获全是套话、无硬信息 | AI 痕迹 / 看一看友好度 |

并在 Feedback 区**单独显著列出**「承诺-兑现缺口」清单——即使总分过线也展示。

落地仍是软的：缺口大时由用户在 Phase 2 既有的 `AskUserQuestion`（Publish anyway / Abort / Re-run write with hints）里决策。Phase 0 不引入新的用户交互分支。

### 3.4 可发布产物的落地

尊重 review 的「少改正文」铁律（图片已生成，改正文会孤儿化 `<!-- IMAGE: -->` 占位符 / CDN URL）：

- **写入 frontmatter `takeaways:`（YAML 列表）** —— 唯一允许的 mutation，**只动 frontmatter，绝不碰正文 / 图片 / handoff 注释**。
- **写一个 sidecar `_takeaways.md`**（与 `article.md` 同目录）—— 随 publish 的 sidecar 搬运逻辑进知识库。`scripts/publish_plan.py` 已搬运 `_evidence.json` / `_harvest_menu.md`，把 `_takeaways.md` 加入其 sidecar 清单。
- **正文里可见的「本文要点」块不在 review 里插** —— 交给 publish / share-card 从 frontmatter `takeaways:` 渲染（它们本就读 frontmatter）。本设计只负责产出数据，不负责正文呈现。

### 3.5 开关

默认开启。提供关闭手段（二选一，实现时定）：
- frontmatter 字段（如 `takeaways: false` 显式关闭），或
- `~/.claude/env.json` 开关（经 `scripts/config.py` 读取，如 `ARTICLE_CRAFT_TAKEAWAYS=false`）。

与现有 tone 校准开关（`ARTICLE_CRAFT_TONE_CALIBRATION`）风格一致。

## 4. 数据流与接口

```
write → ... → images → verify-claims → review
                                          ├─ Phase 0  读者收获提炼
                                          │     ├─ 产出 收获总结（核心收获/关键信息点/隐含承诺）
                                          │     ├─ 写 frontmatter takeaways:（仅 frontmatter）
                                          │     └─ 写 sidecar _takeaways.md
                                          ├─ Phase 1  23 规则自检（不变）
                                          └─ Phase 2  8 维打分（不变）
                                                └─ 承诺-兑现缺口 → 流入 内容深度/标题Hook/AI痕迹
                                                   并在 Feedback 显著列出
        publish ← frontmatter takeaways: + _takeaways.md（搬运 + 可选渲染「本文要点」块）
```

- **review 的 `allowed-tools`** 已含 `Read/Edit/Bash/Grep/AskUserQuestion`，frontmatter 写入用 `Edit` 即可，无需新增工具。
- **实现位置**：Phase 0 的提炼是 LLM 任务（SKILL.md 指令驱动），与 Phase 2 打分同属「agent 读文章后判断」。一致性缺口判定同理。若需要确定性辅助（如抽取所有 `##` 标题做「隐含承诺」清单的脚手架），可在 `review_selfcheck.py` 或新辅助脚本里加一个纯抽取函数，但判断本身留给 agent。

## 5. 错误处理与边界

- **frontmatter 写入失败 / 文章无 frontmatter**：降级为只写 sidecar，不阻断 review。
- **draft 模式**：跳过 Phase 0，不产出 takeaways。
- **幂等**：重复跑 review 时，`takeaways:` 覆盖写、`_takeaways.md` 覆盖写，不追加。
- **绝不触碰**：`<!-- IMAGE: -->`、`<!-- PROMPT: -->`、`<!-- SCREENSHOT: -->`、`<!-- HARVEST: -->`、CDN 图片 URL。这是 review 既有铁律，Phase 0 同样遵守。

## 6. 测试计划

新增 `tests/`（pytest）用例：
1. **结构产出**：给定一篇文章，Phase 0 辅助逻辑（若有抽取脚本）能正确抽出 `##` 标题集合作为「隐含承诺」脚手架。
2. **一致性缺口识别**：构造「标题承诺 X、正文不提 X」的样例，断言缺口能被标记并归类到正确维度。
3. **frontmatter 安全写入**：断言写入 `takeaways:` 后，正文逐行 diff 不变（尤其图片注释 / CDN URL / handoff 注释零改动）。
4. **sidecar 搬运**：断言 `_takeaways.md` 被 `publish_plan.py` 纳入 sidecar 搬运清单。
5. **开关 / draft 跳过**：关闭开关或 draft 模式下，不产出 takeaways、不改文件。

不依赖图像模型 / 网络的纯逻辑测试，遵循仓库现有 `tests/` 风格。

## 7. 版本与文档

- 视改动量走一次 `minor` 版本 bump（`scripts/bump_version.py minor`），同步 13 个 skill 的 frontmatter 版本（lockstep 不变量）。
- 在 `CLAUDE.md` 的 review skill 描述与「Cross-skill data flow」处补一句 Phase 0 / `takeaways` 的说明。
- 若新增 env 开关，更新 `ENV.md` 与 `env.example.json`。

## 8. 待实现时定（非阻塞）

- 开关用 frontmatter 还是 env.json（§3.5）。
- 「隐含承诺」是否需要确定性抽取脚手架，还是全交给 agent（§4）。
- publish / share-card 渲染「本文要点」块的具体位置与样式（属下游呈现，独立小改动，可后续单独处理）。
