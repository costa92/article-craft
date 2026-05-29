# WeChat-Native Body Form: 正交 body-form 轴

**Status**: design
**Date**: 2026-05-29
**Target version**: article-craft v1.8.0
**Author**: costa
**Based on**: 项目记忆 `project_wechat_target.md`（公众号是真实默认目标，但 7/8 style 是 blog 结构）+ v1.7.x WeChat 合规规则演进 + 既有 tone-axis 先例（v1.4.18）

## 0. 问题陈述

公众号是 article-craft 的真实默认分发目标，但正文引擎本质是 blog 生成器：

- 8 个 style 中 7 个是 blog/长文体，只有 Style H 是公众号原生。`style-guide.md` 自称 "Technical Blog Edition"。
- Style A/C/D 强制 Obsidian callout（`> [!abstract]`），**在公众号根本不渲染**。
- 默认路由偏 blog：默认 Style A，"写一篇关于 X" → tutorial/A。通用请求永远产出 blog 结构的正文。
- WeChat 适配是**事后打补丁**（Rule 18-24 合规 + CTA + 标题公式 + platform-adaptation 维度），叠在一个 blog 形状的正文上，而不是原生的公众号正文结构。
- `wechat_target` 字段被两个 consumer（`write/SKILL.md:169`、`publish/SKILL.md:289`）当成开关读取，但**没有任何地方产出它** → blog 逃生舱是死分支，实际每篇都被当成公众号文却又是 blog 正文。

作者实测痛点（已确认）：**正文结构太像博客** —— callout 不渲染、章节太深太长、铺垫太多，读者在手机上划不动。

定位：这是一个 **body 正文形态（结构/长度形态）** 问题，正交于 **content style（内容类型 A-H）** 和 **depth（字数）**。需要一个真正的「公众号原生正文」形态，而不是给 blog 正文再叠一层合规 lint。

## 1. 设计目标

1. 新增一个 **body-form 开关**（`wechat-native` / `long-form` 两档），默认 `wechat-native`。
2. 开关从三个来源合一解析：CLI flag > frontmatter `body_form:` > 默认 `wechat-native`（与 tone 解析一致）。
3. **正交**于 style（A-H 内容身份不变）与 depth（字数不变）。同一内容 style、同一字数，可渲染成两种正文形态。
4. 复活 `wechat_target`：`wechat_target: false` 作为 `body_form: long-form` 的 back-compat 别名，两个现有死 consumer 改读已解析的 `body_form`。
5. `long-form` == 今天的行为（callout 允许、深章节）—— KB/博客归档副本零回归。
6. 走 **augmentation > gating** 路线（项目既定哲学）：形态规则进 prompt + 软 review 维度，**不新增 `WRITE_GATE_RULES` 硬阻断**。
7. 现有 23 条 rule、tone 系统、图片/截图/verify 管线 —— 全部不破坏。`body_form` 字段缺失时降级为 `wechat-native`。

## 2. 非目标（明确不做）

- ❌ 新增第 9 个 style（会把「形态」和「内容类型」混在一起，导致 style 爆炸）。
- ❌ 写完后再加转换 stage 把 blog 正文重构成公众号体（机械重构成品脆弱，且 padding/深度已写死）。
- ❌ 一次 run 同时产出两种形态文件（`--also-long-form`）—— **推迟**到 re-run 摩擦被证实再做。
- ❌ 根据 depth/教程关键词自动路由到 long-form（这正是要消除的 blog 偏差）。
- ❌ 改动 8 个 content style 的内容身份、tone 系统、图片管线。

## 3. 架构

### 3.1 body-form 数据流（镜像 tone-axis）

```
requirements (解析 + 默认 wechat-native)
  → frontmatter body_form: wechat-native | long-form
    → write (Step 3a 注入 style-guide 的 ## Body Form 段 + 形态条件化 callout)
      → review (Phase 2 软 form-consistency 维度)
      → publish / write 的 wechat_target 读点改读 body_form
```

解析优先级（`scripts/config.py` 新增常量，平行 tone defaults）：

```
--body-form CLI  >  frontmatter body_form:  >  默认 "wechat-native"
legacy: frontmatter wechat_target: false   →   等价 body_form: long-form
```

### 3.2 三个轴的正交关系

| 轴 | 取值 | 决定 | 缺省 |
|---|---|---|---|
| **content style** | A-H | 内容类型 / 修辞模式 | A（教程） |
| **body_form**（新） | wechat-native / long-form | 正文结构与长度形态 | wechat-native |
| **tone** | neutral / casual / opinionated | register 强度 | 由 style 决定 |
| **depth** | quick / tutorial / deep | 字数区间 | tutorial |

`wechat-native + deep` = 一篇长但移动端友好的公众号文（短段、图节奏、单主线），与 `long-form + deep`（blog 深度长文）截然不同。

## 4. WeChat-native 正文形态规则

落在 `style-guide.md` 新增 `## Body Form: wechat-native` 段，**叠在所选 style 之上**。同时**吸收并取代**现有 "Platform Adaptation Rules" 块（30 行代码 / ≤3 标题 / inline 链接 / 800 字断行已在其中）—— 是合并，不是并行规则集。

| 维度 | wechat-native | long-form（今天行为） |
|---|---|---|
| 段落 | ≤ ~200 字 / 3-4 短句，频繁断行 | 不变 |
| 冷开场 | 首屏（~100 字）必须钩住，零「本文将…」铺垫 | 软开场可 |
| callout | **禁用**（公众号不渲染）→ 改为 bold 引导句 或 单行 `>` 引用 | Obsidian `> [!abstract]` 允许 |
| 标题层级 | ≤ 2 级（`##`/`###`），无深嵌套 | ≤ 3 级 |
| 章节形态 | 更少更利落（≈3-5 节），一节一个意思 | 多深章节可 |
| 图节奏 | 每 ~2-3 屏（~600 字）一个视觉物（图/截图/表） | 1 图/章 |
| 主线 | 一条核心问题/冲突贯穿首尾 | 子话题罗列可 |
| 代码 | ≤30 行/块，拆长代码（已是 platform 规则） | ≤30 行/块 |

> 数字均为初始值，可调。来源：现有 platform-adaptation 块 + Rule 2（hook ≤100）+ Rule 7b（最低图数）+ Rule 19（标题钩子）。

## 5. 强制方式（augmentation > gating）

- **主机制 = prompt augmentation。** `write/SKILL.md` Step 3a（已在注入 tone 段处）同时注入 `style-guide.md` 的 `## Body Form: wechat-native` 段。工作实际发生在这里 —— 把形态规则喂进写作上下文，与 tone 一致。
- **callout 形态条件化。** Style A/C/D 现强制 callout；在 `wechat-native` 下写成 bold 引导句 / 纯 `>` 引用；在 `long-form` 下不变。这是每个 style 的一条形态注记，不是重写 style。
- **软 review 维度，不是新 gate。** review Phase 2 在既有 `结构可读` / `看一看友好度` 维度里加 `body-form 一致性` 信号（callout 残留、超长段落、heading 深度超限）。**不新增 `WRITE_GATE_RULES` 条目** —— 与避免高 FP 写作阻断的既定决策一致。若日后实测原生合规率下滑，gating 是 plan B（同 Rule 17/22 打法）。
- **Rule 6 交互（已标记）。** Rule 6（章节深度，≥N 代码块/节）保留，但 wechat-native 章节更少更利落，故 `check_rule_6` 的 per-section 阈值应读 form（native = 略低 N）。一处 form-aware 微调，非重设计。

## 6. 受影响文件

| 文件 | 改动 |
|---|---|
| `skills/requirements/SKILL.md` | 解析 + 默认 `body_form`（默认 wechat-native，long-form 仅显式 opt-in），写入已解析 frontmatter 块 |
| `skills/write/SKILL.md` | Step 3a 注入 Body Form 段；form-conditional callout；`wechat_target` 读点改读 `body_form` |
| `skills/write/style-guide.md` | 新增 `## Body Form: wechat-native` 段，吸收 Platform Adaptation 块 |
| `skills/review/SKILL.md` | Phase 2 软 form-consistency 信号 |
| `skills/publish/SKILL.md` | `wechat_target` 读点改读已解析 `body_form` |
| `scripts/review_selfcheck.py` | Rule 6 阈值 form-aware |
| `scripts/config.py` | `BODY_FORM` 默认常量 + `wechat_target:false → long-form` 别名映射（平行 tone defaults） |

**不触碰**：8 个 content style 身份、tone 系统、图片/截图/verify 管线。

## 7. 边界 / YAGNI

- **一次 run = 一种形态。** 默认 run 产出 wechat-native；要 KB long-form 副本则 `--body-form long-form`（或设 frontmatter）re-run。「一源同时出两形态」明确推迟。
- 不做 AI-detection 评分、不做 per-section form 覆盖、不做自动阈值调参。

## 8. 成功标准

1. 通用请求「写一篇关于 X」默认产出 wechat-native 正文（短段、无 callout、≤3 标题、图节奏），content style 仍解析为 A。
2. `--body-form long-form` / `wechat_target: false` 产出与今天等价的 blog 正文（KB 副本零回归）。
3. `body_form` 字段缺失 → 降级 wechat-native，老文章行为不破坏。
4. 现有 506 测试全绿；新增针对 body_form 解析优先级 + 别名映射 + Rule 6 form-aware 阈值的测试。
5. 一篇 wechat-native dogfood 文章：无 callout 残留、段落/标题深度达标、review form-consistency 维度通过。
