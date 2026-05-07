# Tone System: 三档 register-aware 去 AI 化系统

**Status**: design
**Date**: 2026-05-07
**Target version**: article-craft v1.4.18
**Author**: costa
**Based on prior art research**: blader/humanizer, hylarucoder/ai-flavor-remover, Vale prose linter, GPTZero burstiness, 知乎中文去 AI 化共识词表

## 0. 问题陈述

article-craft 当前版本 (v1.4.17) 输出的文章在词汇与连接词层面"register 太单一" — 全文一种正式书面调，从不切换到口语 register。读者第一眼撞到的"AI 味"不是结构问题（结构由 Rule 5 / Rule 6 已经管住），而是：

- 「在某种意义上」「可以看到」「本质上」「值得注意的是」反复出现
- 段首永远是「首先 / 其次 / 最后 / 另外」
- 句长机械均匀（学术界验证的 burstiness 信号）
- 缺第一人称体验、缺强观点、缺人该有的态度

定位：**主观 register / voice quality 提升**，不是 AI-detection 工具评分规避。本文档所有"去 AI 化"措辞均指前者。

## 1. 设计目标

1. 给作者一个 **tone intensity 开关**（neutral / casual / opinionated 三档），不同档对应不同的词汇替换强度、第一人称密度、强观点存在性、句长方差要求
2. 开关从三个来源合一解析：CLI flag > article frontmatter > writing-style 默认
3. 在现有 prevent / detect / fix 三层（write / review / lint）各加一层 tone 维度，**正交**于现有规则
4. 现有 16 条 rule、`lint_article.py` 现有行为、43 个现有测试 — **全部不破坏**（tone 字段缺失时降级为 neutral，行为等价旧版）
5. 不引入外部 AI-detection API 调用（脱网可跑、零额外配置）

## 2. 非目标（明确不做）

- ❌ Originality.AI / GPTZero / ZeroGPT 评分对接（C 方案被否）
- ❌ Voice calibration from user past articles（v2 候选）
- ❌ Per-section tone 覆盖语法（v2 候选）
- ❌ 自动调阈值（v2 — 先攒 20 篇校准数据）
- ❌ 中英双语 tone（仅中文为主，英文段落不参与密度统计）

## 3. 架构

### 3.1 Tone 数据流

```
CLI/orchestrator     frontmatter            writing-style default
─────────────────    ───────────────        ────────────────────
--tone=opinionated   tone: casual    ─┐     (style A → neutral)
--tone=casual    ─┤  tone: neutral   ─┤     (style D → casual)
--tone=neutral   ─┤  (字段缺失)      ─┤     (style G → opinionated)
                 │                    │     (style H → opinionated)
                 ▼                    ▼              ▼
          orchestrator + requirements (resolve_tone 单入口)
                        │
                        ▼
             写回 article.md frontmatter:  tone: <resolved>
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
     write skill    review Rule 17  lint --tone
   (prompt 注入)    (按 tone 调阈值)  (按 tone 切 fix 集)
```

### 3.2 三档 register 语义

| 维度 | neutral | casual | opinionated |
|------|---------|--------|-------------|
| 定位 | 标准技术博客 | 中文技术博主主流 | 个人色彩重的吐槽 / 热点 |
| writing-style 默认归属 | A (技术深挖) / F (速记) | B / C / D / E (教程、评测、入门、复盘) | G (热点) / H (爆料) |
| 第一人称密度 (per 800w) | ≥ 2 | ≥ 4 | ≥ 6 |
| 强观点要求 | 0 (skip) | 0 (软建议) | ≥ 1 (强制) |
| Summary phrase 上限 | 5 | 2 | 0 |
| 句长 CV 下限 | 0 (skip) | 0.30 | 0.45 |
| 「AI 招牌词」红线 | Rule 1 红旗词 | Rule 1 + 段首副词 ≤ 2/篇 | Rule 1 + 不允许「在某种意义上 / 本质上 / 从这个角度看」 |
| 替换强度 | 仅删红旗词 | 中等替换（书面 → 口语） | 强替换（含吐槽变体） + 删尾巴 |
| 结尾 | 信息总结 OK | ≥ 1 行作者立场 | 必须以个人判断 / 预测 / 吐槽收尾 |

#### 对照示范（落入 style-guide.md）

> 原料：UV 是新一代 Python 包管理器，速度比 pip 快 10 倍。

**neutral**:
> uv 是 Astral 出的 Python 包管理器，定位是 pip 的替代品。Astral 自测下来比 pip 快约 10 倍。

**casual**:
> uv 这玩意儿是 Astral 搞的 Python 包管理器，瞄准的就是 pip 的位置。我实测下来比 pip 快接近一个数量级，能看出 Rust 写出来的工具确实是另一个量级。

**opinionated**:
> 说白了 uv 就是来掀 pip 桌子的。Rust 写的，速度直接快一个数量级 — pip 等于卡你十年了。我赌两年内 pip 在新项目里基本看不见。

## 4. 组件改动清单

### 4.1 数据层

| 文件 | 改动 |
|------|------|
| `scripts/config.py` | 新增 `TONE_REGISTER_LEVELS = ("neutral", "casual", "opinionated")`, `STYLE_TO_TONE_DEFAULT: Dict[str,str]`, `TONE_LEXICAL_REWRITES: Dict[str,List[Tuple[Pattern,str,str]]]`（pattern, replacement, severity）, `TONE_THRESHOLDS: Dict[str,Dict[str,float]]`, `STRONG_OPINION_PATTERNS: List[Pattern]`, 函数 `resolve_tone(cli, frontmatter, writing_style) -> str`（三阶优先级单入口） |

### 4.2 逻辑层

| 文件 | 改动 | 大小估计 |
|------|------|----------|
| `scripts/lint_article.py` | 接 `--tone {neutral,casual,opinionated}` 默认从 frontmatter 读；按 tone 切 rewrite 集（继承式：opinionated 包含 casual + neutral）；每条 fix 带 severity；`--min-severity` / `--apply-info` 过滤；inline `<!-- lint:disable rule_id... -->` ... `<!-- lint:enable rule_id... -->` 区块；`--max-passes` (默认 3) 振荡保护 | +180 行 |
| `scripts/review_selfcheck.py` | 新增 `check_rule_17(content, frontmatter, writing_style)`，4 个子检查（密度归一 / 强观点 / summary 上限 / 句长 CV）；Rule 5 现有 `personal_markers < 2` 改为只在 `tone=neutral` 时生效（Rule 17 在 casual+ 接管）。同时新增 4 个文本预处理 helper：`_strip_frontmatter()`、`_strip_code_blocks()`、`_strip_callout_blocks()`、`_strip_image_lines()`（现有 `_split_blocks` / `_is_structural_anchor_block` 不能直接用，因为它们做的是段落切分而非"剥离全部代码块返回纯文本流"） | +160 行 |
| `scripts/pipeline_state.py` | `_scan_article()` 加解析 `tone:`，写入 state 供 `--upgrade` 复用 | +5 行 |

### 4.3 Skill 层（prompt 编排）

| 文件 | 改动 |
|------|------|
| `skills/orchestrator/SKILL.md` | `$ARGUMENTS` 解析新增 `--tone={neutral,casual,opinionated}`；非法值报错退出（与 `--quick` 同处理）；有效值传给 requirements |
| `skills/requirements/SKILL.md` | 新步骤 "tone 解析"：cli 优先 → frontmatter 读 → style 默认。最终值写入 article.md frontmatter `tone:`。**v1 不 AskUserQuestion**：因为 writing-style 永远会被 requirements 决定，`STYLE_TO_TONE_DEFAULT` 一定能给出值，三方俱缺分支不可达。仅当用户主动改 frontmatter 把 `tone:` 设成非法值时打印一次警告，降级 neutral |
| `skills/write/SKILL.md` | Step 3 prompt 构建时读 frontmatter `tone:`，把 `style-guide.md` 中对应 `## Tone: <tier>` 章节注入 prompt |
| `skills/write/style-guide.md` | 新增三个章节：`## Tone: neutral` / `## Tone: casual` / `## Tone: opinionated`，每节含替换映射、第一人称示范、强观点示范、收尾示范、对照原料段 |
| `skills/review/SKILL.md` | Phase 1 调用 `review_selfcheck.py` 时透传 tone（或 selfcheck 自己读 frontmatter） |
| `skills/lint/SKILL.md` | Step 4 调用 lint_article.py 时透传 tone；补充 inline 豁免语法说明 |
| `references/self-check-rules.md` | 加 `## Rule 17: Register Naturalness (tone-aware)`，完整阈值表 + 检测逻辑 + 三档对照例 |
| `commands/article-craft.md` | 文档化 `--tone` flag |

### 4.4 严禁措辞

`SKILL.md` / `references/` / 用户文档中**严禁**出现：
- "AI detection bypass" / "通过检测"
- "anti-detection" / "evade GPTZero"
- "humanizer" 中的 detection-evasion 含义

定位为 "register / voice quality"。这是调研角度 5 的强烈建议（避免与 GitHub humanizer topic 的 SEO 污染混淆）。

## 5. Rule 17 检测细节

### 5.1 输入处理

```python
def check_rule_17(content: str, lines: List[str],
                  frontmatter: Dict, writing_style: str) -> CheckResult:
    tone = resolve_tone(
        cli_tone=None,
        frontmatter_tone=frontmatter.get("tone"),
        writing_style=writing_style
    )
    body = strip_frontmatter(content)
    body = strip_code_blocks(body)              # 代码块不参与统计
    body = strip_callout_blocks(body)           # Obsidian callout 跳过
    body = strip_image_lines(body)              # 图片行不算"段"

    word_count_cn = len(re.findall(r"[一-鿿]", body))
    if word_count_cn < 200:
        return CheckResult.skip(reason="样本太小，密度抖动失真")
    ...
```

### 5.2 子检查 A：第一人称密度

```python
PERSONAL_VOICE_REGEX = re.compile(
    r"我(?:在|曾|的|会|用|选|踩|测|觉得|发现|猜|赌|最后)"
    r"|踩坑|实测|我的(?:经验|理解|做法)"
    r"|生产环境.*(?:我|本人)"
)
density = len(PERSONAL_VOICE_REGEX.findall(body)) / word_count_cn * 800
threshold = TONE_THRESHOLDS[tone]["first_person_per_800w"]
if density < threshold:
    violations.append(Violation(
        line=0,
        text=f"第一人称密度: {density:.1f} 处/800字",
        suggestion=f"tone={tone} 要求 ≥{threshold} 处/800字, 补充第一人称经验/选型理由/踩坑记录",
        severity="warning"
    ))
```

### 5.3 子检查 B：强观点存在性（opinionated 强制，casual 软建议，neutral skip）

```python
STRONG_OPINION_PATTERNS = [
    r"我赌",
    r"我觉得.*(?:就是|根本|纯属|没必要)",
    r"(?:这|那)(?:玩意|破事|设计).*(?:错|烂|拉胯|蠢|坑爹)",
    r"别(?:学|用|碰|信)",
    r"真(?:香|的香)",
    r"纯(?:纯|属)",
    r"我的判断是",
    r"敢断言",
]
opinion_count = sum(len(re.findall(p, body)) for p in STRONG_OPINION_PATTERNS)
required = TONE_THRESHOLDS[tone]["strong_opinion_min"]
if opinion_count < required:
    severity = "error" if tone == "opinionated" else "info"
    violations.append(Violation(
        line=0,
        text=f"强观点 sentence 数: {opinion_count} (需要 {required})",
        suggestion=("tone=opinionated 要求至少 1 处明确个人立场。" if tone == "opinionated"
                    else "考虑加 1 处个人判断/预测，提升可读性"),
        severity=severity
    ))
```

### 5.4 子检查 C：Summary phrase 上限

```python
# 复用 Rule 5 的 EMPTY_JUDGEMENT_PHRASES + SUMMARY_TONE_PHRASES
summary_hits = sum(len(re.findall(p, body)) for p in EMPTY_JUDGEMENT_PHRASES + SUMMARY_TONE_PHRASES)
limit = TONE_THRESHOLDS[tone]["max_summary_phrases"]
if summary_hits > limit:
    violations.append(Violation(
        line=0,
        text=f"总结腔短语命中: {summary_hits} (上限 {limit})",
        suggestion=f"tone={tone} 上限 {limit}, 删 {summary_hits - limit} 处或换具体陈述",
        severity="warning"
    ))
```

> **避免与 Rule 5 重复扣分**：Rule 5 看的是结构维度（连续段、邻段同类段首），Rule 17 子检查 C 只看总数，跟 Rule 5 维度正交。两条都触发是允许的，但报告里给同一条原文 line 号。

### 5.5 子检查 D：句长变异系数（仅 casual / opinionated）

```python
sentences = re.split(r"[。！？\n]", body)
lens = [len(s) for s in sentences if 5 <= len(s) <= 200]
if len(lens) < 10:
    return  # 样本不够 skip 子检查 D

import statistics
mean = statistics.mean(lens)
stdev = statistics.stdev(lens)
cv = stdev / mean if mean > 0 else 0
threshold = TONE_THRESHOLDS[tone]["sentence_len_variance_min"]
if threshold > 0 and cv < threshold:
    violations.append(Violation(
        line=0,
        text=f"句长变异系数: {cv:.2f} (需要 ≥{threshold})",
        suggestion="句子长度过于均匀（AI 节奏特征）。拆 1-2 句长句为短句, 或合并连续短句为长句",
        severity="warning"
    ))
```

### 5.6 阈值表（v1 起跑值，前 20 篇文章后再调）

| 指标 | neutral | casual | opinionated |
|------|---------|--------|-------------|
| `first_person_per_800w` | 2 | 4 | 6 |
| `strong_opinion_min` | 0 | 0 | 1 |
| `max_summary_phrases` | 5 | 2 | 0 |
| `sentence_len_variance_min` | 0 (skip) | 0.30 | 0.45 |

阈值在 `scripts/config.py` 中以 dict 暴露，**不在 review_selfcheck.py 硬编码**。校准期间改 config 即可。

### 5.7 输出格式

```
Rule 17: Register Naturalness (tone=casual) — FAIL
  ⚠️  warning: 第一人称密度: 1.8 处/800字 (需要 ≥4)
       建议: tone=casual 要求 ≥4 处/800字, 补充第一人称经验/选型理由/踩坑记录
  ⚠️  warning: 总结腔短语命中: 5 (上限 2)
       建议: tone=casual 上限 2, 删 3 处或换具体陈述
  ✓  强观点: 0 处 (软建议, casual 不强制)
  ✓  句长变异系数: 0.34 (>= 0.30 ✓)
```

`PASS` 条件：所有子检查无 `error` 级 violation。`warning` 不阻断 review，但计入 7 维评分扣分（"AI 痕迹"维度）。

### 5.8 与现有规则的协作

| 规则 | 责任边界 |
|------|----------|
| Rule 1 | 定义级红旗词 — 一刀切删 |
| Rule 5 | 段间结构 / 锚点（连续无锚段、模板节奏、第一人称下限） |
| Rule 17 | tone-aware 量化指标（密度归一、变异系数、强观点存在性） |

Rule 5 现有的 `personal_markers < 2` 软检查在 Rule 17 上线后**改为只在 tone=neutral 时生效**。Rule 17 在 casual / opinionated 时接管该维度。

## 6. Lint 三档 fix 集 + 严重度 + 振荡保护

### 6.1 数据结构

```python
TONE_LEXICAL_REWRITES: Dict[str, List[Tuple[Pattern, str, str]]] = {
    "neutral": [
        (re.compile(r"赋能"),       "支持",     "warning"),
        (re.compile(r"一站式"),     "完整",     "warning"),
        (re.compile(r"链路"),       "流程",     "info"),
        (re.compile(r"底层逻辑"),   "原理",     "info"),
        # ... 现有 RED_FLAG_REWRITES 全量
    ],
    "casual": [
        # 继承 neutral
        (re.compile(r"在某种意义上[，,]?"),     "其实",       "warning"),
        (re.compile(r"可以看到[，,]?"),         "能看出",     "warning"),
        (re.compile(r"本质上[，,]?"),           "说穿了",     "warning"),
        (re.compile(r"接下来我们[来]?(看|介绍|分析)"), "看看这个", "warning"),
        (re.compile(r"下面分别(来看|介绍)"),    "分别说",     "warning"),
        (re.compile(r"值得注意的是[，,]?"),     "这地方注意", "warning"),
        (re.compile(r"不难发现"),               "能看出",     "warning"),
        (re.compile(r"基于以上分析"),           "由此",       "info"),
    ],
    "opinionated": [
        # 继承 casual
        (re.compile(r"显然[，,]?"),             "明摆着",     "warning"),
        (re.compile(r"综上所述"),               "说白了",     "error"),
        (re.compile(r"总而言之"),               "一句话",     "error"),
        (re.compile(r"希望本文对你有帮助[^\n]*"), "",           "error"),
        (re.compile(r"如果这篇文章对你有帮助[^\n]*"), "",       "error"),
    ],
}
```

继承通过 `get_rewrites_for_tone(tone)` 函数实现：opinionated 返回 neutral + casual + opinionated 三档拼接。

### 6.2 严重度三档语义

- `info` — 报告中列出，**默认不改文件**；`--apply-info` 才动
- `warning` — `--fix` 默认改文件
- `error` — `--fix` 必改；即使没传 `--fix`，**退出码非 0**

### 6.3 CLI 接口

```bash
python3 scripts/lint_article.py \
    --article /path/article.md \
    [--tone {neutral,casual,opinionated}]   # 默认从 frontmatter 读
    [--fix]                                 # 应用 warning+error 替换
    [--apply-info]                          # 也应用 info 级
    [--min-severity {info,warning,error}]   # 报告过滤，默认 warning
    [--max-passes N]                        # 默认 3，振荡保护
    [--report-only]                         # 等价 --min-severity info 不改文件
```

### 6.4 内联豁免语法

```markdown
正常段落，"赋能"会被替换。

<!-- lint:disable rule5 rule17 -->
引用别人的话："这个产品赋能了千万开发者"。
<!-- lint:enable rule5 rule17 -->

正常段落继续。
```

实现：扫描时维护 `disabled_rules: Set[str]` 状态机；`disable` 入栈，`enable` 出栈；区块中字符不参与 fix 也不进 report；末尾未配对 `enable` → 警告但不报错。特殊符号 `all` — `<!-- lint:disable all -->` 屏蔽所有规则。

### 6.5 Max-pass 振荡保护

```python
def auto_fix(article_path: Path, tone: str, max_passes: int = 3) -> FixReport:
    last_violations: Optional[frozenset] = None
    for pass_num in range(max_passes):
        violations = scan_violations(article_path, tone)
        if not violations:
            return FixReport(passes=pass_num, status="clean")

        # signature: (rule_id, before_text, after_text) — 不用 line（fix 后会漂移）
        current_sig = frozenset(v.signature() for v in violations)
        if last_violations == current_sig:
            return FixReport(passes=pass_num, status="oscillating",
                             stuck_violations=violations)
        last_violations = current_sig

        apply_fixes(article_path, violations, tone)

    final_violations = scan_violations(article_path, tone)
    if final_violations:
        return FixReport(passes=max_passes, status="incomplete", remaining=final_violations)
    return FixReport(passes=max_passes, status="clean")
```

### 6.6 Lint 输出格式

```
============================================================
Lint Report — article.md (tone=casual, passes=2)
============================================================

✏️  Pass 1: 12 fixes applied
✏️  Pass 2: 3 fixes applied
✓  Pass 3: 0 violations — clean

[Applied — warning]
  L 47  '在某种意义上' → '其实'                              casual: r1
  L 89  '可以看到'     → '能看出'                            casual: r2
  L 124 '赋能'         → '支持'                              neutral: r-redflag-1

[Applied — error]
  L 312 '希望本文对你有帮助' → ''                            opinionated: r-closing-1

[Reported — info (not applied; pass --apply-info)]
  L 67  '基于以上分析' → '由此'                              casual: r-info-1

[High-Risk Sections (manual review)]
  ## 实战部分:  连续 3 段缺少具体锚点 (Rule 17 子检查 A 触发)
  ## 总览:      连续 2 段总结腔且密度 5 (上限 2)

Exit code: 0 (clean) | 1 (errors remain) | 2 (oscillating)
```

### 6.7 与现有 lint_article.py 的迁移

现有代码 (commit 38708f2)：
- `RED_FLAG_REWRITES` → 拆入 `TONE_LEXICAL_REWRITES["neutral"]`
- `OPENING_FILLERS`（在某种意义上 / 本质上 / 从这个角度看 / 某种意义上 / 回到问题本身）→ 全部进 `casual`
- `PARAGRAPH_STARTERS`（首先 / 其次 / 最后 / 另外 / 此外 / 同时）→ 移至 `casual`，**neutral 不删**
- `ROADMAP_LINE_PATTERNS` → 进 `casual` + `opinionated`
- `FORBIDDEN_CLOSING_PATTERNS` → 全部进 `opinionated` 的 `error` 级

迁移做成**纯重构**（行为等价 if tone=neutral）。但行为变更（neutral 不再无条件删段首副词）需在 CHANGELOG BREAKING 标注。

## 7. 测试策略

### 7.1 单元测试矩阵

| 文件 | 测试数 | 覆盖维度 |
|------|--------|----------|
| `tests/test_tone_resolution.py` | 8 | flag > frontmatter > style-default 三阶；非法 cli 报错；frontmatter 缺失 / 空 / 损坏 YAML 三种降级；style 默认表完整 |
| `tests/test_review_rule17.py` | 12 | 4 子检查 × 3 tone = 12 case；样本 < 200 字 skip；frontmatter 缺失走 style 默认；强观点正则不误伤代码注释；句长方差仅 ≥ 10 句时计算 |
| `tests/test_lint_tone_aware.py` | 14 | 三档 fix 差异；severity 过滤；`--fix` 不动 info；`--apply-info` 动；inline disable 区块跳过；区块字符不进 report；未配对 enable 警告；max-pass 收敛；振荡 signature；max-pass 用尽 incomplete |
| `tests/test_review_selfcheck.py` | +3 regression | tone 缺失时 Rule 5 行为不变；neutral 时 Rule 17 不触发强观点子检查；Rule 17 + Rule 5 同时触发不重复扣分 |
| `tests/test_lint_article.py` | +2 regression | 现有 10 用例在 `tone=neutral` 完全保留；`tone:` 缺失走 neutral 默认 |

### 7.2 集成 fixture

```
tests/fixtures/tone/
├── neutral_uv_intro.md
├── casual_kimi_k2_review.md
└── opinionated_pip_should_die.md
```

3 个 golden test：
- `test_neutral_article_passes_under_neutral_tone` — 防 false negative
- `test_casual_article_fails_under_neutral_tone` — 防 false positive（tone 不严不挑剔）
- `test_neutral_article_warns_under_opinionated_tone` — tone 严时该报

### 7.3 性能基线

```python
def test_rule17_completes_under_500ms_on_5000char_article(self):
    long_article = "。".join(["示例句"] * 1000)
    start = time.time()
    check_rule_17(long_article, ..., tone="opinionated")
    self.assertLess(time.time() - start, 0.5)
```

### 7.4 校准数据采集（v1 上线后用，v2 调阈值）

`scripts/review_selfcheck.py` Rule 17 触发时写记录到 `~/.cache/article-craft/tone-calibration.jsonl`：

```jsonl
{"ts":"...","article":"<sha256>","writing_style":"D","tone_resolved":"casual","metrics":{"first_person_per_800w":3.2,"strong_opinion_count":1,"summary_phrase_hits":3,"sentence_len_cv":0.41},"violations":[...],"final_pass":false}
```

收集 **本机用户跑 review 的 20 篇文章**（不区分通过/失败，按 `ts` 顺序取前 20 条）后人工分析分布，重设 `TONE_THRESHOLDS`。文件 SHA256 不存原文。默认开启，可通过 `~/.claude/env.json` 的 `tone_calibration: false` 关掉。

### 7.5 回归保护清单（v1.4.18 发布前）

- [ ] 现有 43 个测试全绿
- [ ] 新增约 39 个测试全绿（8 + 12 + 14 + 5 regression）
- [ ] 3 个 golden fixture 集成测试通过
- [ ] 性能 < 500ms baseline 通过
- [ ] 跑一遍存量历史文章（取 5 篇）走 review，确保 tone 字段缺失不爆错
- [ ] `--upgrade` 模式在 v1.4.17 文章上能识别"需要补 tone"且不重写其他阶段

## 8. 文档同步

- `CHANGELOG.md` `[Unreleased]` 加 entry
- `CLAUDE.md` § Tone System 新章节，3-5 行说明三档语义 + frontmatter 字段
- `references/self-check-rules.md` 加 Rule 17 + 阈值表
- `skills/write/style-guide.md` 加三档示范段
- `commands/article-craft.md` `--tone` flag 说明
- **不写** "AI detection bypass" 措辞

## 9. 关键不变量

1. 现有 16 条 rule 行为不变，`tone:` 缺失时所有阈值走 `neutral` 默认 — 旧文章 `--upgrade` 不会因为加了 Rule 17 突然全 fail
2. `lint_article.py` 默认 `--min-severity warning` — `info` 级建议不改文件，只报告
3. `--tone` 只对 article-level 生效，不影响系列其他文章（series 模式各篇独立解析）
4. 现有 `lint_article.py --fix` 在 tone=neutral 下行为收紧（不再无条件删段首副词），是 BREAKING change，CHANGELOG 标注

## 10. v2 候选（明确不进 v1）

- Per-section tone 覆盖语法 (`<!-- tone:casual -->...<!-- /tone -->`)
- Voice calibration（用户指 3 篇过去文章，提取惯用语风格）— 借 blader/humanizer 的设计
- 经验数据驱动阈值再校准（前 20 篇收集后改 `TONE_THRESHOLDS`）— 自动化或半自动化
- Per-section tone 检测（同一篇不同 section 不同 tone 的可行性）

## 10b. 推荐实施分批（写 plan 时参考）

整篇 spec 是单一设计单元。但实施时建议分两个 PR 着陆，降低单 PR 评审难度：

- **PR A — 数据层与 resolver**：`scripts/config.py` 三个常量 + `resolve_tone` + `tests/test_tone_resolution.py` 8 个测试。落地后整库行为完全不变（没人调它）。
- **PR B — 三层串起来**：requirements / write / review / lint skill 改动 + Rule 17 + lint tone-aware + 剩余测试 + 3 个 fixture。这个 PR 才会改变用户可见行为，CHANGELOG 在这里加 BREAKING 标注。

writing-plans skill 据此拆任务。

## 11. 未决问题（实现期再定）

1. **中英混排文章的密度归一**：第一人称密度按 `[一-鿿]` 字数归一。如果文章里大段英文（引用文档），这部分不算"中文字数"，是否会让密度统计偏高？v1 初版按现状走，集成测试观察。
2. **代码注释的 fix**：lint 现在跳过代码块。但代码注释里 "这玩意又坑了" 这种吐槽是 opinionated 鼓励的。是否要把代码注释纳入第一人称密度统计？v1 不纳入（保持 lint 简单）。
3. ~~**`requirements` skill 的交互**~~：已在 §4.3 明确——v1 不弹问题，writing-style 永远存在故 style 默认表必能解析。

## 12. 参考文献

- [blader/humanizer (GitHub)](https://github.com/blader/humanizer) — 29 patterns × 4 categories，two-pass audit 模式
- [hylarucoder/ai-flavor-remover (GitHub)](https://github.com/hylarucoder/ai-flavor-remover) — 中文 AI 味移除 prompt
- [Vale: Your style, our editor](https://vale.sh/) — severity tiers + style packs + inline overrides 架构借鉴
- [GPTZero — Perplexity & Burstiness](https://gptzero.me/news/perplexity-and-burstiness-what-is-it/) — 句长方差作为 AI 信号
- [Binoculars (arXiv 2401.12070)](https://arxiv.org/html/2401.12070v3) — sentence-length variance 学术验证
- [知乎 — 8 个去机器味技巧](https://zhuanlan.zhihu.com/p/692546989) — 中文替换词表
