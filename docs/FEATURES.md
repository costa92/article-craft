# article-craft 功能说明

> 版本：**v1.9.0** ｜ 本文档基于当前源码实测整理，覆盖全部技能、脚本、工作流与质量体系。

---

## 1. 这是什么

`article-craft` 是一个 **Claude Code 插件**（不是独立运行的服务），为「技术文章生成全生命周期」提供 **13 个可组合技能 + 1 个编排器**。

- 仓库即源码，通过 `install.sh` 或 Claude Code 插件市场安装到 `~/.claude/plugins/article-craft/`。
- **prompt-first 工程**：大部分「逻辑」写在 `.md` 文件里由 Claude 读取并执行；`scripts/*.py` 只承担 prompt 做不可靠的确定性工作（Playwright 截图、图像生成、压缩、CDN 上传、缓存等）。
- **真实交付目标是微信公众号**：默认正文形态为 `wechat-native`（移动端公众号体），其余平台为可选输出。

### 两种代码

| 类型 | 位置 | 作用 |
|---|---|---|
| 行为定义（prompt） | `skills/*/SKILL.md`、`commands/*.md` | 改这里就改变流水线行为 |
| 确定性辅助脚本 | `scripts/*.py` | 截图 / 图像生成 / 压缩 / 上传 / 自检 / 状态 |

> 路径约定：markdown/shell 一律用 `${CLAUDE_PLUGIN_ROOT}`，JS 用 `process.env.CLAUDE_PLUGIN_ROOT`，Python 从 env/argv 读取。**禁止**硬编码 `~/.claude/plugins/article-craft/`。

---

## 2. 核心架构：编排器模式

一切从 `skills/orchestrator/SKILL.md` 出发，串起主流水线：

```
requirements → verify → [evidence(仅Style H)] → write → screenshot → (share_card?) → images → verify-claims → review → publish
```

- 每个技能也可独立调用：`/article-craft:<skill-name>`。
- 斜杠命令 `/article-craft <参数>` 只是让 Claude 读取并执行编排器 SKILL.md，把 `$ARGUMENTS` 透传进去。
- **两个验证阶段（易混淆，务必区分）**：
  - `verify`（写作**前**）：核验**信息源**——URL 可达性、T0–T5 信任分层（本质是 source-vet，目录名保留是为命令兼容）。
  - `verify-claims`（图像后、review 前）：核验**正文本体**——扫描正文里的 shell 代码块，检查每个工具名是否在 PATH 上（`scripts/verify_claims.py`）。

---

## 3. 工作流模式

通过参数切换跑哪些阶段：

| 模式 | 触发 | 流程 | 用途 |
|---|---|---|---|
| **standard**（默认） | 无 flag | requirements → verify → [evidence] → write → screenshot → (share_card?) → images → verify-claims → review → publish | 带质量门的完整文章 |
| **quick** | `--quick` | requirements → [evidence] → write → screenshot → images | 快速产出，跳过两个验证阶段 + review + publish |
| **draft** | `--draft` | requirements → [evidence] → write | 只要正文，无图、无 review |
| **series** | `--series FILE` | 读 series.md → requirements（预填）→ standard | 写系列的下一篇 |
| **upgrade** | `--upgrade PATH` | 探测已有状态 → 只跑缺失阶段 | 把草稿/quick 文章补全为完整输出 |

> **Style H 特例**：当 requirements 判定为 Style H（爆料自媒体）时，`evidence` 技能**必跑**（在 write 之前），任何模式都不可跳过；evidence 失败或 materials.md 缺失 → 流水线 BLOCK。

参数透传 flag：
- `--tone={neutral,casual,opinionated}` — 语气强度，非法值直接报错不静默降级。
- `--body-form={wechat-native,long-form}`（或简写 `--long-form`）— 正文形态。
- `--upgrade PATH` / `--series FILE`。

编排器在运行任何技能前会做 **preflight**（依赖预检），缺 `MINIMAX_API_KEY` 等会 fail-fast 并指明缺失项；`--draft` 模式跳过预检。

---

## 4. 技能详解（按流水线顺序）

| # | 技能 | 命令 | 职责 |
|---|---|---|---|
| 1 | **requirements** | `/article-craft:requirements` | 意图推断、主题分析、歧义消解、信任源检测（输出 `_trusted_sources` T0–T5）；产出 `body_form`/`tone`/写作风格到 frontmatter |
| 2 | **verify** | `/article-craft:verify` | 批量核验链接/命令/工具特性，按 T0–T5 信任分层聚焦验证；写 `verify-cache.json`；可 WebFetch 官方源 |
| - | **evidence** | `/article-craft:evidence` | 仅 Style H：解析 `materials.md`，批量采集公开源证据（图片/引文/泄露引用），输出 `_evidence.json` 供 write 消费 |
| 3 | **write** | `/article-craft:write` | 按 style-guide 生成正文，自动校验章节深度、强制代码完整性，注入 tone/body_form 段落；预存写门（write GATE） |
| 4 | **screenshot** | `/article-craft:screenshot` | Playwright 真实浏览器渲染网页截图，HEAD 预检、智能选择器（GitHub/Twitter/SO 等）、404/空页检测、尺寸优化、CDN 上传 |
| - | **share-card** | `/article-craft:share-card` | 可选：从 frontmatter 生成社交分享卡（封面/信息流/帖图），**11 个平台预设（9 平台 + 2 别名）+ 7 套配色** |
| 5 | **images** | `/article-craft:images` | 处理正文 `<!-- IMAGE: -->`/`<!-- PROMPT: -->` 占位符，**Minimax 优先、Gemini 兜底**，Pillow 压缩、PicGo/S3 上传，原地改写文章 |
| 6 | **verify-claims** | `/article-craft:verify-claims` | 扫描正文 shell 代码块，逐个检查工具是否在 PATH 上（写作后的事实校验） |
| 7 | **review** | `/article-craft:review` | 质量门：Phase 1 自检 23 条规则 + Phase 2 八维评分（阈值 63/80），无外部依赖 |
| 8 | **publish** | `/article-craft:publish` | 自动归档到知识库（智能目录匹配）、分发优化、微信发布前 checklist |

辅助/独立技能：

| 技能 | 命令 | 职责 |
|---|---|---|
| **lint** | `/article-craft:lint` | 用规范自检规则检查并自动修复风格违规（review 前清理）；Vale 风格 severity + `<!-- lint:disable -->` 内联区 |
| **series** | `/article-craft:series` | 系列规划/管理/生成/审计：共享风格、自动导航、进度追踪、知识覆盖分析 |
| **youtube** | `/article-craft:youtube` | YouTube 视频转文章：提取字幕、分析内容、生成文章（默认走 Style B） |

非技能命令（编排器模式/脚本封装的快捷入口）：

| 命令 | 说明 |
|---|---|
| `/article-craft:upgrade PATH` | `--upgrade` 模式快捷入口（无对应 skill 目录） |
| `/article-craft:doctor [--json]` | 运行时健康检查，封装 `scripts/doctor.py`（依赖预检） |

---

## 5. 三条正交轴

文章由三条**互相独立**的轴定义，可自由组合：

### 5.1 写作风格（内容身份，Style A–H）

write 根据内容信号自动选择，也可手动指定（规则见 `references/writing-styles.md`）：

| 风格 | 类型 | 触发信号示例 |
|---|---|---|
| A | 技术教程 | 教程/指南/入门/实战/部署 |
| B | 经验分享/口语化（截图密集型） | 分享/推荐/技巧/隐藏/「N个」 |
| C | 深度长文 | 原理/源码/架构/设计/底层 |
| D | 评测对比 | 对比/评测/vs/选型/哪个好 |
| E | 资讯快报 | 更新/发布/新版本/changelog |
| F | 项目复盘 / Case Study | 复盘/踩坑/迁移/优化了/从X到Y |
| G | 观点输出 / 思考 | 为什么/我认为/不推荐/应该 |
| H | AI 资讯爆料 / 自媒体爆款 | 曝光/爆料/泄露/一夜/刚刚/硬刚/股价 |

> YouTube 转文章默认归为 Style B。

### 5.2 语气强度（tone，v1.4.18）

三档：`neutral` / `casual` / `opinionated`。整条流水线通过 frontmatter 字段传递。

- 解析优先级：`--tone` CLI > frontmatter `tone:` > `STYLE_TO_TONE_DEFAULT`（`scripts/config.py`）。
- Rule 17 跑四个 tier-aware 子检查；`scripts/lint_article.py` 用 `TONE_LEXICAL_REWRITES`（Vale severity + 3-pass 防震荡）。
- 校准数据：`~/.cache/article-craft/tone-calibration.jsonl`（`ARTICLE_CRAFT_TONE_CALIBRATION=false` 关闭）。
- 规格：`docs/superpowers/specs/2026-05-07-tone-system-design.md`。

### 5.3 正文形态（body_form，v1.8.0）

与 tone 并列的第二条轴，决定**正文形态**而非内容身份：

| 取值 | 形态 |
|---|---|
| `wechat-native`（默认） | 移动端公众号体：短段落、无 Obsidian callout、标题 ≤ `##`/`###`、图片节奏、单一主线 |
| `long-form`（仅显式开启） | 博客体：允许 callout、深章节，知识库/博客归档副本 |

- 解析优先级（镜像 tone）：`--body-form` CLI > frontmatter `body_form:` > 旧字段 `wechat_target: false` 别名 > 默认 `wechat-native`。规范解析器 `config.resolve_body_form()`。
- `wechat-native` 下 `check_rule_6` 章节阈值 -1；review 在 Phase 2 加一个**软**形态一致性信号（不新增 write 门——augmentation > gating）。
- 默认永远 `wechat-native`，`long-form` 绝不从深度/教程关键词自动推断。
- 规格：`docs/superpowers/specs/2026-05-29-wechat-native-body-form-design.md`。

---

## 6. 质量体系

### 6.1 23 条自检规则

`scripts/review_selfcheck.py` 内含 `check_rule_1`…`check_rule_24`（最高 ID 24，Rule 21 保留 → **当前 23 条生效**）。完整说明见 `references/self-check-rules.md`。

代表性规则：

- Rule 1 红旗词、Rule 2 钩子长度、Rule 3 结尾段、Rule 4 标签（≥3 个中文标签强制）
- Rule 5 反 AI 结构、Rule 6 章节深度、Rule 7/7b 图片去重 + 最小 AI 图数
- Rule 11 占位符残留（review 阶段 CRITICAL）、Rule 13 代码块语言标识、Rule 14 非可执行代码块里的 ASCII 图
- Rule 16 PROMPT 文字渲染风险（Gemini 渲染不了中文）、Rule 17 语气自然度（tone-aware）
- **WeChat 系列（v1.7.x）**：Rule 18–24（除 21 保留）——合规 + 触达机制 + LLM 系统性失败模式（Rule 23 反推荐黑名单、Rule 24 虚构数字检测）

### 6.2 写门（write GATE）

write 在保存前只跑子集 `WRITE_GATE_RULES = (1, 2, 6, 13, 14, 16)`：

- Rule 11（占位符残留）**不在**写门内——图像前占位符是预期存在的。
- Rule 14（代码块内 ASCII）是图像前的门。
- **不要**从编排器单独运行 `review_selfcheck.py`，由 review 技能内部调用。

### 6.3 review 两阶段

- **Phase 1**：23 条规则自检。
- **Phase 2**：八维评分，阈值 **63/80**。**自 v1.4.4 起仅诊断，无自动改写循环**。低于阈值时弹 AskUserQuestion（照发 / 中止 / 带提示重跑 write），每次修订都是用户显式决策；编排器把「带提示重跑」上限设为 2 次。

> 设计哲学贯穿全局：**augmentation > gating**（增强提示上下文，而非加更多硬门），以避免高误报率逼出写作循环。

---

## 7. 图像系统

### 7.1 图像 provider（`scripts/image_providers.py`）

`ImageProvider` Protocol + 注册表，按 `config.MODEL_FALLBACK_CHAIN` 兜底：

- **MinimaxProvider**（主力）：`minimax-image-01`
- **GeminiProvider**（兜底）：`gemini-3-pro-image-preview` / `gemini-3.1-flash-image-preview` / `gemini-2.5-flash-image`
- **OpenAI gpt-image-1**（v1.6.20）
- **自建 Stable Diffusion**（v1.6.22）

并行图像路径有 worker 协调的退避（`_ParallelRateLimitCoordinator`），任一 worker 触发限流即设共享暂停窗口。

### 7.2 视觉风格预设 S1–S8

`generate_and_upload_images.py` 的 `VISUAL_STYLE_PRESETS` 按内容关键词路由视觉风格。`vary_prompt_for_position()` 自动注入 **8 个轴**（Camera / Composition / Visual treatment / Palette / Material / Lighting / Scale / **Background**，第 8 轴 Background 在 v1.7.6 D1 修复后才生效）。

- **S8 AI 教程封面风**（v1.7.6）：黑底科技网格 + 悬浮白卡 + 高对比黑白 + cyan 强调，16 个 trigger 词（transformer/llm/rag/ai agent…）。封面零容忍假文字，建议用 `gemini-2.5-flash-image`。

### 7.3 share-card（社交分享卡）

`scripts/share_card.py`：`PLATFORMS` 含 11 个预设 key——9 个平台（wechat-cover、wechat-share、xiaohongshu、xiaohongshu-sq、twitter、linkedin、facebook、juejin、zhihu）+ 2 个别名（wechat-share-square、twitter-card）；`COLOR_PRESETS` 7 套配色（默认 `tech-blue`）。`wechat-double` 自动生成头条 + 分享两张。

---

## 8. WeChat 公众号适配（v1.7.x）

基于 **4 篇实际发布文章** dogfood——发现 8 条自检规则在真实公众号发文上 100% 失败。v1.7.x 五个增量发布各打一个失败模式：

| 发布 | 新增 | 针对 |
|---|---|---|
| v1.7.0 | Rule 18–22 + CTA + 双封面 | 微信合规 + 基础钩子 |
| v1.7.1 | Rule 23 + publish step 3.5 checklist | 反推荐黑名单 + 6 项人工 checklist |
| v1.7.2 | Rule 24 + Rule 23 bugfix | LLM 虚构数字 + `strip_code_blocks` 回归 |
| v1.7.3 | Style G + opinionated 加强模板 | 4 个填空表（个人经历/主观判断/强观点/具体锚点） |
| v1.7.4 | Rule 4 标签强制（write + publish） | ≥3 个中文标签的纵深防御 |

- 所有规则可追溯到 A 级官方源（cac.gov.cn / openstd.samr.gov.cn / mp.weixin.qq.com / developers.weixin.qq.com 运营专员）或 B 级（主流媒体引微信珊瑚安全/微信团队）。证据链：`.research/official-sources-verification.md`、`.research/wechat-distribution-mechanism-2026.md`。
- **v1.8.4 attribution-as-voice**：来源归属（据/根据/官方/原文/「视频里说」）现在算作有效具体锚点，Rule 5 跳过 conclusion/intro 段——移除了「虚构反而通过、忠实归属反被罚」的反常激励。

---

## 9. 配置与脚本

### 9.1 配置

所有 API key、模型选择、S3、超时都在 `~/.claude/env.json`（见 `ENV.md`），模板 `env.example.json`。**不新增配置文件**，扩展 `scripts/config.py` 读新 key。

跨进程缓存路径必须经 `config.cache_dir()`（唯一尊重 `ARTICLE_CRAFT_CACHE_DIR`）；会话临时目录用 `tempfile.gettempdir()`。

### 9.2 关键脚本

| 脚本 | 作用 |
|---|---|
| `config.py` | 加载 env.json，定义 `MODEL_FALLBACK_CHAIN`、`TEXT_MODEL`、`cache_dir()`、tone/body_form 解析器 |
| `screenshot_tool.py` | Playwright 截图 + CDN 上传，读 verify-cache（TTL 1h） |
| `generate_and_upload_images.py` | 批量处理图像占位符（`--process-file` 标准入口） |
| `image_providers.py` / `nanobanana.py` | provider 协议 + 单图 Gemini 调用 |
| `share_card.py` | 社交分享卡生成 |
| `review_selfcheck.py` | 23 条规则自检（review 内部调用） |
| `lint_article.py` | Rule 5 机械修复 + tone 词汇重写 |
| `verify_claims.py` / `write_verify_cache.py` | 正文工具核验 / 写 verify 缓存 |
| `pipeline_state.py` / `series_state.py` / `publish_plan.py` | 流水线状态 / 系列状态 / 发布归档计划 |
| `utils.py` | `PlaceholderManager`（原地改写）+ `SmartDirectoryMatcher`（知识库自动归位） |
| `doctor.py` | 运行时健康检查 |
| `bump_version.py` | 同步 `plugin.json` + `marketplace.json` + 所有 `skills/*/SKILL.md` 版本 |

---

## 10. 跨技能数据流

技能间通过三种机制传状态：

1. **article.md 文件本身**：write 后捕获绝对路径，透传给后续每个技能；占位符（`<!-- IMAGE: -->`、`<!-- SCREENSHOT: -->`、`<!-- PROMPT: -->`）是契约，下游找到并替换。
2. **`~/.cache/article-craft/verify-cache.json`**：URL 状态缓存，verify 与 screenshot 共享（TTL 3600s）；原子写。
3. **编排器上下文**：requirements 输出 `_trusted_sources`（T0–T5），verify 用它跳过预信任链接，write 用它引用官方文档。

另有持久状态文件 **`.article-craft-state.json`**（与 article.md 同目录，`scripts/pipeline_state.py` 在每个阶段边界写）。`--upgrade` 优先读它，缺失才退回文本启发式（兼容 v1.4.2 前的文章）。文章内容仍是 ground truth——状态说 `images: completed` 但正文还有占位符则标 `stale` 重跑。

---

## 11. 命令速查

```bash
# 安装 / 重装
bash install.sh
pip3 install -r scripts/requirements.txt
shot-scraper install            # 或 playwright install chromium

# 全流水线（在 Claude Code 内）
/article-craft 写一篇关于 X 的技术文章
/article-craft --quick <topic>
/article-craft --draft <topic>
/article-craft --upgrade /abs/path/article.md
/article-craft --series /abs/path/series.md
/article-craft --tone=opinionated --body-form=long-form <topic>

# 独立技能
/article-craft:requirements  /article-craft:verify        /article-craft:evidence
/article-craft:write         /article-craft:screenshot    /article-craft:images
/article-craft:verify-claims /article-craft:review        /article-craft:publish
/article-craft:lint          /article-craft:series        /article-craft:youtube
/article-craft:share-card    /article-craft:upgrade /abs/path/article.md
/article-craft:doctor        # 或 --json

# 版本与脚本
python3 scripts/bump_version.py patch                       # major | minor | X.Y.Z
python3 scripts/generate_and_upload_images.py --process-file /abs/path/article.md
python3 scripts/share_card.py -f /abs/path/article.md -p wechat-cover,twitter,xiaohongshu-sq --upload
```

---

## 12. 参考文档索引

| 文档 | 内容 |
|---|---|
| `CLAUDE.md` | 架构与编辑约定（项目级指令） |
| `references/writing-styles.md` | 8 种写作风格 A–H |
| `references/self-check-rules.md` | 23 条自检规则细节 |
| `references/verification-checklist.md` | 验证清单 |
| `references/knowledge-base-rules.md` | 知识库归位规则 |
| `references/gemini-models.md` | Gemini 图像模型 |
| `ENV.md` / `env.example.json` | 配置项 |
| `docs/superpowers/specs/` | tone / body-form 设计规格 |
| `.research/` | 微信生态官方调研证据链 |

---

> `CHANGELOG.md` 已补齐至 v1.9.0（v1.7.8–v1.9.0 条目于本次维护根据 git 历史补录：body-form 正交轴、attribution-as-voice、诚实 AIGC 标签、Minimax-first 回归、若干 edge-case 修复与 CI auto-merge）。注意 v1.7.7/v1.7.8 没有对应 git tag（发布 commit 存在但未打 tag）。
