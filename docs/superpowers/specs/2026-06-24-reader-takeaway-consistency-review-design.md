# 读者收获提炼 + 承诺-兑现一致性复查 — 设计文档

- **日期**: 2026-06-24
- **状态**: Draft（待实现）
- **影响范围**: `skills/review/SKILL.md`、`scripts/review_selfcheck.py`（复用现有解析函数 + 新增确定性写函数）、`tests/`
- **设计哲学对齐**: augmentation > gating（软信号、不进 `WRITE_GATE_RULES`、不开自动重写循环），沿用 v1.8 body-form 软检查成例
- **修订说明**: 本版（重塑版）合并了三轮并行架构/设计/安全审查的结论——取消独立 Phase 0、并入 Phase 2 打分前置步、frontmatter 改用确定性写函数、sidecar 降级为待定。审查要点见 §9。

## 1. 背景与动机

写完文章后，作者想知道「这篇到底给了读者什么」，并据此**反查文章质量**：标题/开头承诺的东西，正文是否真给到了。本质是一道「承诺 vs 兑现」一致性检查，能抓出 LLM 高发的失败模式——标题党、空洞章节、AI 水文（收获全是套话、无硬信息）。

现有 review skill 两段式：
- **Phase 1**：23 条规则脚本自检（`scripts/review_selfcheck.py`）。**会原地改正文**（SKILL.md Rule 1 红旗词替换、Rule 12 改模板化开场、Rule 18 追加 AIGC footer 等）。
- **Phase 2**：8 维诊断打分，`/80`，阈值 `63`，自 v1.4.4 起 diagnostic-only（不自动改）。

目前没有任何「读者视角收获提炼」环节，也没有 frontmatter `takeaways` 这类读者收获字段（Rule 4 的 `description` 是 ≤120 字的 meta 描述，维度不同）。本设计新增该能力。

## 2. 目标 / 非目标

**目标**
- 在 review 内，以读者视角提炼「这篇文章给读者的收获与关键信息」。
- 用该提炼反查文章：识别「承诺了但没兑现」的缺口，作为质量自检软信号。
- 把核心收获落成**可发布产物**（frontmatter `takeaways:`），供 publish / share-card 复用。

**非目标**
- 不新增 review 评分维度（不破坏 `/80` 与阈值 63）。
- 不进 `WRITE_GATE_RULES`，不阻断 save，不开自动重写循环。
- review 不在正文里插入可见的「本文要点」块（保持只读正文，避免孤儿化图片占位符）。
- 不复用 Rule 4 的 `description` 字段。
- 不立独立 Phase 0、不产 sidecar、不加独立开关（见 §3、§8）。

## 3. 总体设计

### 3.1 放置：并入 Phase 2，跑在 Phase 1 之后

**不新增独立阶段。** 在 **Phase 2 打分流程的最前面**加一个「读者收获提炼」前置步。因为 Phase 2 本就在 Phase 1 之后运行、且本身就是「agent 读文章后判断」，把提炼放这里能一举消除三个问题：

- **顺序正确**：Phase 1 已经把红旗词/开场/footer 改完，提炼基于的是**最终发布版正文**，takeaways 与正文不会错位。
- **draft 天然跳过**：Phase 2 在 `draft` 模式整段跳过（SKILL.md「If mode is draft: skip this phase」），提炼随之跳过，**无需新增开关**。
- **零新交互分支**：缺口大时复用 Phase 2 既有的 `AskUserQuestion`（Publish anyway / Abort / Re-run write with hints）。

`quick` 模式本就不跑 review，不受影响。

### 3.2 提炼产出结构

以读者视角通读（已修复的）全文，产出结构化数据：

| 字段 | 内容 | 角色 | 是否落盘 |
|---|---|---|---|
| **核心收获** | 3–5 条：读者读完「能做什么 / 知道了什么 / 改变了什么判断」 | 兑现 | ✅ 落 frontmatter `takeaways:` |
| **关键信息点** | 文章实际交付的硬信息（命令、结论、数据、可复现步骤） | 兑现 | ❌ 仅进程内临时数据，用于比对 |
| **隐含承诺** | 标题 + Hook + 各级 `##` 标题*承诺*要给的东西 | 承诺 | ❌ 仅进程内临时数据，用于比对 |

「隐含承诺」的脚手架复用 `review_selfcheck.py` 现有 `get_sections(body)`（按 `## ` 切分）+ `_section_label()`（清成纯标题文字）抽取 `##` 标题集合；标题/Hook 用 `get_body` / `parse_frontmatter`。承诺**语义**判断仍由 agent 完成，脚本只提供确定性切分。

### 3.3 承诺-兑现一致性（「再次 review」软信号）

对照「隐含承诺」与「核心收获 / 关键信息点」，识别缺口：**承诺了但正文没兑现 / 标题党 / 空洞章节**。这**不是新维度**，扣分流入 Phase 2 现有维度（沿用 v1.8 body-form 软检查成例）。

为避免与已有机械规则**重复扣分**，定三条约束：

1. **补集原则**：提炼出的缺口只在「机械规则（Rule 6/17/19/22）**没**覆盖该具体行/章节」时计入。提炼缺口是机械规则的补集，不叠加。
2. **维度归属**（修正「标题与Hook 维度纯机械、容纳不了标题党」的问题）：

   | 缺口类型 | 流入维度 |
   |---|---|
   | 承诺的能力/结论正文没给、空洞章节 | **内容深度** |
   | 标题/Hook 承诺 > 正文兑现（标题党） | **内容深度**（兑现侧，不塞进纯机械的「标题与Hook」） |
   | 收获全是套话、无硬信息 | AI 痕迹 / 看一看友好度（仅当 Rule 17/22 未覆盖） |

3. **单维度扣分上限 -2**：防止 LLM 主观判断把某维度打穿到 0、放大评分波动。

**严重度分级 + 条数上限**（防 Rule 24 式信号稀释）：缺口分两级——
- `error` 级（真·标题党 / 完全不兑现的承诺）：在 Feedback 区**显著列出**，即使总分过线也展示，**上限 N 条**（实现时定，建议 ≤3）。
- `warning` 级（承诺略大于兑现等轻微项）：折叠为次级提示，不进 Feedback 主区，不计入扣分。

落地仍是软的：不进 WRITE_GATE，不开自动重写循环；用户决策走 Phase 2 既有 `AskUserQuestion`。

### 3.4 可发布产物的落地：确定性 frontmatter 写函数

**唯一允许的 mutation 是写 frontmatter `takeaways:`（核心收获列表）。** 这是对 review 现有铁律「mutations only happen in write, not review」开的一个**受限例外**，需在 SKILL.md Invariants 增补一条明确它的边界（只动 frontmatter、只增改 `takeaways` 一个 key）。

**不用 agent 的 `Edit` 写**（非确定性、可能跨过 frontmatter 闭合 `---` 改到正文、难安全覆盖多行 YAML 列表）。改为**新增一个确定性写函数**（放在 `review_selfcheck.py` 或新辅助脚本），流程：

```
parse_frontmatter(content)              # 复用现有 yaml.safe_load 读
  → fm["takeaways"] = [核心收获...]     # dict 层面只增改一个 key，其余 key 原样保留
  → yaml.safe_dump(fm, sort_keys=False, allow_unicode=True)  # 重序列化整块 frontmatter
  → 用 frontmatter_end_line() 定位，只替换 [1, end_line] 区间，正文区物理不可触
  → 回读 parse_frontmatter 校验          # 解析失败则回滚，走降级
```

SKILL.md 调用该脚本函数，而非让 agent 手搓 Edit——与现仓库「Phase 1 never asks the agent to write greps by hand … calls the script once」一致。

**降级矩阵（≥4 分支）**：

| 情形 | 处理 |
|---|---|
| 无 frontmatter（文件无开头 `---`） | **不写**。绝不在文件头硬塞 frontmatter（等于改正文头）。仅在报告里展示 takeaways，不落盘。 |
| 有 frontmatter、无 `takeaways` | 在 dict 加 key，重序列化写入。 |
| 有 frontmatter、已有 `takeaways` | **覆盖**整个 key（dict 设值即覆盖，幂等），不追加、不留旧列表项孤儿。 |
| frontmatter 解析失败（YAML 非法） | 不写，记录警告，报告里展示 takeaways。 |

### 3.5 幂等性

由「结构化覆盖整个 frontmatter 块」保证：重复跑 review / `--upgrade` 重跑时，`fm["takeaways"] = ...` 永远是覆盖同一 key，不会产生孤儿列表项。**注意产品语义**：若用户手工润色过 `takeaways:`，review 重跑会无声覆盖——文档需注明「review 会覆盖自动生成的 takeaways」。

## 4. 数据流与接口

```
write → ... → images → verify-claims → review
                                          ├─ Phase 1  23 规则自检（原地改正文，不变）
                                          └─ Phase 2  (publish 模式)
                                                ├─ [新] 读者收获提炼（基于已修复正文）
                                                │     ├─ 抽 ## 标题脚手架（复用 get_sections/_section_label）
                                                │     ├─ agent 判定 核心收获/关键信息点/隐含承诺
                                                │     ├─ 承诺-兑现缺口 → 补集+分级+上限 → 流入现有维度
                                                │     └─ 确定性写 frontmatter takeaways:（含降级）
                                                └─ 8 维打分（/80、阈值 63、verdict 不变）
        publish ← frontmatter takeaways:（搬运 + 可选渲染「本文要点」块，属下游）
```

- **review 的 `allowed-tools`** 已含 `Read/Edit/Bash/Grep/AskUserQuestion`；脚本写入走 `Bash` 调脚本，无需新增工具。
- **复用的现有函数**（`review_selfcheck.py`）：`parse_frontmatter`、`frontmatter_end_line`、`get_body`、`get_sections`、`_section_label`、`strip_code_blocks`。
- **新增**：一个确定性 `write_takeaways(content, takeaways) -> (new_content, status)` 纯函数（§3.4），可被 pytest 直接 import 调用。

## 5. 错误处理与边界

- frontmatter 写入的四分支降级见 §3.4 表。
- **绝不触碰**：`<!-- IMAGE: -->`、`<!-- PROMPT: -->`、`<!-- SCREENSHOT: -->`、`<!-- HARVEST: -->`、CDN 图片 URL，以及 frontmatter 内既有的封面/CDN URL 字段（重序列化时其他 key 逐字节保真，写后校验）。
- 「Review never regenerates the whole article」继续成立：整块 frontmatter 重序列化**不得**顺带规范化或重排正文，正文区不进入写入区间。
- draft 模式跳过整个 Phase 2，自然无产出。

## 6. 测试计划

诚实区分「确定性可单测」与「LLM 主观判断（无单测）」。现有 `tests/` 用 `importlib` 动态加载脚本模块直接调纯函数（`test_review_selfcheck.py` / `test_publish_plan.py`），新测试复用此风格。

**确定性单测（可断言）**：
1. **`##` 标题脚手架**：`get_sections` + `_section_label` 抽取的隐含承诺集合正确（边界：无 `##`、含代码块内的 `#`）。
2. **frontmatter 安全写入**：调 `write_takeaways`，断言——
   - 闭合 `---` 之后的正文区**逐行 diff 不变**；
   - frontmatter 内**除 `takeaways` 外其他 key diff 不变**（对称断言，守住 1.2/1.3 类风险）；
   - frontmatter 含 CDN/cover URL 字段时该字段**逐字节不变**。
3. **降级四分支**：无 frontmatter（断言不在文件头插入任何内容、文件字节不变）/ 有无 takeaways / 解析失败，各一用例。
4. **幂等覆盖**：连写两次 takeaways，结果等同写一次，无孤儿列表项。
5. **开关/模式**：把模式判定下沉到脚本入口（接受 `--mode` 或等价参数），断言 draft 模式下 `write_takeaways` 不被触发、文件字节级零改动。

**非单测（示例驱动 + dogfood）**：
- 承诺-兑现缺口识别、核心收获/隐含承诺的语义判定，是 agent 主观环节，**不写 pytest 断言**（与 Phase 2 打分同属 agent 判断，本仓库 Phase 2 主观分也无单测）。改为 SKILL.md 内 few-shot 示例 + 人工 dogfood 验证。文档明文标注此边界。

## 7. 版本与文档

- 视改动量走一次 `minor` 版本 bump（`scripts/bump_version.py minor`），同步 13 个 skill 的 frontmatter 版本（lockstep 不变量）。
- 在 `CLAUDE.md` 的 review skill 描述与「Cross-skill data flow」处补一句 Phase 2 读者收获提炼 / `takeaways` 字段的说明。
- 新增一条 **Known design debt**：承诺-兑现缺口是 LLM 主观判断，有 Rule 24 式「高密度警告稀释信号」风险；§3.3 的分级+上限是缓解器，给 **4-6 周观察窗**（对齐 v1.7.4 augmentation 验证节奏）。若缺口分级在实践中仍噪声过高，再收紧判定或并入内容深度。
- 不新增 env 开关（draft 天然跳过），故不动 `ENV.md` / `env.example.json`。

## 8. 待实现时定 / 待定（非阻塞）

- **sidecar `_takeaways.md`：暂不做。** frontmatter `takeaways:` 已携带全部数据、下游（publish/share-card）都读 frontmatter，sidecar 与之完全重复且无独立消费者（对比 `_evidence.json` 是 write 阶段消费的输入、有独立生命周期）。若未来出现「需单独打开的要点文件」需求，再在 `scripts/publish_plan.py` 的 `SIDECAR_FILES`（模块级元组）加一项即可——零函数签名改动。
- `error` 级缺口 Feedback 显著展示的条数上限 N（建议 ≤3）具体取值。
- 「关键信息点」是否真的全程不落盘，还是 dogfood 后发现有展示价值再补。
- publish / share-card 渲染「本文要点」块的位置与样式（下游呈现，独立小改动，后续单独处理）。

## 9. 审查结论沉淀（三轮并行审查）

本设计在初稿后经三个并行 agent（架构落地 / 设计自洽 / 不变量与可测性）审查，重塑版已吸收：

- **架构**：`publish_plan.py` sidecar 仅改 L19 元组（本版暂不改）；`get_sections`/`_section_label` 现成可复用；**修正事实错误**——tone 校准开关 `ARTICLE_CRAFT_TONE_CALIBRATION` 在 `review_selfcheck.py` 用 `os.environ` 读（非 config.py/env.json）；本版已取消独立开关故不涉及。
- **设计自洽**：消除「Phase 0 落盘早于 Phase 1 修复」的高危顺序漏洞（并入 Phase 2 后置）；补「补集原则 + 单维度上限」消歧重复扣分；「标题党」归入内容深度而非纯机械的标题与Hook 维度。
- **不变量与可测性**：frontmatter 写入由 `Edit` 改为确定性脚本函数（解决跨界改正文、多行列表覆盖、可测性三事）；降级矩阵补到 4 分支；测试计划诚实拆分确定性单测 vs LLM 主观判断。
