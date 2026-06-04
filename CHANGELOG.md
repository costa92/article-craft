# Changelog

## [1.9.6] - 2026-06-04 — 逻辑/关系图改用 S2 手绘信息图海报（替代等距透视）+ 英文标签例外

### Why

逻辑、关系、流程、框架类图先前默认走 S2 等距透视（isometric 2.5D 工程风），但这类图
的本质是"把关系讲清楚"——手绘信息图/知识地图（奶油纸 + 黑线描 + 卡通角色 + 箭头连线）
的可读性和亲和力更适配公众号读者。owner 决定：所有结构/逻辑/关系图统一改用手绘信息图
海报，彻底替代等距透视。

随之而来的矛盾：信息图的核心是**带标签**，而全局 Rule 16 硬禁止 PROMPT 渲染文字（图像
模型渲染中文不稳）。解决办法——S2 允许**英文短标签**（Input/Parser/Output 在所有模型上
都稳定渲染），但 CJK 对 S2 也照拦，强制 English-only，避免中文翻车。中文正文 + 英文图
标签是中文技术写作的常规搭配。

### Changed

- **S2 视觉风格：等距透视 → 手绘信息图海报**。`VISUAL_STYLE_PRESETS` 用
  `hand-drawn infographic poster` 替换 `isometric technical illustration`；
  `DESIGN_LOGIC_RULES` 的 "explain structure" 改向新 preset 并扩词（+`relationship`
  /`framework`/`mind map`/`concept map`/`knowledge map`/`logic`/`hierarchy`/`topology`
  /`structure`），所有结构/逻辑/关系图自动路由到手绘信息图海报。
- **Rule 16 新增 S2 英文标签例外**。带 S2 风格签名（`hand-drawn infographic poster`
  /`sketchnote`/`knowledge map`/`whiteboard doodle`）的 PROMPT 豁免"渲染英文文字"告警，
  可写 panel labels；**CJK 仍对 S2 硬拦**（English-only 强制执行）。
- `image-guide.md` S2 段、全局 Rule 5、`write/SKILL.md` 同步：英文短标签三条底线 + 全英文风格示例。
- `write/SKILL.md` 顺带修正过时计数 "7 种(S1-S7)" → "8 种(S1-S8)"。

### Tests

- `test_image_variation.py`：更新 architecture → 新 preset 契约，新增 relationship 路由用例。
- 新增 `test_rule_16_infographic_text.py`（5 测试）：S2 英文标签过 / S2 中文拦 / 非 S2 中文拦。

## [1.9.5] - 2026-06-02 — 根治代码块豁免 bug 类：统一到 canonical scanner + 跨规则守护

### Why

「红旗词/数字/裸链/模板词写在代码块里却照样被规则误报」这个 bug 连续三轮审核反复
出现（v1.9.2 Rule 1/12、v1.9.3 Rule 1、v1.9.4 Rule 23/24）。根因不是单条规则写错，
而是**「代码块在哪几行」在仓库里有三套互不等价的实现**——`strip_code_blocks` 正则、
手写 `startswith('```')` toggle、canonical `iter_code_blocks`——只有最后一套对 `~~~`
和变长/嵌套 fence 正确。每轮审计只把踩雷的一两条规则迁到 canonical，其余仍用错的两套，
于是 bug 在下一条没迁的规则上复发。这次消灭整个 bug 类，而不是再修一条。

### Fixed

- **`strip_code_blocks` 重写在 `iter_code_blocks` 之上** — 一次性修正所有正则调用点：
  `get_paragraphs`、Rule 8（裸 URL）、Rule 17（语气）、Rule 22（个人化）现在都对 `~~~`
  和嵌套 ```` 正确豁免。
- **`_split_blocks` / `check_rule_12`（模板化摘要）迁离手写 toggle** — 改用
  `_code_block_line_set`，认 `~~~` 与嵌套 fence。
- **`_is_structural_anchor_block` 识别 `~~~`** — 此前只认 ` ``` `，`~~~` 代码块不被当作
  结构锚点。

### Tests

- 新增**跨规则守护测试** `tests/test_code_block_exemption_guard.py`：把每条代码块敏感规则
  的触发串塞进 `~~~` 块和嵌套 ```` 块，跑全部规则断言零误报；另有 sanity 断言证明这些
  触发串在普通正文里确实会触发。任何规则（现在或将来）退回到非 fence-aware 的探测都会
  立刻让它变红——这是「避免再次出现」的防回归闸门。
- `python3 -m pytest tests/ -q` → **614 passed**（v1.9.4 为 611）。

## [1.9.4] - 2026-06-02 — 第三轮审核修复：SSRF 重定向链 + Rule 23/24 fence/边界 + KB 路径

### Why

借助多 agent 做第三轮审核（提示词/SKILL 一致性 / 设计架构 / Python 脚本正确性 /
测试覆盖），对抗式复核确认 P0 安全 2 条、规则 3 条、架构 1 条 + P1 文档漂移。全程
TDD：每条先写复现测试看它红 → 最小修复 → 验证绿 → 原子提交。

### Security

- **SSRF 守卫漏 IPv4-mapped IPv6** — `::ffff:169.254.169.254` 是 metadata 地址的 v6
  写法，双栈主机上能真实打到 metadata 端点却绕过 `is_link_local` 硬拦。分类前先
  unwrap `ipv4_mapped` 再判定。
- **SSRF 守卫只校验初始 URL，30x 可绕过** — 攻击者控制的页面能把干净公网域名
  301 到 169.254.169.254。新增 `_redirect_chain_safe`，在 HEAD 状态检查、GET rehost
  后复检 `response.history`+`response.url`，Playwright 导航后复检 `page.url`；harvest
  命中即中止（不走 baoyu-fetch 兜底），内网内容永不回传。

### Fixed

- **Rule 23/24 代码块豁免漏 `~~~`/嵌套 fence** — 手写 `startswith('```')` toggle 完全
  看不见 `~~~`，且把 ```` 块内的裸 ``` 当闭合，使文档化的反例/数字泄漏进违规扫描。
  改走 canonical `_code_block_line_set`（Rule 13/14/ascii_gate 同款）。4 空格缩进的
  ``` 按 CommonMark 不再闭合。
- **Rule 24 frontmatter 边界误吞正文** — 旧「前 20 行像 yaml 就跳过」既漏掉 20 行后的
  frontmatter，又把 `实测结果: 提升 50%` 这类正文行误跳（中文是 Unicode `\w`）。新增
  `frontmatter_end_line`（与 `get_body` 同源），严格按闭合 `---` 行号跳过。
- **Rule 24 两段 code-span 间的数字被误豁免** — `` `a` 50% `b` `` 里的 50% 被「最近一对
  backtick」启发式 + `HEDGE_PREFIXES` 的 `` `[^`]*\d[^`]*` `` 双重误豁免。改用 backtick
  奇偶判定（match 前为奇数才算在 span 内），并删除同 bug 的 hedge 模式。
- **`pipeline_state` 硬编码 `/02-技术/`** — fork 改 `kb_category_root`（env.json 文档化的
  覆盖项）后，每篇 KB 内文章都被 `--upgrade` 误判为不在 KB、白重跑 publish。改读
  `config.kb_category_root()`，带 `02-技术` 兜底（脱离插件布局时）。

### Docs

- 图像生成描述 Gemini → 多供应商（`MODEL_FALLBACK_CHAIN` Minimax-first，Gemini/OpenAI
  兜底，与实际一致）；`review_selfcheck.py` 头部「15 rules」→ 23（Rule 21 reserved）；
  规则数锚点 v1.8.4 → v1.9.3。核对 share_card 实为 11 = 9 + 2 别名，CLAUDE.md 原文正确未动。

### Tests

- 新增复现测试：SSRF 重定向链（HEAD/GET/Playwright 三处）、IPv4-mapped IPv6、Rule 23/24
  `~~~`/嵌套 fence、Rule 24 frontmatter 边界、双 code-span、自定义 KB 根。
- `python3 -m pytest tests/ -q` → **611 passed**（v1.9.3 为 600）。

## [1.9.3] - 2026-06-02 — 第二轮审核修复 + SSRF 加固（5+4 条）

### Why

对 v1.9.2 做了第二轮审核，换角度覆盖上轮没碰的面（回归核查 / 安全 / 容错并发 /
测试完整性）。对抗式复核确认 5 条 + 4 条低优先级，并发现上轮 Rule 1 修复的一处不
完整。575 测试全绿但盖不到这些更深的缺陷。

### Fixed

- **Rule 1（写入 GATE）代码块豁免漏 `~~~`/嵌套 fence** — v1.9.2 的 `in_code`
  toggle 只认 ` ``` `，红旗词写在 `~~~` 块或嵌套更长 fence 里仍触发 GATE。改走
  canonical `iter_code_blocks`（Rule 13/14/ascii_gate 同款），新增 `_code_block_line_set`
  共享辅助。
- **`lint_article` 三处 in-place 写非原子** — 唯一非原子的文章 mutator，中断会截断
  作者文章且无备份。新增 `_atomic_write`（mkstemp + os.replace），并用 dirty 标志跳过
  无改动时的空写。
- **`is_404_content` host 匹配** — 把 `_normalized_host` 重复计算合一，github/twitter/x
  统一走 `_host_matches`（修 v1.9.2 commit message 声称"全走 _host_matches"的遗漏）。

### Security

- **SSRF guard（`_is_fetchable_url`）** — verify/screenshot/harvest 此前对 URL 不做
  任何校验，`page.goto` 能渲染 `file://`、harvest `--rehost always` 时第三方页面的
  `<img src>` 能打内网/metadata。现硬拦非 http(s) scheme 与 link-local/metadata 地址
  （169.254/16、fe80::/10），对 localhost/RFC1918 放行仅告警（保留本地开发截图），
  接入 `check_url_status` / `rehost_image` / `harvest_images`。

### Tests

- 补三处绿但无守护的关键路径：`_is_stale` 正向 stale 检测（`--upgrade` 安全网）、
  `generate_image` 全模型耗尽分支（429→raise / 非限流→return False）、`upload_image`
  S3/PicGo 分发 + `upload_to_s3` 错误分支。
- 重写 Rule 17 的空测试（原仅 `assertIsNotNone`）为真正断言 skip 边界。
- 新增 5 个测试文件，4 个真 bug/防护走 TDD 先红后绿。
- `python3 -m pytest tests/ -q` → **600 passed**（v1.9.2 为 575）。

## [1.9.2] - 2026-06-02 — 深度审核修复（9+2 条）

### Why

对 v1.9.1 做了一次 4 维度深度审核（文档漂移 / 跨文件不变量 / 脚本逻辑 bug /
prompt 编排），对抗式复核确认 9 条问题成立、0 条证伪，外加 2 条低优先级。测试
全绿但盖不到这些「文档/编排/逻辑」层缺陷。

### Fixed

- **`check_rule_1`（写入 GATE）误拦代码块内红旗词** — 只跳过 fence 行、没跳过
  fence 之间的内容，导致 demo 输出 / 引用示例里的「赋能/闭环/抓手/底层逻辑」触发
  GATE 阻断保存。改用 Rule 23 同款 `code_lines` set 豁免。
- **`check_rule_12` 死变量**（`strip_code_blocks` 回归族）— 计算了
  `text=strip_code_blocks(body)` 却遍历完整 `lines`，代码块内模板词被误报。
- **截图 host 子串过度匹配** — `"x.com"` 把 vox/netflix/max/xbox.com 当成
  Twitter 套 tweet 选择器。改为域名边界匹配（`host==key or endswith('.'+key)`）。
- **pipeline-state 仅认含 "cdn" 的图片 URL** — S3 公开前缀 / endpoint URL 不含
  "cdn"，导致 `--upgrade` 无 state 文件时误判 images 未完成、白重跑。改为识别任意
  绝对 http(s) URL 图片。
- **orchestrator quick/draft 模式说明漏 `[evidence if Style H]`** — 与模式表 /
  Style-H 特例自相矛盾，Style-H 草稿会在 write 阶段致命阻断。
- **裸文件路径入口跳到 images** — 跳过 screenshot/HARVEST 展开，与「next
  unfinished stage」承诺矛盾。改走 `missing-stages` 检测。
- **§3.4 截图阶段未提 HARVEST** — HARVEST-only 文章被「无 SCREENSHOT 则静默跳过」
  漏掉，源图不展开后被 publish gate 阻断。现扫描两者。
- **wechat-native 下章节 callout 矛盾** — 默认禁用 callout，但各风格章节模板无条件
  要求 callout。补全局 body_form 作用域说明。
- **marketplace.json 技能数 "12" → "13"**（PR#6-8 计数审计遗漏处）。
- **tone-calibration 缓存绕过 `config.cache_dir()`**（low）— `~` 前缀不展开，落到
  字面 `./~/` 目录。
- **完成摘要示例 `58/70` → `66/80 (PASS)`**（low）— 旧 7 维评分残留。

### Tests

- 新增 4 个测试文件（Rule 1/12 代码块豁免、截图 host 边界、S3 图片识别、
  tone-calibration 缓存路径），4 个 Python bug 均先写复现测试再修。
- `python3 -m pytest tests/ -q` → **575 passed**（v1.9.1 为 559）。

## [1.9.1] - 2026-06-02 — 补齐 S3 渐变科技视觉 preset（消除孤儿标签）

### Why

文档审计发现 code/doc 不一致：`skills/images/image-guide.md` 面向作者定义了
S1–S8 共 **8 个风格标签**（推荐矩阵也引用 S3），但代码 `VISUAL_STYLE_PRESETS`
只有 **7 个 preset**——**S3「渐变科技 / Gradient Tech」没有对应路由项**。作者按
image-guide 选 S3 时路由器悄悄落到默认风格，S3 是个孤儿标签。

### Added

- **S3「渐变科技 / Gradient Tech」preset**
  (`scripts/generate_and_upload_images.py`)：深色背景 + 霓虹渐变、未来感，面向
  C 深度 / G 观点 的前沿技术话题，规格对齐 image-guide.md S3 段。
  - `VISUAL_STYLE_PRESETS["gradient tech style"]`：palette 紫→青/品红→蓝霓虹渐变，
    background `dark navy ... neon gradient accents and glowing edges`，treatment/
    lighting/scale 双变体，结构与其余 7 个 preset 一致。
  - `DESIGN_LOGIC_RULES` 新增 `primary_goal: "evoke frontier tech"` 路由规则，
    触发词 `futuristic` / `cutting-edge` / `frontier` / `next-gen` / `sci-fi` /
    `cyberpunk`（distinctive，不与现有规则触发词冲突）。
  - 至此 image-guide 的 S1–S8 全部由代码 preset + 路由支撑（8 preset / 7 路由规则 +
    默认 S1）。

### Tests

- `tests/test_image_variation.py` +4：futuristic prompt 路由到 gradient tech、
  `build_design_logic` primary_goal、preset schema 完整性、background 注入含
  `gradient`。全套 544 tests pass（含这 4 个，排除 Playwright E2E）。

---

## [1.9.0] - 2026-06-02 — edge-case 修复批次 + Minimax-first 回归 + CI auto-merge

### Why

v1.8.4 dogfood 后清扫了一批 edge-case bug，并补上 CI 自动合并 owner PR 的工作流。
核心矛盾：env.example.json/ENV.md 文档化的 `gemini_image_model` 配置在缺
`image_model` 时会让默认图像模型悄悄退回 Gemini，与「Minimax 优先」设计相悖。

### Added

- **CI 单人 owner 自动发布流水线**（已上线并实测验证：owner 开 PR → 测试绿 →
  自动合并删分支 → 版本变更则级联打 tag/release）(`df7b595`, `60d2b40`)：
  - `auto-merge-owner.yml`：仅当 PR 作者 == `github.repository_owner` 且非草稿时，
    `gate` job 跑测试套件（排除 Playwright E2E，由独立 workflow 覆盖），`merge` job
    （`needs: gate`）通过后直接 `gh pr merge --merge --delete-branch`。非 owner 的 PR
    原样留待人工 review。无需 branch-protection / `allow_auto_merge` 仓库设置——合并由
    job 的 contents/pull-requests write 权限授权。
  - **关键坑**：用 `GITHUB_TOKEN` 推送的合并 commit **不会**级联触发 `on: push` 工作流，
    所以 `tag-release.yml` 在自动合并后永远不会自己跑、版本 bump 会漏打 tag。
    `workflow_dispatch` 是该抑制的显式例外，故 merge job 末尾用
    `gh workflow run tag-release.yml --ref main` 主动派发。
  - `tag-release.yml` 是 **version-driven + 幂等**：读 `plugin.json` 版本，已存在
    release 则 no-op，否则建 tag + release。无 auto-bump（`plugin.json` 是唯一真源）。
- **生成图像/截图文件名加时间戳段**，避免跨次运行覆盖 (`b9948c2`)。

### Fixed

- **图像默认模型回归 Minimax**：抽出 `config.resolve_default_image_model()`——
  显式 `image_model` 覆盖优先，否则一律 `minimax-image-01`；`gemini_image_model`/
  `minimax_image_model` 不再翻转默认（`gemini_image_model` 只选 Gemini 兜底变体）
  (`2948ffc`)。
- **Minimax 生成路径可观测**：暴露 `base_resp` 错误而非吞掉 (`27379f2`, `0b0c24a`)。
- **verify-cache 原子写**：`write_verify_cache` 与 `screenshot_tool` 改为写临时文件
  + `os.replace`，避免序列化中途失败或两个写者交错导致缓存损坏/清空 (`836cb90`)。
- **verify-claims 不再漏掉工具**：`FOO=bar mytool` 的前导赋值前缀现在会被剥离；
  `git -- file` 的 `--` 不再被误判为帮助说明分隔符（散文分隔符限定为 em/en 破折号）
  (`b8edbac`)。
- **Rule 13 围栏扫描器去同步修复**：4 反引号嵌套 3 反引号时朴素 toggle 失同步，
  误把内层当闭合、外层当无语言标识开头，导致 `--write-gate` 退出 1 阻断保存；
  新增 CommonMark 正确的 `iter_code_blocks()`，Rule 13/14/ascii_gate 共用 (`a99d434`)。
- **Rule 11 本地图检查不再依赖 CWD**：删掉对 `os.path.exists()` 的非确定性检查与死变量，
  发布门下相对本地路径一律判为残留 (`a2af3ff`)。
- **lint 尊重行尾内联 `lint:disable` 标记** (`69589dc`)。
- **images 占位符文件名唯一化 + 跳过代码块内占位符**（含 screenshot 解析器）
  (`ff51cbc`, `0a192d4`)。
- **release：bump_version 打的 tag 指向包含 bump 的 commit**（而非 bump 前 HEAD）；
  release commit 只 scope 到 bump 文件 (`f949394`, `31687ed`)。

### Docs

- review 命令描述更正为「23 rules + 8-dim scoring」(`2cb1cde`)。

### Tests

- `test_images_cli` 在无 key 的 CI 下保持 hermetic (`4e03f86`)。

---

## [1.8.4] - 2026-06-01 — attribution-as-voice (Rule 5/22) + 诚实 AIGC 标签

### Why

dogfood 暴露反常激励：忠实、完整归属来源的 YouTube 摘要被 Rule 5/22 判「个人声音太少」，
而从零虚构 6 段第一人称轶事的文章却通过——规则在**奖励虚构、惩罚诚实引述**。

### Fixed

- **来源归属算作有效锚点/声音**：新增 `ATTRIBUTION_ANCHOR_REGEX`
  (据/根据/官方/原文/「视频里说」/「Karpathy 演示」)，`_has_concrete_anchor` 现在
  计入归属，Rule 5 不再把忠实归属段判为「连续 3 段缺少具体锚点」；Rule 22 在
  `个人经历 ≥2 OR 来源归属 ≥2` 时通过；Rule 5 跳过 conclusion/intro 段 (`9560a62`)。
- **诚实的默认 AIGC 标签**：默认页脚从「本文 AI 辅助起稿 + 人工核实改写」（自动断言
  常常并未发生的人工核实）改为「本文由 AI 辅助创作，关键数据与事实请以原始来源为准」；
  「+ 人工核实改写」降级为作者真正核实后的 opt-in，来源摘要类文章用诚实变体 (`e672cff`)。

### Tests

- `tests/test_attribution_anchor.py` 钉住 attribution-as-voice 契约。

---

## [1.8.3] - 2026-05-31 — 共享上传器静默降级改为告警

### Fixed

- **screenshot 共享上传器失败时告警而非静默吞掉** (`e656a95`)。

### Tests

- screenshot 上传测试 hermetic 化（此前会打到真实 CDN）(`824185b`)。

---

## [1.8.2] - 2026-05-31 — 修复裸 'scan' 被误读为 screenshot_tool 子命令

### Fixed

- **screenshot：裸词 `scan` 被误读为 CLI 子命令**，改写措辞规避 (`a2c01d5`)。

---

## [1.8.1] - 2026-05-29 — dogfood 文档跟进

### Fixed

- 处理 3 个 dogfood 小跟进：title-skip、字数校准、Rule 14 提示 (`dbcd9c4`)。
- **series 导航 callout 在 `wechat-native` 下随形态条件化** (`a2fe442`)。
- **Rule 6 显式 `body_form` 优先于 `wechat_target` 别名**（解析器对齐）(`658b6a1`)。

---

## [1.8.0] - 2026-05-29 — 正交 body-form 轴（wechat-native 默认）

### Why

需要与 tone 并列的第二条正交轴 `body_form` 来决定**正文形态**：`wechat-native`
（移动端公众号体，默认）vs `long-form`（博客体，知识库归档副本）。它独立于
*写作风格*（A–H 内容身份）和 *深度*（字数）——`wechat-native + deep` 文章可以又长又
移动端形态。

### Added

- **`config.resolve_body_form()` 解析器**：优先级 `--body-form` CLI > frontmatter
  `body_form:` > 旧 `wechat_target: false` 别名 > 默认 `wechat-native`；
  `wechat_target` 不再是死字段 (`ab31364`)。
- **requirements 输出 `body_form`**（默认 wechat-native，long-form 仅显式开启，
  绝不从深度/教程关键词自动推断）(`b917716`)。
- **orchestrator 解析 `--body-form` / `--long-form` 并透传 requirements** (`3dacabe`)。
- **write 注入 Body Form 规则**，callout 随形态条件化渲染（仅 long-form），
  style-guide 新增 Body Form 段并吸收 platform-adaptation 块 (`dba52cc`, `ba2bc0c`)。
- **publish 在 `body_form: long-form` 时跳过微信 checklist**（此前 wechat_target 死字段）
  (`19a9462`)。
- **review Phase 2 软形态一致性信号**（不新增 write 门）(`5cf8a9d`)。
- **`check_rule_6` 阈值随形态调整**（wechat-native 每节阈值 -1）(`b2ad49a`)。

### Docs

- 设计规格 `docs/superpowers/specs/2026-05-29-wechat-native-body-form-design.md`
  + 实施计划（9 任务 TDD）(`2eb1ad2`, `afffe72`)。

---

## [1.7.8] - 2026-05-29 — write-gate bug 修复 + 死代码/文档清理

### Why

严格遵从的 write agent 永远无法保存：write 预存门跑了 Rule 11（占位符残留），
但 write 阶段**必须**产出 `<!-- IMAGE: -->` 占位符（由 images 阶段后续解析），
导致 `--write-gate` 在每篇合法草稿上退出 1（GATE BLOCKED）。测试套件因「干净文章」
fixture 无占位符而漏检。

### Fixed

- **write 门 Rule 11→14 互换**：write 门应捕获 ASCII 图（图像前自动转换），
  占位符残留是 review 阶段门——脚本与文档间的 Rule 11/14 身份此前交叉了 (`8883ba7`)。

### Removed

- **删除死代码 `VerificationCache`**：`config.py` 里 `VerificationCache` /
  `get_verification_cache()` 零调用方（~130 行），连带清掉孤立的
  `time`/`atexit`/`tempfile` import；verify/SKILL.md 文档化的可配置 TTL
  (`verify_cache_ttl_seconds` 等)纯属虚构——真实缓存是固定 1h TTL，已重写为如实描述
  (`1803c0d`)。

---

## [1.7.7] - 2026-05-29 — 修复 datetime.utcnow() 弃用警告

### Why

用户安装 1.7.6 后运行 review 阶段，`review_selfcheck.py` 产生
`DeprecationWarning: datetime.datetime.utcnow() is deprecated`。该 API 在
Python 3.12+ 已弃用并计划移除。属于警告级（功能正常），但污染 review 输出。

### Fixed

- `scripts/review_selfcheck.py:1187`（tone-calibration jsonl 时间戳）与
  `scripts/publish_plan.py:46`（备份文件名时间戳）：`datetime.utcnow()`
  → `datetime.now(timezone.utc)`。输出格式逐字节一致（review_selfcheck
  保留 `...Z` 后缀，publish_plan 保留 `YYYYMMDDhhmmss`）。全仓库已无其他
  `utcnow()` 调用；504 tests pass。

## [1.7.6] - 2026-05-27 — S8 AI 教程封面 preset + D1 Background 注入轴架构修复

### Why

用户要新增「AI 教程封面风」视觉风格（黑底科技网格 + 悬浮白卡 + 高对比黑白 + cyan 强调 + Notion/Figma/B 站 AI 知识博主氛围），落到 S8。落地过程中通过 7 轮 dogfood（v1–v7, 28 张实测图）发现并修复了一个潜伏的架构问题：

**核心发现 (v6 → v7 对照实验)**

`scripts/generate_and_upload_images.py` 的 `_style_variants_for_preset()` 返回 `background` 字段，但 `vary_prompt_for_position()` 自动注入的 7 个轴（Camera / Composition / Visual treatment / Palette / Material / Lighting / Scale）**不含 Background**——`background` 在所有 7 个 preset 里都是死字段。

实战影响：S8 的 background token 是整套风格的核心锚点（"dark black background with subtle tech grid, multiple floating white diagram cards as the dominant visual structure"）。作者写 naive 内容 prompt（"A RAG pipeline showing ..."）触发 S8 路由后，模型只拿到 `Palette: B&W with cyan accent` 一个弱信号，**0/4 产出 S8 美学**（白底 + S7 信息图 + 满屏 gibberish 文字标签）。

D1 修复后，同一组 base prompt **4/4 全部回归黑底 + cyan**，其中 2/4 完整复现 S8 卡片结构（剩余 2/4 偏离是内容语义抢首位注意力，作者侧已在 image-guide.md 写作规则中告诫）。

### Added

- **S8 AI 教程封面 preset** (`scripts/generate_and_upload_images.py` `VISUAL_STYLE_PRESETS`)：
  - 16 个 trigger 关键词：transformer / llm / large language model / neural network / attention mechanism / self-attention / embedding / fine-tune / fine-tuning / rag / retrieval-augmented / ai agent / llm agent / prompt engineering / ai tutorial / knowledge card
  - palette **单变体**锁 cyan（v4 实测双变体 cyan/yellow 轮转导致 4 图整组 accent 不一致）
  - background 强 anchor: `"dark black background with subtle tech grid, multiple floating white diagram cards with rounded corners and soft shadows as the dominant visual structure"`
  - treatment 双变体: `diagrammatic with stronger visual hierarchy` + `bold contrast with crisp outlines and accent blocks`（v3 实测 `editorial and narrative` 让 rhythm 图脱锚到赛博朋克场景，已去除）
- **`DESIGN_LOGIC_RULES` 首位 AI 规则**：`primary_goal: "teach AI/LLM concept"` 放在 `explain structure` 之前，确保 "Transformer architecture diagram" 优先命中 S8 而非 S2（命中顺序很关键，pythonic 实测验证）

- **`skills/images/image-guide.md` 新增 S8 段**：
  - 完整风格约束模板 + Transformer 封面示例 PROMPT
  - **⚠️ 避坑 box（v1.7.6 实测）4 条**：
    - 不要用文字暗示词（`notebook annotations` / `handwritten notes` / `sticky notes` → 改 `hand-drawn doodle marks` / `arrow scribbles` / `geometric shape sketches`）
    - rhythm 图必须用结构化措辞（含 ❌/✅ 对照表 3 行）
    - 模型选择建议（minimax 多卡场景下 ~30% 假文字漏出，封面零容忍用 gemini-2.5-flash-image）
    - palette article-wide 锁 cyan（作者要换 accent 需显式 `Palette: ...` 覆盖）
  - 风格 × 文章类型推荐矩阵新行：A 教程（AI/LLM 主题）+ AI 知识博主向 → S8
  - 设计逻辑表新行：讲 AI/LLM 概念 → S8

### Fixed

- **D1: `vary_prompt_for_position()` 新增第 8 个注入轴 `Background:`**：
  - 同 palette/material 等的 `"X:" not in base_prompt.lower()` skip 模式
  - 修复了所有 7 个 preset 的 background 死字段问题（S1-S7 也顺带受益，之前同样不被注入）
  - **v6 vs v7 对照实测**：同一组 naive RAG / fine-tune / embedding / ai agent prompt，D1 前 0/4 产出 S8，D1 后 4/4 黑底 + cyan + 卡片结构

### Tests

- 7 轮 dogfood（v1–v7, 28 张实测图）逐轮发现并闭环：
  - v1：单图基础验证（minimax 默认）—— S8 视觉成立，但有 gibberish 文字 + yellow 溢色
  - v2：去掉 `notebook annotations` text-priming 词 + 强化 `single cyan only` —— 单图干净
  - v3：4 张 dogfood —— 暴露 idx 1 脱锚（赛博朋克头颅）+ cyan/yellow 翻烧饼
  - v4：A+B+C 三联修（palette 单锁 + treatment 去 editorial + 结构化 base prompt）—— 4/4 S8 家族，但 idx 1 出现可读 "KNOWLEDGE"
  - v5：B' 修（locked token 里 "knowledge cards" → "diagram cards"）—— 4/4 干净 + 无可读单词
  - v6：naive 作者用法（不写 S8 风格 stem，只写内容）—— **暴露 background 死字段架构盲点，0/4 S8**
  - v7：D1 修复后同一组 naive prompt —— **4/4 回归 S8**
- Python selector 自检 7 个 probe prompt 全部正确路由（transformer / ai tutorial / RAG → S8；benchmark → 数据可视化；microservices → 等距）
- `py_compile` 通过

---

## [1.7.5] - 2026-05-22 — publish step 3.5 A/B 路径（「点亮原创」vs「创作来源-AI 生成」gray zone）

### Why

实际发布 v1.7.4 dogfood 文章时碰到真实矛盾：v1.7.4 的 checklist 让作者**同时勾选**：

- 「点亮原创」（推荐池命中, ≥300 字门槛）
- 「创作来源 → 内容由 AI 生成」（GB 45438-2025 合规）

但 developers.weixin.qq.com 用户社区的实际反馈是「未经原创著作人独家授权的再创作内容不能声明原创」——AI 完全生成的内容**实际上**无法点亮原创。

**官方调研**（developers.weixin.qq.com 多个相关帖）：

| 用户提问 | 官方答复 |
|---|---|
| AI 生成的内容能否在公众号声明为原创？ | 官方运营专员（旦旦 2024-12-21）回避主题，只说"需提交证明内容原创或已授权的材料" |
| 原创声明中能否提供 AI 选项？ | **无官方回复** |
| 内容由 AI 生成 是指什么？ | 仅有"智能回答 本次回答由 AI 生成"，**非官方运营专员** |
| 推文由 AI 辅助大纲，内容自己撰写，需要勾「内容由 AI 生成」吗？ | **无官方回复** |

**结论**：这是**官方未明确表态的 gray zone**——必须把决策权交给作者本人，但要给清楚 A/B 路径。

### Changed

- **`skills/publish/SKILL.md` Step 3.5 checklist 重构**为 A/B 二选一：

  **路径 A — AI 辅助路径**（推荐 article-craft 默认场景）：
  - 适用：主题/立场/数据/经历都是作者的，AI 起稿后人工审阅决策
  - 操作：**点亮原创** + 「创作来源」**不勾** AI 生成 + 文末保留 Rule 18 AIGC 显式标识
  - 含 3 个自检问题（个人经历真伪 / 立场归属 / 责任承担）

  **路径 B — AI 完全生成路径**：
  - 适用：LLM 一键生成 + 几乎不改 / 流水线批量产出
  - 操作：**不点原创** + 勾「创作来源-内容由 AI 生成」+ 文末 Rule 18 标识

  **决策权**：明确归作者本人。article-craft 工具只检测显式标识（Rule 18）是否存在，**不评估 AI 占比**。

- **【合规项-通用】分组新增**：A/B 路径都必须满足
  - Rule 23 反向声明检查（"非 AI 生成 / 完全人工 / 纯手写"等不能写）

- **`tests/test_publish_ab_path.py`**：11 个 unit test：
  - A/B 两个路径结构存在
  - Path A 明确说"不勾创作来源-AI" + "点亮原创"
  - Path B 明确说"勾创作来源-AI" + "不点原创"
  - 文档显式承认 gray zone + 决策权归作者
  - 含 Path A 自检问题
  - 通用合规规则（Rule 23 + 允许推荐 + 单发未分组）在两条路径下都强制

### Why no `wechat_ai_path: A|B` frontmatter field

考虑过让作者在 frontmatter 加 `wechat_ai_path: A` 让 publish 自动跳转到对应 checklist。否决原因：

1. 这是**作者决策**，不是文章属性——同一作者写不同文章可能走不同路径
2. 决策权落地到 frontmatter 会创造"工具替作者背书"的错觉——但 article-craft 不评估 AI 占比，无法判定路径
3. publish 阶段一次性给出 A/B 两套对照表，作者扫两眼自己选反而更快

### Tests

- 50 个 unit test 全部通过（v1.7.1-v1.7.5 累计）
- 真实 fixture: v1.7.4 dogfood 文章 + 4 篇 patched 旧文均能正确走对应路径

---

## [1.7.4] - 2026-05-22 — Rule 4 tags 强制 (P2 补救 4 篇实测 100% 失败)

### Why

4 篇已发布文章在 Rule 4 上 **100% 失败**：

| 文章 | tags 数量 | 中文 tags 数 |
|---|---|---|
| A1 LLM Wiki | 2 | 1 |
| A2 金鱼脑 | 2 | 1 |
| A3 NotebookLM | 2 | 1 |
| A4 Hindsight | 2 | 1 |

要求是 ≥3 tags + ≥3 中文 tag。全英文 tags（如 `[MCP, AI, DevOps]`）让看一看 NLP 算法无法匹配中文兴趣画像 → 长尾推荐池命中率拉低。

根因：article-craft 默认生成的 frontmatter 模板只展示了 3 个 placeholder（tag1/tag2/tag3），LLM 跟写时倾向只填 2 个英文短词。

### Added

- **`skills/write/SKILL.md` Step 3a 升级**：frontmatter 模板从抽象 placeholder 改为带 Rule 4 硬约束 + 中文标签示例：
  - 硬约束表格：≥3 tags + ≥3 中文 tag
  - 禁用模式 ❌：`[MCP, AI, DevOps]` / `[Kubernetes, Docker]`
  - 推荐模式 ✅：`[Kubernetes, Docker, 容器运维, AI工具, 实战教程]` 等 3 套示例

- **`skills/publish/SKILL.md` Step 3.5.0 新增**：发 checklist 之前**自动跑** `review_selfcheck.py --rules 4 --json`：
  - `passed` → checklist 中 tags 项标 ✅
  - 不达标 → 标 ⚠️ + 给出基于 title / description 推断的补丁建议
  - 兜底防护：即使 write 阶段漏了，publish 阶段最后自检一次

- **`skills/publish/SKILL.md` Step 3.5 checklist 新增条目**：「frontmatter tags ≥ 3 个 且 ≥ 3 个中文 tag」作为"看一看 NLP 匹配项"独立分组

- **`tests/test_rule_4_tags_enforcement.py`**：9 个 unit test 覆盖：
  - write SKILL.md Step 3a 含 Rule 4 硬约束 + 推荐模式 + 禁用示例
  - publish SKILL.md Step 3.5.0 调用 `--rules 4 --json` + 含 dogfood 引用
  - 集成测试：2 tags 失败 / 3 中文 tags 通过 / 3 英文 tags 失败

### Why publish 阶段也跑（不只 write）

Defense in depth：write 阶段的约束依靠 LLM 自觉跟模板。如果 LLM 默认偏差再次发生（这本身就是 LLM 写作的常见模式），publish 阶段的自动自检是最后一道关卡。

实操上：write 输出 2 tags → publish step 3.5.0 自动跑 Rule 4 → 检测失败 → 在 checklist 中标黄并给具体建议 → 作者发布前在 frontmatter 手工补 1-2 个中文 tag → 重新跑 publish → 通过。整个流程闭环。

### Tests

- 39 个 unit test 全部通过（含 v1.7.1 / v1.7.2 / v1.7.3 / v1.7.4 所有新规则）
- 真实 fixture 验证：3 中文 tag → PASS；3 英文 tag → FAIL（Rule 4 行为符合设计）

---

## [1.7.3] - 2026-05-22 — Style G + opinionated 加强模板（P1 补救 4 篇实测 100% 失败）

### Why

dogfooding 跑 v1.7.2 review_selfcheck 在 4 篇已发布微信文章上发现：

```
4 篇文章在 Rule 17 强观点 + Rule 22 主观判断上 100% 失败:
  A1 LLM Wiki      强观点 0  /  主观判断 0
  A2 金鱼脑         强观点 0  /  主观判断 0  /  个人锚点 0
  A3 NotebookLM    强观点 0  /  主观判断 0
  A4 Hindsight     强观点 0  /  主观判断 0
```

这不是单篇运气问题——是**写作模板缺失导致的系统性偏差**。v1.7.2 的
tone-aware prompt augmentation（`## Tone: opinionated`）只给了抽象 rules
（"强观点 sentences 必须 ≥ 1"），没给可填空的句式表，LLM 写到结尾退化
成中立技术教程。

### Added

- **`skills/write/style-guide.md` 新增 `### Style G + opinionated 加强模板`** —
  在 `## Tone: opinionated` 之后追加可填空的写作模板：
  - **个人经历句式表**（≥ 2 处，Rule 22 检查项）：时间锚 / 项目锚 / 失败锚 / 选择锚 / 数字锚
  - **主观判断句式表**（≥ 1 处，Rule 22 检查项）：我推荐 X 因为 Y / 我不用 Y 因为 Z / 我觉得 X 就是 Y 等
  - **强观点句式表**（≥ 1 处，Rule 17 检查项）：我赌 / 我敢断言 / 别学 / 这玩意儿就是 等（命中 `STRONG_OPINION_PATTERNS`）
  - **具体锚点句式**（每章节 ≥ 1 处，Rule 5 检查项）：命令 / 数字 / 路径 / 报错码
  - **4 篇实测对照表**：写作时贴在屏幕上的具体失败案例（贴的是真实失败数据，不是抽象 rules）
  - **A2 金鱼脑 before/after 改写示例**：展示如何把"中立技术教程腔"改写为含个人锚点

- **`skills/write/SKILL.md` Step 3a.5 升级**：当 `tone: opinionated` 时，
  **额外加载** `### Style G + opinionated 加强模板` 章节作为 prompt augmentation

- **`tests/test_style_guide_p1.py`**：8 个 unit test：
  - style-guide 结构（必含 4 句式表 + 4 篇对照表 + "100% 失败" 警告）
  - `STRONG_OPINION_PATTERNS` 与文档不漂移（文档里的强观点例子必须实际匹配
    `scripts/config.py` 里的 regex）
  - write SKILL.md Step 3a.5 引用新章节

### Why 没把 Rule 5/17/22 加入 write pre-save GATE

考虑过把 review-only 规则 (5/17/22) 加入 write 的 `WRITE_GATE_RULES`，让保存
前必须过。最终没做的原因：

1. write SKILL.md 现有职责分工明确："内容质量规则由 review skill 的 Phase 1
   统一执行,write 不再重复做"——加 gate 违反此约定
2. Rule 5/17/22 误报率比 Rule 6/11/13/16 略高，加 gate 会导致频繁循环
3. 改 prompt augmentation 的杠杆点 ROI 更高——LLM 写作时就吸收模板，而不是
   写完后被规则打回

v1.7.3 选择 **augmentation > gating**：让模板在写作时已经在 prompt 里，
而不是写完后被规则反复打回。如果效果不达预期，v1.7.4 再考虑加 gate。

### Tests

- 30 个 unit test 全部通过（含 v1.7.1 Rule 23 / v1.7.2 Rule 24 / v1.7.3 P1）
- 4 篇 P0 patched markdown 仍保持 P0 修复效果（Rule 18 + Rule 3 PASS）
- Rule 17/22 在已发布的旧文章上仍报失败——这是**预期**，P1 改进只针对未来文章

### Note

P1 模板的真实效果验证窗口期至少 4-6 周（需要作者用 v1.7.3 写 2-3 篇文章观察
review 阶段 Rule 17/22 通过率变化）。如果通过率未明显上升，v1.7.4 启动 gate
路径。

---

## [1.7.2] - 2026-05-22 — Rule 24 虚构数字检测 + Rule 23 bug 修复

### Why

Dogfooding pipeline 跑一篇 LAT.md 评论文章时发现两个真问题：

1. **Rule 23 实装 bug**：第一版代码 `body = strip_code_blocks(...)` 算出来后**没用**，违规检测循环仍迭代原始 `lines`——讨论 Rule 23 本身的文章（含规则反例的 ```text 块）被规则自己误报。
2. **22 条规则没有一条检测"虚构数字"**：LLM 写文章倾向"自信地编数字"让文章看起来更可信。第一轮微信调研推翻 10 条 CSDN 循环引用伪事实，但 v1.7.1 没有规则检测这种模式——这是 LLM 写作最大失败模式之一。

### Added

- **Rule 24: 虚构数字检测**（v1.7.2+，warning，不阻断）—— `scripts/review_selfcheck.py:check_rule_24`：
  - 扫描正文（非代码块、非 frontmatter）的"数字 + 单位"声明
  - 6 种豁免：backtick / markdown link / frontmatter `verified_numbers` / 前置 hedge（约/我估计/可能）/ 后置 hedge（左右/上下）/ 年份
  - Warning-only：FP 率天然高，目的是提醒作者人工核对，不机械阻断 publish
  - 高密度 (> 5 个) 在 `details` 字段标注
  - 详细文档：`references/self-check-rules.md` Rule 24

- **`tests/test_rule_24_fabricated_numbers.py`**：14 个 unit test，覆盖：
  - 4 种 bare claim 触发场景（百分比/时间/数量、warning-level 不阻断）
  - 6 种豁免机制各 1 测试
  - hedge 在中文流式句子里的灵活间距
  - 句子级 hedge 范围（逗号分隔的子句不互相豁免）
  - 高密度 marker

- **`tests/test_rule_23_code_block_exempt.py`**：8 个 unit test，覆盖 Rule 23 bug fix 的 code-block 豁免行为 + 几个 boundary cases

### Fixed

- **Rule 23 strip_code_blocks bug** (`scripts/review_selfcheck.py:check_rule_23`)：
  - 用 `code_lines` 集合标记所有处于 fenced block 内的行号
  - 违规检测循环遇到 code-block 内的行直接 `continue`
  - 修复前：讨论 Rule 23 本身的文章因 ```text 块里的反例字串被误报
  - 修复后：dogfood pipeline 上跑实测正常

### Changed

- **`references/self-check-rules.md`**：active rule count 23 → 24，新增 Rule 24 完整定义（检测项 + 6 种豁免 + 修复 4 选 1）
- **Rule 23 doc**：实现注意 footer 说明 strip_code_blocks bug fix 历史

### Why warning 而非 error（Rule 24 设计决策）

虚构数字检测的天然 FP 率高——同样写"30%"，可能是 LLM 编的、也可能是作者自己测的。Rule 24 不能机械阻断 publish，只能提醒作者"这里有未标注的数字，请核对"。

### Tests

- Rule 24 + Rule 23 unit tests 共 22 个全部 pass
- Dogfooding 验证：LAT.md 文章修前 Rule 24 报 51 个 warning，修后报 9 个（剩余均为可保留的边界 case）

---

## [1.7.1] - 2026-05-22 — 第二轮官方调研增量（推荐运营规范 A 级 + Rule 23 反推荐黑名单）

### Why

v1.7.0 已经基于第一轮调研（20 条命题）实装 Rule 18-22 + CTA + 双封面。本轮做了**第二轮增量调研**（`.research/wechat-distribution-mechanism-2026.md`），新挖到 **2 条 A 级 + 3 条 B 级官方证据**：

1. **`developers.weixin.qq.com` 公开了《微信公众号推荐运营规范》** — A 级官方一手，**公众号推荐资格的官方门槛**首次有完整证据：非分组发表、非转载、未勾选"不允许推荐"（**不可逆**操作）、符合两套规范。推荐流量去向是**"没有关注该公众号的用户"**——这是粉丝 <1000 小号破圈的唯一官方通道。
2. **微信珊瑚安全 2025-08-31 公告**明确平台**主动**添加 AI 标识——意味着不做合规标识不能"侥幸过关"。同时反向声明（"非 AI 生成"、"完全人工"）= 伪造标识，违反公告。
3. **"朋友推荐"功能 2025-03 真实扩测**（B 级），但微信官方无独立文档；36 氪 45.9% 数据是其自身矩阵账号自报，**不是微信官方公开数字**（修正第一轮"某财经小号"的描述）。

### Added

- **Rule 23: 反推荐特征词黑名单**（A/B 级官方依据）— `scripts/review_selfcheck.py` 实现 `check_rule_23`：
  - **ERROR**（阻断）：AIGC 反向声明检测（"非 AI 生成"、"完全人工撰写"、"纯手写"、"100% 人工"、"未使用 AI"等 10+ 种模式）——违反珊瑚安全公告"不得删除/篡改/伪造平台标识"
  - **WARNING**（不阻断）：标题营销词头部（"震惊"、"重磅"、"紧急"、"必看"、"独家解密"、"不看后悔"等 11 种）——违反《推荐运营规范》"捏造扭曲事实吸引眼球"
  - 文档：`references/self-check-rules.md` Rule 23 完整定义 + 修复指引

- **publish step 3.5 扩展为完整发布前 checklist**（6 项必须人工确认）— `skills/publish/SKILL.md`：
  - 合规 3 项：后台「创作来源」勾选 / 文末 AIGC 声明（Rule 18） / 无反向声明（Rule 23）
  - 推荐池命中 3 项：≥300 字点亮「原创」/ 保持「允许推荐」开启（**不可逆**警告）/ 单发未分组
  - 发布后 24h-7 天查后台「内容分析 → 单篇群发」指引

- **`skills/write/style-guide.md` 朋友推荐适配章节**（B 级软约束）— 标题应让"粉丝的非技术好友也能 get 痛点"，引用 v1.7.1 调研档命题 23

### Changed

- **`references/self-check-rules.md` active rule count: 22 → 23**，"Who enforces what" 矩阵新增 Rule 23 行，文档头部说明 Rule 23 来源是第二轮调研

### Why not（基于第二轮调研修正的"不做"清单）

- **不做图片 EXIF/水印隐式标识** — B 路盘点曾列为缺口，但珊瑚安全 2025-08-31 公告明确"平台**主动**添加隐式标识"，且 mp.weixin.qq.com CDN 会剥掉 EXIF，article-craft 做了也白做
- **不做细粒度（H3+）段落去重** — Rule 20 H2 级已覆盖 80% 场景，4 篇实测仅文章 3 有重复事故，ROI 太低
- **不做 Style-aware CTA 模板库** — Rule 3 检测已强制"必须含 CTA"，文案多样性是 LLM 生成能力问题，不是规则问题

### Tests

- `Rule 23` smoke test：反向声明触发 error（2 处），营销标题触发 warning（1 处），正常文章 0 violation
- `Rule 23` 真实 fixture 验证（`tests/fixtures/tone/opinionated_pip_should_die.md`）：不误报

### Research

- 新增：`.research/wechat-distribution-mechanism-2026.md` — 9 条增量命题（2A + 3B + 4C-），含官方原文 URL + 逐字摘录

---

## [1.7.0] - 2026-05-22 — WeChat 公众号生态适配（A 级合规 + 5 条新 Rule + 双封面 + CTA 模板库）

### Why

2026-05-22 用户反馈 article-craft 产出文章发布到微信公众号阅读量低。经过四轮调研验证：

1. **官方渠道严格调研**（`.research/official-sources-verification.md`）确认了 7 条 A 级 + 3 条 B 级官方一手事实，**推翻了 10 条无官方来源的伪事实**（包括"算法权重 40/30/20/10"、"30 天新号保护期"、"AI 率 <20% 安全"、"行业打开率 0.89%"等被前期诊断当 fact 用的核心数字）
2. **4 篇实际发布文章诊断**（`.research/published-articles-analysis.md`）暴露 3 个真瓶颈：CTA 100% 缺失、AIGC 标识 100% 缺失、标题命中钩子公式 0/4
3. **独立审计**（`.research/diagnosis-audit.md`）剔除恐慌驱动的过度推论（如"系列发文 = 自动化批量发布信号" — 无任何官方证据支持）

本版本只基于 A/B 级官方证据 + 4 篇实证瓶颈做改造，14 项变更覆盖合规 + 标题 + CTA + 工程质量四块。

### Added

- **Rule 18: AIGC 显式标识检查**（A 级合规）— GB 45438-2025 强制国标 2025-09-01 已生效，网信办《标识办法》14 条同步生效。文末必须含 "本文 AI 辅助起稿 + 人工核实改写" 或等效声明。`scripts/review_selfcheck.py` 实现 `check_rule_18` + auto-fix（lint 自动追加文末脚注）。`skills/publish/SKILL.md` Step 3.5 加发布前提醒用户在公众号后台勾选「创作来源 → 内容由 AI 生成」（4 选 1，**发布后不可改**）。
- **Rule 19: 标题钩子 + 长度约束** — 标题 ≤28 字（业界实测）/ ≤64 字（硬上限）+ 至少 1 个钩子类型命中（数字 / 反差 / 痛点 / 故事 / 悬念）+ 黑名单词检测（震惊 / 重磅 / 解密等标题党降权风险）。
- **Rule 20: 段落相似度去重** — fuzzy match H2 标题（≥0.85）或首句相似（≥0.85）+ 内容相似度（≥0.7）→ block，防止 LLM 上下文跳跃事故（文章 3 实测有「引用是怎么工作的」段落重复两次）。
- **Rule 22: 个人化注入软警告** — 个人经历 ≥ 2 处 + 具体数字 ≥ 1 处 + 主观判断 ≥ 1 处。基于 4 篇实测分布校准的阈值（不是凭空 ≥3 处）。
- **`wechat_action` frontmatter 字段**（heart / share / collect / comment）— `skills/requirements/SKILL.md` Layer 4.5 按 Style + Intent 自动推断；`skills/write/SKILL.md` 文末按 wechat_action 选 CTA 模板。
- **CTA 模板库**（`references/writing-styles.md` § Closing Templates）— 4 类引导动作各配 2 个具体话术，禁用"一键三连"和"希望本文有帮助"等空话。
- **3 个候选标题机制**（`skills/write/SKILL.md` Step 1.5）— write skill 生成 3 个候选标题（数字 / 反差 / 痛点钩子各一个），AskUserQuestion 让用户选，作为 WeChat 不支持原生 A/B 测试的变通方案。
- **GitHub URL 真实性 + CJK 幻觉检测**（`scripts/verify_claims.py`）— 扫描文章所有 `github.com/<org>/<repo>` URL：仓库名含中文 → 直接 block（明显 AI 幻觉，零成本）；HEAD 请求 404 → block（4 月草稿事故里的 `aws-lab/aws-mcp-server` 实测被拦下）；网络/限流错误不阻断。新增 `--skip-network` flag 离线模式。
- **CTA + 系列预告位置规则**（`skills/series/SKILL.md` Step 3）— 系列文章末尾结构强制 CTA 在系列预告之上（视觉首位），4 篇实测有 3/4 篇被预告挤掉 CTA。
- **share_card 双封面**（`scripts/share_card.py`）— 新增 `wechat-double` 特殊值，自动展开为 `wechat-cover`（900×383, 2.35:1 头条封面）+ `wechat-share`（1080×1080, 1:1 分享方图）。`wechat-share` 改为 1:1（v1.6.x 是 1.25:1）。
- **8 维 review 评分（v1.7+）**（`skills/review/SKILL.md`）— 在原 7 维基础上新增"看一看友好度"维度（标签丰富度 + 独家信号 + 中段钩子 + 金句密度 + 关键词密度，**全定性，不用伪算法权重**）。Threshold 从 55/70 → 63/80（等价比例）。

### Changed

- **Rule 3（结尾段落）从"全禁互动引导"改为"必须含 1-2 个具体 CTA"** — 这是 v1.6.x 的反向优化：4 篇实测 4/4 都缺 CTA = 主动放弃公众号生态的关键算法权重。新版强制至少 1 个 CTA 动作 + 仍禁"希望本文有帮助" / "一键三连" / 伸手党语气。Style H "⭐点赞、转发、在看一键三连⭐"通过 Style 检测放行。
- **Rule 4（Description 字段）扩展中文标签强制** — tags ≥ 3 个且 ≥ 3 个中文标签（公众号读者 99% 中文用户，全英文 tags 会让看一看 NLP 算法无法匹配中文兴趣画像）。

### Compliance

- **GB 45438-2025 强制国标**（2025-09-01 生效）+ **网信办《人工智能生成合成内容标识办法》14 条**（同步生效）双合规：Rule 18 强制文末 AIGC 脚注 + publish skill 提醒后台勾选。这是 A 级官方一手要求，不是行业经验。
- **微信《运营规范》"非真人自动化创作"条款**（微信团队 2026-04-09 对媒体确认）— article-craft 的"用户发起 + AI 辅助 + 用户审核 + 用户发布"姿态**不命中**违规条款（条款针对"完全替代真人 + 矩阵号 + 程序托管批量发布"），微信官方明确表态"鼓励合理使用工具辅助创作"。前期诊断的"封号风险高"评估被官方调研推翻。

### Removed（基于官方调研推翻的伪事实，避免污染未来）

前期诊断引用的多条"事实"在官方渠道找不到来源，本版本不再使用：

- ❌ "算法权重 40/30/20/10"（CSDN 个人博客虚构，循环引用无源头 → 8 维评分不再使用任何算法权重数字）
- ❌ "30 天新号保护期" / "完播率 1.3 倍流量加成" / "AI 率 <20% 安全"（无官方来源 → 不做基于这些数字的工程）
- ❌ "行业打开率 0.89%" / "尾部 <0.3%"（一手发布方不可考 → 不做 KPI 校准基线）
- ❌ "AI 率检测 API + >30% block publish"（基于伪事实 → 不引入第三方 AI 检测依赖）
- ❌ "系列发文 = 自动化批量发布信号"（恐慌驱动 → 不强制系列发文随机化）
- ❌ "AI 自声明禁用 P0"（4/4 实际产出未出现，伪问题）

详见 `.research/official-sources-verification.md` 与 `.research/diagnosis-audit.md`。

### Sources（A/B 级官方一手）

- GB 45438-2025: <https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=F32EA2A561F1886CD8D606513512D547&refer=outter>
- 网信办《标识办法》: <https://www.cac.gov.cn/2025-03/14/c_1743654684782215.htm>
- 微信运营规范 2026-04-09 团队回应（21 经济）: <https://www.21jingji.com/article/20260409/herald/85296dd9f3152bdbc88af96167989bcd.html>
- RALM 论文（仅作用于"看一看"频道，非订阅号信息流）: <https://arxiv.org/abs/1906.05022>
- 完读率官方定义（livia 答复）: <https://developers.weixin.qq.com/community/develop/doc/000a8857660538166ecf9b8f751800>
- 原创门槛 300 字（明月清风答复）: <https://developers.weixin.qq.com/community/develop/doc/0006ecc2f98b88fa138adfd0d51800>

---

## [1.6.24] - 2026-05-21 — pipeline GATE alignment + youtube transcript robustness

### Why

A live `/article-craft:orchestrator` run on a YouTube video surfaced 8 design
gaps that traced back to skills/SKILL.md drift away from the canonical
`references/self-check-rules.md` matrix and from the actually-shipped
`scripts/`. Concretely:

- **write skill's pre-save GATE only enforced Rule 11/14** via the focused
  `ascii_gate.py`, but rules.md says write owns 1/2/6/11/13/16. Result: an
  article shipped with 4 red-flag words (Rule 1), 9 shallow `##` sections
  (Rule 6), and 3 untagged code blocks (Rule 13) — all caught only at review
  time when they should have been blocked at save.
- **youtube skill's `yt-dlp --dump-json` path is broken by YouTube's 2026
  n-challenge** — even `--no-check-formats` fails with "Requested format is
  not available". There was no graceful fallback and cookie handling was
  reactive (error-table only). The Step 4 handoff to `article-craft:write`
  was also ambiguous ("调用 write 的写作规范" — invoke the skill, or
  inline-follow?), so the failing run bypassed write entirely and missed
  every GATE.
- **review SKILL.md told the agent to "read rules.md and grep"** instead of
  calling the already-implemented `scripts/review_selfcheck.py --json`. The
  agent re-implemented half a dozen rule checks in one-off Bash/Python that
  the script already did, including subtly different (and worse) detection.
- **AskUserQuestion presented `02-技术/AI 应用/` as a save destination on a
  vault that has `02-技术/AI-生态/Claude-Code/`** — write skill didn't
  validate paths against the actual filesystem before surfacing options.
- **youtube skill never wrote `pipeline_state.py`**, so `--upgrade` mode
  can't resume articles produced via that branch.

### What changed

**`scripts/review_selfcheck.py`**:

- New `WRITE_GATE_RULES = (1, 2, 6, 11, 13, 16)` constant — the source of
  truth for which rules block save. Pinned by
  `CLIRuleSelectionTests.test_write_gate_rules_constant_matches_doc`.
- New CLI flag `--write-gate` — runs only those 6 rules, exit 1 on any FAIL.
- New CLI flag `--rules N,M,...` — run an arbitrary subset by ID. Precedence:
  `--rules > --write-gate > --gate-only > all`. Empty / whitespace-only input
  fails with `parser.error`, not a silent pass.
- New `run_selected_rules()` and `_parse_rule_list()` helpers. Unknown rule
  IDs surface as `skipped=True` CheckResult entries so callers can detect
  typos via the JSON output.
- Backward compat: `--gate-only` still works as an alias for `--rules 11`.

**`skills/write/SKILL.md`**:

- **Step 2** now requires `ls 02-技术/` before presenting save-path options
  via AskUserQuestion. Options must be paths that returned from `ls` (or
  paths to be created via explicit `mkdir -p` with the action announced).
- **Step 5** updated to list rules 1/2/6/11/13/16 as the pre-save GATE
  (was: 1/2/6/11 only). Deferred list expanded to 3/4/5/7/7b/8/9/10/12/14/15/17.
  Mentions the `WRITE_GATE_RULES` constant in `review_selfcheck.py` as the
  source of truth.
- **Step 6** now shells out to `review_selfcheck.py --write-gate --json`
  instead of just `ascii_gate.py`. `ascii_gate.py` is kept as a focused
  Step 4a tool (Rule 14 only). Per-rule failure-handling table inline.
- **Step 7** adds Check E — IMAGE placeholder count vs Rule 7b thresholds.
  Soft warning (writes a `cover` placeholder if missing, warns on rhythm-image
  shortfall but doesn't auto-insert — those would be orphaned). The
  "职责分工" callout no longer contradicts Step 6.
- "11 rule bodies" / "11 self-check rules" → 17 in both prose mentions.

**`skills/review/SKILL.md`**:

- **Phase 1 rewritten** to call `review_selfcheck.py --json` and parse the
  structured output, not to grep manually. Includes the JSON shape, exit-code
  semantics, and per-rule disposition (fix-in-place vs detect-only).
- "rules 1-11" → "all 17 rules" in feature list and output template.
- **Rules Index** at the end of the file rewritten to match actual
  `_RULE_DISPATCH` names in `review_selfcheck.py` — previous index had Rule 1
  as "Template Filler" (actually 红旗词汇), Rule 4 as "Code Block Depth"
  (actually Description 字段), Rule 11 as "ASCII Diagrams" (actually 占位符
  残留 — ASCII is Rule 14), etc. The misleading index was guiding agents to
  fix the wrong things.

**`skills/youtube/SKILL.md`**:

- **Complete rewrite** (308 lines, +166/-101 net).
- **Method A (recommended)**: `Skill(skill="baoyu-skills:baoyu-youtube-transcript", args=URL)`
  via the Skill tool — leverages baoyu's InnerTube + multi-client + yt-dlp
  fallback + cookie prompt that's already implemented. If Skill tool not
  available, bash glob now has correct path (`baoyu-skills/baoyu-skills/<hash>/...`
  — the directory is nested twice, was missed in the previous version).
- **Method B (fallback)**: `yt-dlp --cookies-from-browser=chrome` with
  cookies up front (not as error recovery), and `--print` instead of
  `--dump-json` to bypass the format check.
- **Method C (last resort)**: WebFetch for cases where A/B both fail.
- **Step 4** now explicitly invokes `article-craft:write` via the Skill tool
  with a complete args JSON template (topic / audience / depth /
  writing_style / key_points / source / transcript_path). The previous
  ambiguous "调用 write 的写作规范" was the root cause of write being
  skipped entirely during the failing session.
- **Step 6** calls `pipeline_state.py init / complete / skip` so
  articles produced via youtube can be resumed by `--upgrade`.
- Bot-detection handling moved from error-table into a step-by-step
  procedure in §Step 1+2.
- Hand-off section now mentions `--upgrade` for resuming.

**`tests/test_review_selfcheck.py`**:

- New `CLIRuleSelectionTests` class (8 tests). Coverage:
  - `WRITE_GATE_RULES` constant stays at `(1, 2, 6, 11, 13, 16)`
  - `_parse_rule_list` handles whitespace, commas, empty tokens
  - `_parse_rule_list` rejects non-integer with SystemExit
  - `run_selected_rules` emits skipped+passed for unknown IDs (doesn't mask real bugs)
  - End-to-end `--write-gate` exit 1 on failing article
  - End-to-end `--write-gate` exit 0 on clean article (happy path)
  - `--rules` flag overrides `--write-gate` per documented precedence
  - `--rules ""` / `--rules ",,,"` fails with argparse error (not silent pass)
- Total suite: 446 → 454 tests, all green (~21s).

### Independent code review

`superpowers:code-reviewer` audited the first round of fixes and found 5
BLOCKERs + 4 IMPORTANTs (write/SKILL.md Step 7 directly contradicting Step 6,
write/SKILL.md Step 5 still listing the old GATE rules, the misleading review
Rules Index, the broken baoyu path glob, the `--rules ""` silent pass, missing
happy-path test, stale source comment). All addressed in the same release.

### Migration notes

- No breaking API changes. New CLI flags are additive.
- Skills that were following the prior write SKILL.md will auto-pick up the
  new GATE on next run; existing articles are not re-validated retroactively.
- If you maintain a fork of `review_selfcheck.py`, the new `_RULE_DISPATCH`
  dict and `run_selected_rules` function are public-ish surface for callers.

## [1.6.23] - 2026-05-21 — verify-claims flag validation (B8 Phase 1)

### Why

`scripts/verify_claims.py` MVP only checked tool presence via
`shutil.which`. It would catch `python3 → not on PATH` but happily
shrug at `git push --mesage "..."` (typo) or `kubectl get --dryyy-run`
(typo) because the *tool* is present. B8 Phase 1 adds flag-level
validation for 7 high-frequency tools so authors get a typo-catch
warning before review.

### What changed

**New schema** in `scripts/verify_claims.py`:

- `TOOL_FLAG_SCHEMA` — a `dict[str, set[str]]` of curated long-flag
  whitelists for 7 tools: **git / docker / kubectl / uv / npm / curl /
  python3**. Each set has 20-100 of the most common flags per tool.
- Schema is **curated, not exhaustive** — designed to catch typos
  cheaply. Unknown flags emit warnings, never errors (Phase 1 contract).

**New helper functions**:

- `_extract_tool_and_flags(fragment)` — extends the existing
  `_extract_tool` to also return the long flags used. Strips `sudo` /
  `env` prefixes the same way, handles `--name=value` form, strips
  trailing punctuation.
- `_check_flags(tool, flags)` — returns the de-duplicated subset of
  flags NOT in the tool's schema. Tools outside the schema return `[]`
  (no validation).

**Scan integration**:

- `scan_article()` now collects per-tool flag usage across the whole
  article (incl. ubiquitous tools like git — the flag schema is the
  point), runs `_check_flags`, and reports each unknown flag with
  the offending fragment in the new `flag_warnings` JSON array.
- `cmd_scan()` displays warnings as `⚠️ N unknown flag(s)` block in
  human output; JSON consumers get them under `flag_warnings`.
- **Exit code is unchanged** — flag warnings are informational. Only
  missing-on-PATH still fails the run (Phase 1 contract). This is
  explicitly pinned in `test_scan_keeps_exit_code_unchanged_with_only_flag_warnings`
  so a later phase that DOES gate is an explicit behaviour change.

### Long flags only (Phase 1 design)

Short flags (`-a`, `-v`, etc.) are deliberately not validated. They
collide too much across tools — `-a` is `--all` for git, `--addr` for
some servers, `--archive` for tar/cp/rsync. Validating without
subcommand context produces too many false positives. Phase 2 (spec
§4) will add subcommand-aware schemas, which is the right place to
re-introduce short-flag checks.

### Documentation

- `skills/verify-claims/SKILL.md` — new "Flag-level validation" block
  explicitly noting Phase 1's scope (long flags only, warnings only,
  schema is curated not exhaustive)

### Tests

+13 new in `tests/test_verify_claims.py` (`FlagValidationTests` class):

- `_extract_tool_and_flags` long-flags-only + `=value` form + trailing
  punctuation + sudo prefix attribution (4 tests)
- `_check_flags` returns empty for unknown tool / unknown subset for
  known tool / dedupes (3 tests)
- `scan_article` flag warnings: git typo caught / valid flags clean /
  cross-tool aggregation / tool-not-in-schema skipped / exit code
  unchanged (5 tests)
- `TOOL_FLAG_SCHEMA` pins the curated 7-tool list (1 test — adding a
  new tool is a conscious schema-expansion decision)

**Total**: 446 passing (was 433 — +13 new, no regressions).

### What this enables

Phase 2 (subcommand-aware): split each tool's flat set into
`{global: set, subcommands: {name: set}}` and resolve flags against
the right scope. Catches "valid flag, wrong subcommand" errors
(e.g. `git checkout --message` — `--message` is valid for git
generally but not for checkout).

Phase 3 (ERROR promotion for specific tools): once schema confidence
is high enough (proven against a corpus of articles), promote
unknown-flag warnings to errors for select tools where the schema is
provably complete.

### Spec

`docs/superpowers/specs/2026-05-20-verify-claims-flag-validation.md`
— Phase 1 closed; Phases 2-3 still queued.

---

## [1.6.22] - 2026-05-21 — Self-hosted Stable Diffusion provider (B7 Phase 3)

### Why

Phases 1-2 covered SaaS image backends (Minimax + Gemini + OpenAI).
Phase 3 proves the same protocol handles non-SaaS — a self-hosted
Stable Diffusion via Automatic1111 webui, no API key, configurable
endpoint URL. Demonstrates that the `ImageProvider` contract doesn't
quietly assume "cloud auth-token" shape.

### What changed

**New provider class** `StableDiffusionProvider` in
`scripts/image_providers.py`:

- `name = "stable-diffusion"`, model `sd-local`
- POST `<endpoint>/sdapi/v1/txt2img` — the standard a1111 / Forge /
  sd.next / vlad webui shape
- Endpoint resolution: `STABLE_DIFFUSION_ENDPOINT` env var (preferred
  for ephemeral) → `stable_diffusion_endpoint` env.json key →
  `http://127.0.0.1:7860` default
- **Opt-in `is_configured()`**: returns True only when the env var
  OR env.json key is explicitly set. The localhost default fires
  inside `generate()` so users running a1111 locally get zero-config,
  but the provider doesn't show in `configured_providers()` / doctor
  output for users who never opted in.
- Aspect-ratio → (width, height) mapping with a1111's required
  multiple-of-8 rounding: `1:1` → 1024², `16:9` → 1280×720,
  `9:16` → 720×1280, `4:3` → 1152×864, `3:4` → 864×1152.
  Explicit `width`+`height` beats aspect_ratio.
- Sensible default sampling params: 25 steps, Euler a, CFG 7.
- `ConnectionError` from requests is translated to a friendly
  RuntimeError naming `STABLE_DIFFUSION_ENDPOINT` as the fix —
  catches the most common SD failure mode (a1111 not running).
- Handles `data:image/png;base64,` prefix that some a1111 forks add.

**`sd-local` is NOT in `MODEL_FALLBACK_CHAIN` by default**. The
chain stays SaaS-only to avoid surprising "no a1111 found" errors
at generation time. Opt-in via `image_model: "sd-local"` in env.json
or extend `MODEL_FALLBACK_CHAIN` locally for fallback behavior.

**Doctor extension** (`scripts/setup_dependencies.py`):

- `check_stable_diffusion_endpoint()` — `pass` when explicitly set,
  `warn` (not block) when missing (sd-local isn't in default chain
  → missing this never blocks the pipeline)
- Registered in `run_all_checks()`

**Documentation**:

- `env.example.json` — adds `stable_diffusion_endpoint: ""`
- `ENV.md` — adds SD to recommended config table + available-models
  block; explains the not-in-default-chain semantics

### Tests

+9 new in `tests/test_image_providers.py`:

- Protocol conformance for StableDiffusionProvider
- Registry resolution (`for_model("sd-local")`)
- `all_providers()` includes 4 providers now
- Opt-in `is_configured()` semantics (3 tests: false by default,
  honors env var, honors env.json key)
- Generate path: ConnectionError → friendly RuntimeError naming the
  env var
- Generate path: HTTP 500 → RuntimeError with status code
- Generate path: empty `images[]` → NoImageDataError
- `_sd_default_dimensions` aspect-ratio mapping + multiple-of-8 rounding

**Total**: 433 passing (was 424 — +9 new, no regressions).

### What this enables

Phase 4 (per-provider config namespacing) is the last open piece:
with 4 providers registered, the `env.json` top-level is getting
noisy (`minimax_api_key`, `gemini_api_key`, `openai_api_key`,
`stable_diffusion_endpoint`). Phase 4 will namespace under a single
`image_providers: { minimax: {...}, ... }` key while preserving
backward compat with the flat keys.

For users: D2 (English-language output) now has a fully self-hosted
backend option that doesn't require any SaaS account — useful for
air-gapped or privacy-sensitive deployments.

### Spec

`docs/superpowers/specs/2026-05-20-multi-provider-image-abstraction.md`
— Phases 1-3 done; Phase 4 queued.

---

## [1.6.21] - 2026-05-21 — Screenshot fixtures batch 2: reddit / zhihu / wechat (B3 Phase 2)

### Why

Continues B3 Phase 2 from v1.6.19 (4 → 7 of 15 platforms). The 3 new
fixtures cover the highest-traffic UGC platforms in `HOST_MAIN_SELECTORS`
— each had a non-trivial selector contract that without a regression
net would slip on the next platform redesign.

### What changed

Three new fixture directories under `tests/fixtures/screenshot/`:

| Slug | URL pattern | Target selector | Why |
|------|-------------|-----------------|-----|
| `reddit/post` | `https://reddit.com/r/.../comments/...` | `shreddit-post` (modern web-component) | Pin the modern (2023+) Reddit layout. `[data-testid='post-container']` (2020-2023 SPA) and `.Post` (pre-2020) are still in the host map as fallbacks. |
| `zhihu/answer` | `https://zhihu.com/question/.../answer/...` | `.QuestionRichText` (question above) + `.AnswerCard` containing `.RichContent-inner` | Zhihu has 4 selectors for 4 page types — this fixture is the answer-page form. |
| `wechat/article` | `https://mp.weixin.qq.com/s/...` | `#js_content` (canonical body id) | Style H's most-cited source. Decoy `.qrcode_box` (follow-button area) must not win — that crop would look like an ad. |

All 3 follow the same synthetic-minimal-HTML + decoy-siblings pattern.
Auto-discovery picks them up; no test-file edits needed.

### Tests

407 (parametrized: 4 platforms × 2 + 1 sanity) → 424
(7 platforms × 2 + 1 sanity).

Total: **424 passing** (was 418 — +6 new, no regressions).

### Coverage status

`HOST_MAIN_SELECTORS` has 15 entries. After v1.6.21: **7 covered**
(github, hn, stackoverflow, x, reddit, zhihu, wechat). Remaining 8:
twitter (alias of x — selector identical), npmjs, weibo×2,
xiaohongshu×2, youtube, bilibili, medium, arxiv. Future batch
candidates.

### Spec

`docs/superpowers/specs/2026-05-20-screenshot-e2e-snapshot-tests.md`
— Phase 2 in progress 7/15.

---

## [1.6.20] - 2026-05-21 — OpenAI gpt-image-1 provider (B7 Phase 2) + screenshot-e2e CI fix

### Why

v1.6.17 shipped the `ImageProvider` protocol with two built-ins
(Minimax + Gemini). Phase 2 is the proof that the abstraction actually
buys new-provider velocity: adding OpenAI gpt-image-1 should be a
single subclass + one `register()` line + no edits to dispatch loops.
This release is exactly that — net code added is one class, one
registration, one fallback-chain append.

This also unblocks **D2 (English-language output)**: the Minimax key
is hard to get for English-market users, the Gemini key has its own
regional quirks, OpenAI gpt-image-1 is the universally available
option.

Also bundled: a CI fix for v1.6.19's lean install (was missing
`requests`, broke the new screenshot-e2e workflow on first run).

### What changed — B7 Phase 2

**New provider class** in `scripts/image_providers.py`:

- `OpenAIImageProvider` — POST `https://api.openai.com/v1/images/generations`
- Registered as `name = "openai"`, model `openai-gpt-image-1`
- `is_configured()` honors `OPENAI_API_KEY` env var + `openai_api_key`
  in env.json (parity with Minimax + Gemini conventions)
- Aspect-ratio → OpenAI size mapping for `1:1` / `16:9` / `4:3` / `9:16`
  (gpt-image-1 supports 1024×1024 / 1536×1024 / 1024×1536)
- `_openai_model()` strips the `openai-` namespace prefix before
  hitting the API (`openai-gpt-image-1` → `gpt-image-1`) — keeps the
  fallback-chain entry unambiguous
- Handles both b64_json (gpt-image-1 default) and hosted URL fallback
  shapes

**`scripts/config.MODEL_FALLBACK_CHAIN`** now ends in
`openai-gpt-image-1`. Minimax stays at index 0 (headline default); the
Gemini block stays in the middle. A user with only `OPENAI_API_KEY`
gets a chain of just `["openai-gpt-image-1"]` after
`filter_chain_by_available_keys` — no wasted attempts on missing
providers.

**`scripts/setup_dependencies.py`** (doctor):

- New `check_openai_api_key()` returns `warn` (not `block`) when
  missing — OpenAI is optional, the pipeline works without it.
- `check_network_reachability()` extended to probe
  `https://api.openai.com/` when an OpenAI key is configured.
- `_NETWORK_PROBE_TARGETS` gets the OpenAI entry.

**Documentation**:

- `env.example.json` — adds `openai_api_key` placeholder.
- `ENV.md` — adds OpenAI to recommended config table + lists
  `openai-gpt-image-1` in the available-models block; calls out
  the auto-prune behavior of `filter_chain_by_available_keys`.

### Tests

+11 new in `tests/test_image_providers.py`:

- Protocol conformance for OpenAIImageProvider
- Registry resolution (`for_model("openai-gpt-image-1").name == "openai"`)
- `is_configured()` env var + env.json parity (3 tests)
- `configured_providers()` includes openai when key set
- `filter_chain_by_available_keys` returns only `["openai-gpt-image-1"]`
  when only OPENAI_API_KEY is set
- `generate()` raises RuntimeError on missing key
- `generate()` raises RuntimeError on HTTP 4xx (401 mocked)
- `generate()` raises NoImageDataError on empty `data:[]` response
- `generate()` strips the `openai-` namespace prefix from the model
  name before hitting the API + maps `16:9` → `1536x1024`

`tests/test_config.py::test_model_defaults_remain_stable` updated:
now pins the headline default (`minimax-image-01` at index 0) AND the
new tail (`openai-gpt-image-1`), without locking the exact length.

**Total**: 418 passing (was 407 — +11 new, no regressions).

### What this enables

Phase 3 (self-hosted provider — Stable Diffusion via Automatic1111
or Replicate) follows the same pattern. Phase 4 (per-provider config
namespacing) is the hygiene pass once 4+ providers are registered.

D2 (English-language output): users now have a universal-availability
image backend that doesn't require a Chinese-market Minimax key or a
regional Gemini key. Style guides + lint patterns are still CJK-centric
— that's the next D2 dependency.

### Bundled fix: screenshot-e2e CI

`.github/workflows/screenshot-e2e.yml` failed its first run on v1.6.19
because the lean install (`pytest pillow playwright`) was missing
`requests` — `scripts/screenshot_tool.py` imports it at module top
and `sys.exit(1)` on miss. Added `requests pyyaml` to the install line.
The workflow now passes on the same fixture set v1.6.19 added.

### Spec

`docs/superpowers/specs/2026-05-20-multi-provider-image-abstraction.md`
— Phases 1-2 closed; Phases 3-4 still queued.

---

## [1.6.19] - 2026-05-21 — Screenshot E2E in CI + 3 more platform fixtures (B3 Phases 2-3)

### Why

v1.6.18 shipped the foundation (one fixture + auto-discovery infrastructure)
but the test only ran locally — no CI signal. Two follow-ups close that:

1. **Phase 3 (CI wiring)**: new `.github/workflows/screenshot-e2e.yml`
   so PRs touching `screenshot_tool.py` or fixture files actually exercise
   the e2e suite before merge. The workflow runs on `pull_request` +
   `push: main`, scoped via `paths:` so unrelated PRs don't burn CI
   minutes. Playwright Chromium is cached across runs (~120 MB only
   re-downloaded on Playwright version change).
2. **Phase 2 batch 1 (platform coverage)**: 3 more fixtures so the e2e
   suite isn't a one-platform proof-of-concept. Auto-discovery means
   no test-file edits needed — drop a fixture dir, the test runs.

### What changed

**New CI workflow** (`.github/workflows/screenshot-e2e.yml`):

- Triggers: `pull_request` + `push: main` + `workflow_dispatch`, scoped to
  `scripts/screenshot_tool.py` / `tests/fixtures/screenshot/**` /
  `tests/test_screenshot_e2e.py` / `tests/fixtures/_screenshot_e2e_helpers.py` /
  the workflow file itself.
- `concurrency: cancel-in-progress` per ref — new commits cancel
  pending runs.
- Caches `~/.cache/ms-playwright` keyed on `scripts/requirements.txt`
  hash; cache miss → `playwright install --with-deps chromium`;
  cache hit → `playwright install-deps chromium` (idempotent, ~10s,
  covers system-library drift between cached browser and CI image).
- Lean Python deps: `pytest pillow playwright` only — no full
  `scripts/requirements.txt` (Gemini SDK / tenacity / etc. not
  needed for the hermetic e2e suite).

**README badges**: added both `Plugin Layout Smoke` and
`Screenshot E2E` workflow status badges to the project header.

**3 new platform fixtures** under `tests/fixtures/screenshot/`:

| Slug | URL pattern | Target selector | Why |
|------|-------------|-----------------|-----|
| `stackoverflow/question` | `https://stackoverflow.com/questions/.../...` | `#question` (preferred) / `#mainbar` (fallback) | Pins selector ORDER — `#question` should win over `#mainbar` when both exist. `#sidebar` is the decoy. |
| `hn/item` | `https://news.ycombinator.com/item?id=42` | `.fatitem` / `tr.athing` | HN's table-based layout (Arc HTML); `.fatitem` wraps /item pages, `tr.athing` is the home-page row form. |
| `x/status` | `https://x.com/.../status/...` | `article[data-testid="tweet"]` / `[data-testid="tweet"]` | Path-sensitive: `suggest_selector` only returns a selector for `/status/` URLs (profile pages → viewport screenshot). Two tweet articles in fixture test "first match" semantics. |

All synthetic — minimal HTML reproducing the load-bearing DOM shape
without committing 100 KB+ vendor CSS captures. Each ships
`<slug>.html`, `<slug>.expected.json`, `SOURCE.txt`. See
`tests/fixtures/screenshot/README.md` for the capture procedure.

### Tests

**Total**: 407 passing (was 401 — +6 new e2e parametrized tests,
+3 platforms × 2 tests each, no regressions).

### What this enables

Phase 2 continues additively: 11 more `HOST_MAIN_SELECTORS` entries
to cover (npmjs, twitter alias, reddit, weibo×2, xiaohongshu×2,
zhihu, mp.weixin, youtube, bilibili, medium, arxiv). Each is a
fixture dir + parametrize-list pickup — no further infra work.

Phase 4 (maintenance doc consolidation into CONTRIBUTING.md) is the
last open piece.

### Manual follow-up (not in this commit)

Per spec §6 OQ #5: make `screenshot-e2e.yml` a required check for
`main` branch protection. This is a GitHub admin setting, not
something the workflow file controls.

---

## [1.6.18] - 2026-05-20 — Screenshot E2E snapshot test foundation (B3 Phase 1)

### Why

`scripts/screenshot_tool.HOST_MAIN_SELECTORS` ships per-platform CSS
selectors for 15 hosts (GitHub, Stack Overflow, X, Reddit, HN, Weibo,
Zhihu, WeChat, YouTube, Bilibili, Medium, arXiv, …). Five consecutive
releases (v1.4.17 - v1.5.6) fixed framing / anchor / selector
regressions in this dict — there was no regression net beyond
`tests/test_screenshot_crop.py`, which only checks dict-lookup
plumbing, not "does the selector actually match a real DOM."

Each user-reported screenshot bug was the only feedback signal.

### What changed

New test infrastructure under `tests/fixtures/screenshot/`. The
foundation pieces (Phase 1 of the 4-phase spec
`docs/superpowers/specs/2026-05-20-screenshot-e2e-snapshot-tests.md`):

- **`tests/fixtures/_screenshot_e2e_helpers.py`** — Playwright
  `route.fulfill()` handler that serves a fixture HTML file inline
  while the page URL stays canonical (e.g. `https://github.com/example/repo`).
  This is what lets `screenshot_tool.suggest_selector(url)` /
  `main_content_selectors_for_host(url)` still resolve "github.com"
  against the fixture. Also includes a `FixtureServer` (stdlib
  `ThreadingHTTPServer`) for any future test that needs local hosting
  without the route trick.
- **`tests/fixtures/screenshot/github/`** — the Phase 1 fixture:
  - `repo-readme.html` — synthetic, minimal HTML with the same DOM
    shape github.com uses (target `article.markdown-body` + decoy
    `.file-tree` / `.sidebar-meta` / `.AppHeader` siblings that must
    NOT win selection).
  - `repo-readme.expected.json` — schema_version 1: url_pattern,
    fixture_html ref, expected_selector_candidates,
    expected_first_match, bbox tolerances, anchor_keywords,
    is_404_expected. The contract every fixture follows.
  - `SOURCE.txt` — provenance (origin, date, author).
- **`tests/fixtures/screenshot/README.md`** — fixture-capture
  procedure + maintenance protocol (PR-A captures new HTML, PR-B
  updates the production selector — never both in the same change).
- **`tests/test_screenshot_e2e.py`** — parametrized over every
  discovered fixture. Three tests per fixture:
  1. `test_selector_resolves_via_host_map` — selector lookup logic
     (no browser; fast pre-check).
  2. `test_selector_matches_dom_with_route_redirect` — full Playwright
     headless flow: `page.goto(url)` → routed fixture → selector
     match + bbox-within-tolerance assertion.
  3. `test_fixtures_discovered_at_least_one` — sanity check that
     the parametrize list isn't empty (would otherwise silently skip
     every test if the fixture dir were broken).

The whole module skips gracefully when Playwright Chromium isn't
installed (CI installs via `shot-scraper install`; doctor warns).

### Architecture note: route.fulfill vs route.continue_

The spec §3.2 originally sketched `route.continue_(url=local_url)` to
rewrite the request URL to localhost. Playwright rejects this with
"New URL must have same protocol as overridden URL" — security guard
against https→http downgrade. Implementation uses `route.fulfill()`
instead: serves the fixture HTML inline as the response body, page
URL stays canonical. The risk listed in spec §5.2 turned out to be a
real one, and the fix is recorded here for future fixture work.

### Tests

**Total**: 401 passing (was 398 — +3 new e2e, no regressions).

### What this enables

Phase 2 (platform coverage): add one fixture dir per
`HOST_MAIN_SELECTORS` entry. Each fixture is auto-discovered — no
edits to `test_screenshot_e2e.py` needed. ~30 min per platform.

Phase 3 (CI): new workflow file. Caches Playwright Chromium between
runs.

Phase 4 (maintenance doc): consolidate the protocol from the fixture
README into CONTRIBUTING.md.

### Spec

`docs/superpowers/specs/2026-05-20-screenshot-e2e-snapshot-tests.md`
— Phase 1 contract closed; Phases 2-4 still queued.

---

## [1.6.17] - 2026-05-20 — `ImageProvider` protocol + registry (B7 Phase 1)

### Why

Adding a third image-generation backend (OpenAI gpt-image-1, Stable
Diffusion, Flux, …) required edits in 5+ files in lockstep:
`generate_and_upload_images.py` (`_generate_minimax_image*`,
`startswith("minimax")` dispatch), `nanobanana.py` (`_generate_single_*`,
mirrored dispatch), `config.filter_chain_by_available_keys` (hardcoded
`prefix == "minimax"` / `"gemini"` branches), `setup_dependencies.py`
(per-provider preflight). Each addition was one more `if`-branch in
each file. Phase 1 lays down the abstraction so future providers are a
single subclass + `register()` call.

This is the contract phase — **net-zero behaviour change** for current
Minimax + Gemini users. Phases 2 (OpenAI), 3 (self-hosted SD /
Replicate), and 4 (per-provider config namespacing) build on it.

### What changed

New module **`scripts/image_providers.py`**:

- `ImageProvider` Protocol (`@runtime_checkable`) — three required
  methods (`model_names()`, `is_configured()`, `generate()`) and one
  attribute (`name`). Errors normalized to `NoImageDataError`
  (recoverable, try next model) vs `RuntimeError` (hard fail).
- Registry: `register()`, `unregister()`, `for_model()`,
  `configured_providers()`, `all_providers()`.
- `MinimaxProvider` — HTTP body extracted from
  `_generate_minimax_image_with_options` (byte-for-byte identical
  HTTP shape).
- `GeminiProvider` — SDK call extracted from
  `nanobanana._generate_single_model` (string-prompt path; edit mode
  with PIL Image inputs still goes through the legacy SDK path in
  `nanobanana` because the protocol doesn't model image-edit yet).
- Built-in registrations at module import time.
- `_load_env_json()` consults `config._user_config` when available so
  tests that monkey-patch `config._user_config` continue to see the
  same source of truth.

**Call-site refactors**:

| File | Before | After |
|------|--------|-------|
| `generate_and_upload_images.py` `_generate_minimax_image*` | 80-line HTTP duplicates | Thin shims that call `MinimaxProvider().generate(...)` |
| `generate_and_upload_images.py:902` main loop | `if current_model.startswith("minimax"):` | `provider = for_model(current_model)` + `provider.name == "minimax"` check |
| `nanobanana.py:210` `_generate_single_model` | Inline SDK call | Routes string-prompt path through `GeminiProvider`; preserves edit-mode SDK call |
| `nanobanana.py:250` `_generate_single_minimax` | Inline HTTP | Routes through `MinimaxProvider` |
| `nanobanana.py:295` `generate_image` chain loop | `if startswith("minimax")` (twice) | Registry lookup + provider-name check |
| `config.py` `filter_chain_by_available_keys` | Hardcoded `prefix == "minimax"`/`"gemini"` branches | `for_model(m) is not None and p.is_configured()` |

The shim names (`_generate_minimax_image_with_options`,
`_generate_single_minimax`, etc.) **stay importable at the same paths**
so existing tests that `mock.patch.object(mod, "...")` keep working
without modification (`test_images_cli.py`, `test_image_parallel_backoff.py`).

### Tests

**New**: `tests/test_image_providers.py` (27 tests covering protocol
conformance, registry lifecycle, `is_configured()` env-var/env.json
parity, `configured_providers()` filtering, registry round-trip with
`filter_chain_by_available_keys`, provider error semantics
(HTTP 4xx → RuntimeError, missing image bytes → NoImageDataError),
non-overlapping model_names across providers).

**Updated**: `tests/test_filter_chain.py` switched from
`importlib.spec_from_file_location` reload to canonical `import config`
+ adds `import image_providers` so the registry's `is_configured()`
sees the same `config._user_config` patches the tests apply.

**Total**: 398 passing (was 371 — +27 new tests, no regressions).

### What this enables

Phase 2 (OpenAI): one new class `OpenAIImageProvider` in
`image_providers.py` + one `register(OpenAIImageProvider())` line. No
edits to `generate_and_upload_images.py`, `nanobanana.py`, or
`config.filter_chain_by_available_keys`. The doctor preflight picks it
up via the registry automatically (when that helper migrates in
Phase 4).

### Spec

`docs/superpowers/specs/2026-05-20-multi-provider-image-abstraction.md`
— Phase 1 contract closed; Phases 2-4 still queued.

---

## [1.6.16] - 2026-05-20 — unify personal-anchor regex (B21)

### Why

`scripts/review_selfcheck.py` had two separate personal-anchor regexes
that had drifted in scope:

- `check_rule_5` inline (after v1.6.14 B15 broadening): ~30 verbs +
  `我自己` + extras (`踩过`, `本机实测`, `从经验看`, `我们最后`,
  `这次我`).
- `PERSONAL_VOICE_REGEX` at line 933 (used by Rule 17 sub-check A —
  first-person density per tone tier): only ~10 verbs, plus 2 that
  check_rule_5 didn't have (`猜`, `生产环境.*?本人`).

Result: a sentence like `我接 agent 项目` counted as personal voice in
Rule 5 but not in Rule 17 — same intent, two contradicting answers
from two rules in the same file. The agent that fixed B15 flagged
this drift; B21 closes it.

### What changed

New module-level constant `PERSONAL_ANCHOR_REGEX` at the top of
`scripts/review_selfcheck.py` (right after the other regex
constants). The union of both old regexes:

- All ~30 verbs from check_rule_5 (post-v1.6.14)
- `猜` and the broader `生产环境.*?(?:我|本人)` from Rule 17's old
  regex
- All non-`我` anchors from check_rule_5 (`踩坑`, `踩过`, `实测`,
  `本机实测`, `实测下来`, `我的(?:经验|理解|做法)`,
  `从.{0,6}经验看`, `我们最后`, `这次我`)

`check_rule_5` now calls `PERSONAL_ANCHOR_REGEX.findall(body)` —
inline regex removed. `PERSONAL_VOICE_REGEX = PERSONAL_ANCHOR_REGEX`
kept as an alias for backward-compat (Rule 17's existing call site +
any external imports continue to resolve).

### Behaviour note: Rule 17 sub-check A will fire less often

Broadening Rule 17's matcher means more articles meet the
first-person density threshold (2 / 3 / 6 per 800 chars for neutral /
casual / opinionated). That's intended — the old narrow regex was
causing false-positive Rule 17 warnings on articles that did use
first-person anchors that simply weren't in the verb list.

The tone-calibration thresholds were tuned in v1.4.18 against the
narrower regex; they may need re-calibration. The backlog already
tracks this as **B11** (v2 tone-threshold recalibration from
collected data — requires 20+ articles of `tone-calibration.jsonl`
to land). No threshold change in this release.

### Tests

No new tests added — the new constant is exercised by the existing
21 tests in `tests/test_rule_5_personal_anchor.py` +
`tests/test_tone_resolution.py`. All pass (371 total in full suite,
same as v1.6.15).

Regex parity verified:

- 10/10 broadening cases match (`我接 / 我跑通 / 本机实测 / 我猜 /
  从过去经验看 / 生产环境本人 / 我们最后 / 这次我 / 踩过`)
- 0/4 false-positive cases still don't match (`我是开发者 / 我国 /
  他在做实验 / 我们刚开始`)
- `PERSONAL_VOICE_REGEX is PERSONAL_ANCHOR_REGEX` → True (alias)

### Closes

- B21 from `docs/research/2026-05-20-feature-candidates.md`

## [1.6.15] - 2026-05-20 — verify must WebFetch official sources (B22)

### Why this exists

The v1.6.13 e2e test article (Gemini 3.5 Flash) shipped two facts —
`"289 tokens/sec"` and specific `$1.50/$9` pricing — that, when
audited post-write via WebFetch against Google's official blog,
TechCrunch, and llm-stats, **didn't appear in any T0 source**. Both
came from WebSearch *snippets* used as the de-facto fact source. The
pipeline's verify stage was only running URL HEAD checks (200/404),
not extracting verbatim content. Pure tool-usage gap: snippets are
summaries, not ground truth.

### What changed

**`skills/verify/SKILL.md`** — new mandatory **Step 1.5: Official Source
Fact Extraction**. Procedure:

1. From requirements' `_trusted_sources`, pick every entry with
   `tier ∈ {T0, T1}`.
2. For each, call `WebFetch(url, prompt=fact_extract_prompt)` —
   *not* WebSearch.
3. Save the structured output as a markdown sidecar at
   `<article_dir>/_extracted_facts.md`, one `## T<tier> — <url>`
   section per source, verbatim bullets.

Includes a topic-aware fact-extraction prompt template that asks
WebFetch to: extract verbatim figures, name benchmarks with their
scores, list availability channels, list pricing if disclosed, and
**explicitly mark "NOT present" when a commonly-cited figure is
missing from the source body** — absence is itself a finding.

**`skills/write/SKILL.md`** — new mandatory **Fact source contract**
section in Inputs. Specifies:

1. When `_extracted_facts.md` exists, that's the **primary fact
   source** for all figures, quotes, prices, benchmarks. WebSearch
   snippets and prior-knowledge memory are explicitly demoted.
2. Headline figures absent from the sidecar must be **omitted or
   hedged** (e.g. `"按 llm-stats 收集到的数据为 ..."`), never
   restated as authoritative.
3. "NOT present" markers in the sidecar are signal — don't claim
   official disclosure of figures that the source body doesn't
   actually include.
4. When the sidecar is missing (draft/quick mode bypasses verify),
   write must add a description-frontmatter note flagging
   unverified-fact status. Intentional friction.

### Cost / cache

WebFetch is harness-cached 15 min per URL — repeated runs within the
window cost nothing. Across runs, the sidecar file itself is the
persistent cache; delete it to force re-extraction.

### Closes

- B22 from `docs/research/2026-05-20-feature-candidates.md`
- The "289 tokens/sec" fact integrity gap surfaced by the v1.6.13
  Gemini-3.5 e2e test article on 2026-05-20.

### Tests

No new automated tests — this is a prompt-engineering change in two
SKILL.md files; the contract is enforced at runtime by Claude reading
the SKILL.md. Layout smoke test passes (10/10), full suite passes
(369/371, 2 pre-existing env failures unchanged).

## [1.6.14] - 2026-05-20 — three review/lint precision fixes (B14 + B15 + B16)

All three discovered while running the v1.6.13 orchestrator pipeline
end-to-end on a real article (Gemini 3.5 Flash 发布解读). Each one
forced the author through an unnecessary edit cycle for a false
positive. Three small precision fixes; one release.

### B14 — `check_rule_6` is now writing-style-aware

Generic "≥2 code blocks per section" conflicted with the canonical
style table in `skills/write/SKILL.md` which defines:
- A 教程 → 3 code blocks
- B 分享 / E 资讯 / G 观点 → **1 code block**
- C 深度 → 5+
- D 评测 / F 复盘 / H 爆料 → 2 (matches old default)

Style B/E/G articles previously got 4 false-positive shallow-section
flags by design. Fixed by adding `STYLE_CODE_BLOCK_THRESHOLD` dict at
the top of `scripts/review_selfcheck.py`, reading `writing_style` from
frontmatter, and applying the per-style threshold. Default (style
missing/unknown) remains 2 — fully backwards compatible. The `details`
string now surfaces `style=X, threshold=N` for easy debugging.

### B15 — `check_rule_5` personal-anchor regex covers natural verbs

The old regex matched 10 verbs after `我` (`我(?:在|曾|的|会|用|选|踩|测|最后|发现)`).
Natural Chinese tech writing uses many more — `我接 / 我做 / 我跑 / 我自己 /
我之前 / 我后来 / 我跑通 / 我意识到` etc. Authors had to restructure
sentences purely to satisfy the regex.

Expanded to ~30 verbs + new non-`我` anchors (`踩过`, `本机实测`,
`实测下来`, `从经验看`, `我们最后`, `这次我`, `我的(?:经验|理解|做法)`).
Confirmed false-positive safety: `我是开发者` / `我国` / `我们`
(without `最后`) / `他在做实验` all still do NOT match.

`PERSONAL_VOICE_REGEX` at line ~888 (used by Rule 17 sub-check A)
was intentionally left untouched — unifying both into one constant
is logged as B21 in the backlog.

### B16 — Scope-aware ASCII gate

New `scripts/ascii_gate.py` — thin CLI that reuses rule_14's existing
scoping logic (only flags ASCII inside non-executable code blocks via
`box ≥ 5` OR `box ≥ 2 AND arrow ≥ 2` thresholds). `_BOX_CHARS`,
`_ARROW_CHARS`, `_EXECUTABLE_LANGS` imported from `review_selfcheck.py`
— no duplication of the underlying detector.

`skills/write/SKILL.md` Step 6 (and the parallel Step 4a check)
updated from `grep -nE '│|├|...'` to
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ascii_gate.py <article>`. Exit
codes: 0 clean, 1 violations, 2 file missing.

Result: inline rhetorical arrows (`需要更强推理 → 上 Pro` as prose)
no longer trip the gate. Genuine ASCII diagrams inside a `text`-tagged
code block still do.

### Tests

24 new tests across 3 files:

- `tests/test_rule_6_style_aware.py` (11) — style A/B/C/E/G coverage
  + default + unknown + lowercase normalization + intro-chapter scaling
- `tests/test_rule_5_personal_anchor.py` (5) — 23 positive samples,
  7 negative samples, 3 integration tests
- `tests/test_ascii_gate.py` (8) — prose arrow PASS, text-block FAIL,
  bash-block PASS, no-ASCII PASS, missing-file / no-arg / box+arrow
  combo / single-box below threshold

**369 total tests pass** (was 345 + 2 pre-existing
`test_screenshot_upload.py` failures unrelated to this work — env-
specific, mock-shadow issue when PicGo is actually on PATH).

### Discovered during implementation

The agent doing the work noted that `PERSONAL_VOICE_REGEX` and the
`check_rule_5` inline regex have drifted — different verb lists, both
incomplete, used by different rules. Logged as **B21** in
`docs/research/2026-05-20-feature-candidates.md` for a future
unification pass.

### Closes

- B14, B15, B16 from `docs/research/2026-05-20-feature-candidates.md`
- All three surfaced as concrete pain points in the v1.6.13 e2e test
  article ("Gemini 3.5 Flash 发布解读" written via the orchestrator).

## [1.6.13] - 2026-05-20 — per-section tone override syntax (B10, v1)

### New — `<!-- tone:X -->...<!-- /tone -->` regions in articles

Authors can now override the article-level tone for a span of prose:

```markdown
默认 neutral 行文。

<!-- tone:casual -->
这一段切换到 casual,lint 会按 casual 词表重写
（比如「在某种意义上」→「其实」）。
<!-- /tone -->

回到默认 neutral。
```

Closes the v2 candidate listed in
`docs/superpowers/specs/2026-05-07-tone-system-design.md:474`.

### Parser — `config.parse_tone_regions(text, default_tone)`

Returns `[(start_line, end_line_exclusive, tone), ...]` covering every
line with no gaps. Semantics (v1, flat — no nesting):

- `<!-- tone:X -->` opens region X. Closes any previously-open region
  implicitly (so missing `/tone` doesn't leak the region forever).
- `<!-- /tone -->` closes the current region.
- Stray closers (no prior opener) are no-ops.
- Unknown tone names (not in `TONE_REGISTER_LEVELS`) are ignored —
  the marker is treated as plain text and no region is opened.
- Unclosed regions extend to EOF.
- Marker lines themselves use the **surrounding** tone (the markers
  are HTML comments, no prose to rewrite).

### Lint integration

`scripts/lint_article.auto_fix_text` now pre-builds rewrite tables for
all three tones (neutral / casual / opinionated), parses regions via
`parse_tone_regions`, and applies the matching tone's rewrites per
line. Behavior unchanged for articles without any tone markers
(every line resolves to the article-level tone). Region markers are
preserved verbatim in output (same convention as `<!-- lint:disable -->`).

### Known v1 limitation

`scripts/review_selfcheck.py` Rule 17 (Register Naturalness) still
uses article-level tone for **all** its density-based sub-checks
(first-person markers, strong-opinion sentences, summary phrases,
sentence-length variance). A `<!-- tone:opinionated -->` region inside
a neutral article will get its rewrites applied by lint, but Rule 17
won't yet treat the region's metrics differently. Region-aware Rule 17
metrics depend on whether they should be per-region thresholds or
weighted-average aggregations — punted to v2 pending calibration data.

### Tests

16 new tests (`tests/test_tone_regions.py`) cover:

- Parser: no markers, empty text, single region splits, multiple
  regions, implicit close via new opener, unclosed regions, unknown
  tone names ignored, stray closers harmless, default fallback to
  neutral, whitespace tolerance
- Lint integration: default tone outside region, region tone inside
  region (wins over article tone), marker preservation, unclosed
  region doesn't crash, invalid region name falls back to article tone

**347 total tests pass** (was 331).

### Closes

- B10 from `docs/research/2026-05-20-feature-candidates.md`
- Tone spec v2 candidate #1

## [1.6.12] - 2026-05-20 — plugin-layout smoke test in CI (B6)

### New — `tests/test_plugin_layout.py` (10 tests) + GitHub Actions workflow

Closes the v1.6.2 / v1.6.3 / v1.3.4 fragility pattern: bugs that don't
break individual scripts but break the plugin's **layout contract**
(command files in wrong place, frontmatter versions out of lockstep,
referenced scripts missing, marketplace.json drift from plugin.json).
Pre-v1.6.12, none of these were CI-enforced — every drift surfaced as
a user report after the release shipped.

**Tests pinned**:

- `test_no_commands_nested_under_article_craft_subdir` — would have
  caught v1.6.2 (the original `commands/article-craft/doctor.md`
  placement that registered as the doubled `/article-craft:article-craft:doctor`).
- `test_every_skill_has_matching_command` — 1:1 invariant from CLAUDE.md.
- `test_every_command_either_wraps_a_skill_or_is_in_allowlist` — orphan
  catcher; adding a non-skill command requires explicit allowlisting
  in the test (forces code-review).
- `test_all_skill_versions_match_plugin_json` — would have caught
  v1.3.4 (marketplace.json stuck at 1.1.0 for months).
- `test_marketplace_json_agrees_with_plugin_json` — same lockstep
  check from the bump_version side, pinned at PR time.
- `test_skill_name_matches_directory` — `skills/X/SKILL.md` frontmatter
  `name:` must be `article-craft:X`.
- `test_referenced_scripts_actually_exist` — every
  `${CLAUDE_PLUGIN_ROOT}/scripts/X.py` mentioned in any markdown
  (skills, commands, CLAUDE.md, INSTALL.md, README.md) must resolve.
- Frontmatter validity: command `description:` present, skill
  required-fields complete, plugin.json shape sane.

**GitHub Actions workflow** `.github/workflows/smoke.yml` runs the
above on every PR and push to main. Minimal deps (pyyaml + pytest);
~5 second job. Concurrency-grouped so new pushes cancel stale runs.

### Fix — 14 command files had invalid YAML frontmatter

The test caught a **real layout bug** the moment it ran:
`argument-hint:` values with multiple unquoted square brackets were
being read by YAML as malformed flow-sequence syntax. For example,
`commands/series.md` had:

```yaml
argument-hint: [create|next|status|validate|audit|collection] [series-file-path]
```

YAML reads the first `[...]` as a flow sequence, then expects `,`
or `]` — and finds `[` instead, raising `ParserError`. The repo had
been shipping these invalid YAML frontmatters since v1.5.x because
Claude Code's plugin loader uses a more lenient parser than strict
`yaml.safe_load`. Strict YAML is now the canonical contract; 14 files
fixed by quoting the value:

```yaml
argument-hint: "[create|next|status|validate|audit|collection] [series-file-path]"
```

**331 total tests pass** (was 321).

### Closes

- B6 from `docs/research/2026-05-20-feature-candidates.md`

## [1.6.11] - 2026-05-20 — test coverage for evidence / utils / bump_version (B9)

### Tests — 42 new across the three biggest no-test scripts

Before: `scripts/evidence.py` (356 LOC), `scripts/utils.py` (317 LOC),
and `scripts/bump_version.py` (254 LOC) had **zero** matching
`tests/test_*.py`. `SmartDirectoryMatcher` in particular is the
publish-skill auto-placement engine — silently picking the wrong KB
folder is the kind of bug that wouldn't surface for releases. Bump
tooling was similarly unverified, despite being on the critical path
of every release.

New test files:

- **`tests/test_bump_version.py`** (12 tests): version arithmetic
  (major/minor/patch/explicit X.Y.Z), arity rejection, non-numeric
  part rejection, `parse_bump_arg` CLI validation, current-version
  semver shape, **plugin.json ↔ marketplace.json lockstep invariant**
  (would catch the v1.3.4 drift).
- **`tests/test_evidence_parse.py`** (14 tests): `parse_materials`
  bucket sorting (public / local / gated), section header
  variants in Chinese and English (`## 公开` / `## local` / `## 付费` /
  `## paywall`), `tier=T1`, quoted `note="..."` / `desc="..."` syntax,
  bullet prefix variants (`- ` / `* `), trailing-punctuation cleanup,
  unrecognized-section fallback to public.
- **`tests/test_utils_classes.py`** (16 tests):
  `SmartDirectoryMatcher` keyword / pattern / history rules,
  case-insensitivity, invalid-regex tolerance, cross-instance
  persistence, `learn_feedback` token extraction;
  `PlaceholderManager` construction / learn / suggest / recent-prompts
  cap / clear-history; singleton helpers for both.

**321 total tests pass** (was 279).

### Fix — `SmartDirectoryMatcher.get_rules()` now returns a deep copy

A real latent defect surfaced while writing test coverage:
`get_rules()` returned `self.rules.copy()` (shallow), sharing the
nested `keywords` / `patterns` / `history` containers with internal
state. A caller doing `rules["keywords"].clear()` would silently wipe
the matcher's rules. Fixed by switching to `copy.deepcopy`.

### Closes

- B9 from `docs/research/2026-05-20-feature-candidates.md`

## [1.6.10] - 2026-05-20 — self-check rules 12–15 reference entries (B12)

### Docs — closes the v1.6.4 doc debt

`references/self-check-rules.md` previously had prose entries for
rules 1–11 + 7b + 16 + 17 only. The v1.6.4 sweep updated the preamble
to acknowledge rules 12–15 were implemented but undocumented and to
point readers at the `check_rule_N` docstrings as the interim source.

This release fills the gap:

- **Rule 12 — Template Summary Detection**: full list of 6 regex
  patterns, line-bounded matching, bad/good replacement examples
  (lead with a concrete problem instead of "本文将…")
- **Rule 13 — Code Block Language Identifier**: state-machine scan,
  default-to-`text` auto-fix policy, common tag list
- **Rule 14 — ASCII Diagram in Non-Executable Code Blocks**:
  box/arrow character thresholds (`box ≥ 5` OR `box ≥ 2 AND arrow ≥ 2`),
  `_EXECUTABLE_LANGS` skip-list explained, side-by-side table comparing
  Rule 14 vs Rule 11 (where they overlap and where they don't)
- **Rule 15 — Orphan PROMPT Comments**: 2-line look-back detection,
  auto-fix policy (delete safely), common causes

The "Who enforces what" table at the top expanded from 12 rows to 18
(adds rules 12–17). Preamble doc-debt warning + "consult the docstrings"
pointer removed — every active rule now has a canonical reference entry.

279 tests still pass — pure documentation, no code change.

### Closes

- B12 from `docs/research/2026-05-20-feature-candidates.md`
- v1.6.4's "doc debt" item flagged in `references/self-check-rules.md`

## [1.6.9] - 2026-05-20 — auto-prune fallback chain by available API keys (B13)

### Fix — no more wasted Minimax attempts for Gemini-only users

Before: a user with only `GEMINI_API_KEY` (the default new-user state
since v1.6.0 made Minimax the headline default) saw the fallback chain
try `minimax-image-01` first **per image**, fail with an auth error,
then fall through to Gemini. Across a batch of N placeholders that was
N wasted Minimax attempts plus the latency / log-noise overhead.

After: `config.filter_chain_by_available_keys(chain)` prunes models
whose provider key isn't set. Minimax models need
`minimax_api_key` (env.json) or `MINIMAX_API_KEY` (env var); Gemini
models need `gemini_api_key` or `GEMINI_API_KEY`. Both call sites
(`generate_and_upload_images.py:864`, `nanobanana.py:308`) filter
through the helper after building the chain.

### Behaviour notes

- **Filtered chain empty** → callers raise `RuntimeError` with a clear
  fix hint instead of letting an empty loop silently succeed-zero or
  emit a confusing "all attempts exhausted" error.
- **Explicit `--model` dropped** → warning printed showing what fell
  back to. (User selected a model whose provider isn't configured —
  surface the override rather than silently overriding their choice.)
- **Unknown provider prefix** → passes through (forward-compat: future
  Qiniu / DALL-E / Flux entries get their own key check when wired up,
  not arbitrarily dropped by this filter).
- **Empty-string env.json key** treated as missing (matches the
  existing API-key-check semantics in `doctor.py`).

### Tests

10 new tests (`tests/test_filter_chain.py`) cover: both keys, only
Gemini (the headline scenario), only Minimax, neither, env.json-only,
env-var-only, chain order preservation, unknown-prefix pass-through,
empty-string-key handling, empty input chain. **279 total tests pass**
(was 269).

### Closes

- B13 from `docs/research/2026-05-20-feature-candidates.md` —
  originally surfaced as a side observation while documenting the
  Minimax default for a user question.

## [1.6.8] - 2026-05-20 — shared PicGo parser + Uploader protocol (B2)

### Refactor — canonical PicGo output parser in `scripts/uploaders.py`

Closes the v1.5.2-pattern fragility: previously
`screenshot_tool.upload_to_cdn` and
`generate_and_upload_images.upload_to_picgo` each had their own
duplicated line-scan + JSON-fallback heuristic for extracting a URL from
PicGo CLI output. v1.5.2 fixed one parser (the multi-line
`[PicGo INFO]` log case that silently broke screenshot uploads); the
other was a parallel implementation with subtly different defensiveness
that would have needed its own fix on the next regression.

Now both call sites delegate to a single
`scripts/uploaders.parse_picgo_output(stdout)`:

- Strategy 1: line scan for `http://` or `https://` (the real-world
  PicGo output shape — multi-line log + final URL line)
- Strategy 2: JSON fallback (`{"url": ...}` or `[{"url": ...}]`) for
  forward-compat with potential PicGo format changes
- Returns `None` if neither finds a URL — callers decide whether to
  raise (image-gen, fail-fast) or fall back to local path (screenshot,
  lenient)

Inline `line.startswith("http://")` parsing removed from both
`screenshot_tool.py` and `generate_and_upload_images.py`. Both files
now `from uploaders import parse_picgo_output`.

### New — `Uploader` Protocol (future extension point)

`uploaders.Uploader` is a `@runtime_checkable` Protocol with a single
`upload(local_path: str) -> str` method. Current uploader functions
(`upload_to_picgo`, `upload_to_s3`, `upload_to_cdn`) are intentionally
**not** refactored to instances yet — their callers have very different
error contracts (image-gen raises, screenshot returns local path) and
forcing them into one shape would force converting the retry-wrapped
PicGo flow and the lenient screenshot fallback, expanding scope beyond
what B2 demands. The protocol exists so future Qiniu / imgbb / SMMS
backends slot in cleanly via a `get_uploader()` factory rather than
adding more branches to `upload_image`.

### Tests

16 new tests (`tests/test_uploaders.py`):

- Parser behavior: real-world multi-line log, bare URL, http vs https,
  URL anywhere in lines
- JSON fallbacks: dict / list shapes, line-URL beats JSON when both
  present
- Failure modes: empty string, no URL anywhere, invalid JSON, dict
  without `url`, empty list, non-dict list head, non-string `url` value
- Uploader Protocol: `isinstance()` accepts correct shape, rejects wrong

All existing upload tests (`tests/test_screenshot_upload.py`,
`tests/test_share_card_upload.py`, `tests/test_images_cli.py`) pass
unchanged — the refactor preserves the public contracts.

**269 total tests pass** (was 253).

### Closes

- B2 from `docs/research/2026-05-20-feature-candidates.md`
- Pattern A1 (silent stub / stdout-pollution) from the same doc

## [1.6.7] - 2026-05-20 — share-card standalone skill (B4)

### New — `/article-craft:share-card` standalone skill

`scripts/share_card.py` (553 LOC, 10 platform presets, 7 color schemes)
was previously only reachable from the orchestrator pipeline's Step
3.4.5 — there was no way to regenerate cards for a published article
without rerunning the whole pipeline.

Promoted to a first-class skill at `skills/share-card/SKILL.md` with
top-level `commands/share-card.md` (single-prefix `/article-craft:share-card`
per the v1.6.3 convention). Same engine, just a standalone entry point
for post-publish card regeneration, brand-refresh batches, and color
tweaks without article-level changes.

The orchestrator still calls the same script directly — no behavior
change for the integrated pipeline.

### Skill count

13 → **14** child skills under `skills/` (orchestrator unchanged at 1).
README, INSTALL, scripts/README all updated.

## [1.6.6] - 2026-05-20 — cookie injection for headless screenshots (B1)

### New — Playwright cookie loading in `screenshot_tool`

Closes the v1.5.6 "Out of scope" item: login-walled platforms (HN-HTTPS,
Reddit, 知乎, 微博, 小红书 …) whose selectors landed in v1.5.5 now work
end-to-end from headless runs once a cookies file is configured.

The integration is deliberately format-agnostic — we consume
**Playwright-format cookies JSON** (the shape `BrowserContext.cookies()`
emits), so any extractor that produces it works: gstack
`setup-browser-cookies` skill, Playwright's own dump, browser extensions
like EditThisCookie, or hand-written.

**Configuration** (priority order):

1. CLI `--cookies PATH` (highest) or `--no-cookies` (disable)
2. env.json `browser_cookies_path`
3. Default `~/.cache/article-craft/cookies.json` (only if file exists —
   no behavior change for unconfigured installs)

**Format**: top-level JSON list, or `{"cookies": [...]}` wrapper. Each
entry needs `name` + `value` + (`url` or `domain`). Malformed entries
are skipped individually rather than failing the whole load.

**Safety**: Playwright filters cookies by domain at send time, so
loading the full jar for any screenshot is safe — only matching cookies
are sent. A bad cookies file logs a warning and screenshot continues
without cookies (not a fatal error).

### New — `--cookies` / `--no-cookies` CLI flags

Both `screenshot_tool.py screenshot` and `screenshot_tool.py batch`
accept the flags. ENV.md has a new "截图 cookie 注入" section with
format example and provenance notes. `skills/screenshot/SKILL.md` —
the "需要登录的页面" row in the avoidance table flipped from "跳过" to
the actual integration path.

### Tests

14 new tests (`tests/test_screenshot_cookies.py`) cover the three
helpers: `_resolve_cookies_path` (5 cases — disabled / explicit /
config / default-present / default-missing), `_load_cookies` (6 cases
— missing / invalid JSON / list / wrapped / wrong-shape / partial
skip), `_apply_cookies` (3 cases — empty / success / playwright error
swallowed). 253 total tests pass (was 239).

### Closes

- B1 from `docs/research/2026-05-20-feature-candidates.md`
- v1.5.6 CHANGELOG "Out of scope" deferral

## [1.6.5] - 2026-05-20 — doctor extended checks (B5)

### New — `env_json` check

`scripts/setup_dependencies.py` previously parsed `~/.claude/env.json`
through `_load_env_json()` which swallows `JSONDecodeError` and returns
`{}`. A single typo in env.json silently degraded every downstream
check (API keys, S3, PicGo override) without any user-visible signal.
The new `env_json` check surfaces this explicitly:

- **PASS** — file absent (optional) or parses cleanly
- **WARN** — file present but empty
- **BLOCK** — file present but invalid JSON (with line/col + fix hint)

### New — `plugin_root` check

Verifies `CLAUDE_PLUGIN_ROOT` (when set) points to an existing directory.
A typo or stale checkout silently broke scripts that join paths onto it.

- **PASS** — env var resolves to a real dir
- **WARN** — env var not set (script-relative fallback works for direct
  shell runs; Claude Code sets it automatically)
- **BLOCK** — env var points to a non-existent path

### New — `--network` flag for network reachability

`doctor.py check --network` adds an optional Minimax / Gemini host
reachability probe (HEAD with 3 s timeout each). Only probes hosts
whose API key is actually configured. Default `check` stays fast
(~1 s) — the network flag is opt-in to avoid blocking the orchestrator
preflight on a slow corporate proxy.

Default `doctor check` now runs **11** checks (was 9); with `--network`
it runs 12.

### Tests

10 new tests added (`tests/test_doctor.py`: env_json valid/invalid/
empty/missing, plugin_root unset/missing/valid, network excluded-by-
default / runs-with-flag / warns-no-keys / warns-unreachable). 239
total tests pass (was 228).

## [1.6.4] - 2026-05-20 — post-v1.6.3 doc sweep

### Fix — rule-count drift across docs (11 / 12 / 17 disagreement)

`scripts/review_selfcheck.py` implements **17** active rules
(`check_rule_1` through `check_rule_17`, dispatched at line 1076) — but
the canonical reference said "11 rules" in its preamble, `CLAUDE.md`
said "11", and `README.md` said "12". Synced all three to 17.

`references/self-check-rules.md` preamble updated to be honest about
the doc gap: full reference entries exist for rules 1–11, 16, 17, plus
the 7b degradation-aware variant; prose entries for rules 12–15 are
doc-debt and the preamble now points readers at the `check_rule_N`
docstrings in `scripts/review_selfcheck.py` until those entries land.

### Docs — `scripts/README.md` expanded

Was listing 6 of 17 `.py` files. Updated to include all 17, organized
by purpose (healthcheck, image generation, screenshot, publish, series,
lint/review, release tooling). Adds a "run the healthcheck" example
using `doctor.py`.

228 tests pass — markdown only, no Python changed.

## [1.6.3] - 2026-05-20 — flatten command directory + sync docs

### Fix — every sub-command now resolves as `/article-craft:<name>` (single prefix)

v1.6.2 fixed only the `doctor` command. The 13 other sub-commands
(`write`, `publish`, `series`, `review`, `lint`, `images`, `screenshot`,
`requirements`, `verify`, `verify-claims`, `evidence`, `youtube`,
`upgrade`) still sat under `commands/article-craft/` and resolved as the
nested `/article-craft:article-craft:<name>` for marketplace installs —
which contradicted every doc, README, and CLAUDE.md mention of the
intended single-prefix form.

Moved all 13 to the top level of `commands/`. The repo convention now
matches what users (and the docs) have always expected: one command file
per skill at `commands/<name>.md`, resolving as `/article-craft:<name>`.
`commands/doctor.md` (the v1.6.2 fix) and the new placement are now
consistent.

### Docs — synced to match reality

- `INSTALL.md` skill count corrected (11 → 13), tree updated to include
  `evidence/` and `verify-claims/`, scripts tree updated to include the
  v1.6.0 additions (`doctor.py`, `publish_plan.py`, `series_state.py`,
  `share_card.py`, etc.). The "单独使用" example block — which previously
  listed nonexistent commands like `/article-write` — now shows the real
  14 commands.
- `README.md` "Standalone Commands" block expanded from 8 to 14 entries
  (was missing `requirements`, `verify`, `evidence`, `series`, `publish`,
  `doctor`, `upgrade`). The "series" Workflow Modes row fixed
  (`/article-series` → `/article-craft:series`).
- `CLAUDE.md` "New skills" convention rewritten: new commands go at
  `commands/<name>.md` top-level (not `commands/article-craft/<name>.md`)
  with the why-it-matters explanation inline.
- `commands/doctor.md` self-explanation simplified (it no longer needs
  to call out its location as a special case — every command does this
  now).

228 tests pass — no Python code changed, this release is markdown only.

## [1.6.2] - 2026-05-19 — fix /article-craft:doctor command name

### Fix — doctor command moved to `commands/doctor.md`

v1.6.1 shipped the command at `commands/article-craft/doctor.md`, which a
plugin install registers as the nested `/article-craft:article-craft:doctor`
(`/article-craft:doctor` returned "Unknown command"). Moved the file to the
top level of `commands/` so it resolves as the intended `/article-craft:doctor`.

## [1.6.1] - 2026-05-19 — /article-craft:doctor command

### New — `/article-craft:doctor` slash command

`commands/article-craft/doctor.md` — a thin command wrapping
`scripts/doctor.py check`, so the runtime healthcheck (the same preflight
the orchestrator runs as its Step 0) has a standalone slash entry point.
Supports `--json`. No matching skill directory — `doctor.py` is a script,
not a skill — mirroring how `commands/article-craft/upgrade.md` wraps an
orchestrator mode.

## [1.6.0] - 2026-05-19 — doctor preflight, publish/series state scripts, pipeline hardening

The post-1.5.6 batch: three new deterministic helper scripts, broad
hardening of the image / screenshot / install paths, and a round of
review-driven fixes folded in.

### New — `scripts/doctor.py` runtime healthcheck

Unified preflight CLI (`doctor.py check [--json]`) that delegates to
`setup_dependencies.run_all_checks`, summarizes pass/warn/block counts,
and maps them to exit codes 0/1/2. Backs the orchestrator's "Step 0:
Preflight Dependency Check".

### New — `scripts/series_state.py` series state machine

`status` / `next` / `mark-published` / `validate` subcommands. The
`series` skill's modes 2/3/7 now delegate state handling here instead
of carrying their own ad-hoc logic. `next` returns full prev/next
navigation context. A documented `validate` mode (模式 7) was added.

### New — `scripts/publish_plan.py` publish planner

Single command with a `--dry-run` preview: KB auto-placement (via
`SmartDirectoryMatcher`), SHA-256 collision detection with timestamped
rename, and Style H sidecar (`_evidence.json` / `_harvest_menu.md`)
collection. The `publish` skill's Steps 1–3 now delegate to it.

### Config — KB directory names are no longer hardcoded

`config.kb_category_root()` / `config.kb_uncategorized_dir()` replace
the literal `02-技术` / `未分类` strings, overridable via env.json so a
fork with a differently-named KB tree works unchanged. `ENV.md` and
`env.example.json` updated.

### Fixes — review-driven

- `publish_plan.py`: planning is now side-effect-free — a `--dry-run`
  no longer creates directories; `mkdir` happens only on the executed
  run. The earlier `plan` / `apply` subcommand split (where `apply`
  silently re-computed the plan) was collapsed into one command so the
  preview and the executed run share a single code path.
- `series_state.py`: `mark-published` now fails loudly (exit 1,
  `error_code: series_row_not_found`) on an unknown `--index` instead
  of silently rewriting nothing and reporting success.
- `series_state.py`: dropped the unused `slug` parameter from
  `_article_filename`.

### Docs

- Purged the last stale `content-reviewer` references (`INSTALL.md`,
  `README.md`, `write/style-guide.md`, `orchestrator/SKILL.md`). The
  `content-reviewer` script was superseded long ago — review is
  self-contained (`review_selfcheck.py` + inline 7-dim scoring) — but
  these textual mentions had lingered.

228 tests pass.

## [1.5.6] - 2026-05-08 — robustness fixes from v1.5.5 e2e testing

End-to-end testing v1.5.5 across 14 platforms surfaced two robustness
issues that the unit tests didn't catch.

### Fix — selector candidate height floor: 400 → 100

`capture_screenshot` rejected any `suggest_selector` candidate whose
bounding box was <400px tall. The threshold was originally meant to
filter out tiny nav icons, but it also discarded legitimately short
main-content containers:
  - arxiv `#abs` is ~375px — silently dropped, fell through to
    full-page (1280×wide × very long).
  - Single tweets, short Reddit threads, etc. — same fate.

Lowered to 100px (matches `MIN_CONTENT_HEIGHT_PX`). E2E confirmed:
arxiv now produces a clean 1021×375 element screenshot.

### Fix — element-timeout fallback to viewport

`el.screenshot()` raises `PlaywrightError` when the element matches
but isn't stable/visible — common on lazy-loaded SPAs. YouTube hit
this consistently: `#meta` matched but mounted later, screenshot
timed out after 15s, entire run failed.

Wrapped the call in try/except: on timeout, fall back to
`page.screenshot(full_page=False)` (viewport) plus a warning. User
gets a working screenshot tagged `selector_used: "X (timeout →
viewport)"` instead of the whole pipeline failing.

E2E confirmed: YouTube watch page now produces a 1280×800 viewport
shot with the warning surfaced.

### Out of scope

Hard-network-blocked / aggressive-anti-bot platforms (HN via HTTPS,
Reddit / 知乎 / 微博 / 小红书 from headless) still need cookie
support to work end-to-end — that's a much bigger fix involving
`setup-browser-cookies` integration and is intentionally deferred.

166/166 tests pass.

## [1.5.5] - 2026-05-08 — multi-platform main-content selectors

User report after v1.5.4: anchor + auto-suggest still only had useful
entries for GitHub. On X / 微博 / 小红书 / 知乎 / 微信公众号 /
Reddit / HN / YouTube / B 站, screenshots fell back to viewport
mode, anchor scope fell through to the generic markdown-body family
(nothing matched), then to body-global (sidebar/header noise).

### Refactor

Pull all platform-specific selector knowledge into a single
`HOST_MAIN_SELECTORS` dict consumed by both `suggest_selector()`
and `capture_screenshot`'s anchor scope. Adding a new platform is
one entry; both code paths benefit immediately.

### New built-in coverage

| Category | Hosts |
|---|---|
| Code/dev | github.com, stackoverflow.com, npmjs.com |
| Western UGC | x.com + twitter.com, reddit.com, news.ycombinator.com |
| Chinese UGC | weibo.com, xiaohongshu.com + xhslink.com, zhihu.com, mp.weixin.qq.com |
| Video | youtube.com, bilibili.com |
| Long-form | medium.com, arxiv.org |
| Docs (generic) | `.markdown-body` / `.docs-content` / `.documentation` / `.main-content` |

`www.` prefix is stripped before matching; host substring match means
`x.com` covers `m.x.com` too.

### Configuration

env.json `screenshot_main_content_selectors` lets users add private
platforms or override built-ins when sites redesign:

```json
"screenshot_main_content_selectors": {
  "myblog.com": [".post-body"],
  "weibo.com":  [".New_Feed_Content_Container"]
}
```

User entries win over built-ins via host substring match.

### Tests

`tests/test_screenshot_crop.py` adds 22 cases: 14 per-platform
recognition tests (parameterized), www. stripping, unknown-host
empty-list, user-override-wins-over-builtin, user-override-for-new-host,
suggest_selector reading host map for video/zhihu, and the v1.5.4
guardrail (`main`/`article` must NOT be in GENERIC_CONTENT_SELECTORS).

166/166 tests pass.

## [1.5.4] - 2026-05-08 — anchor scope fix (followup to v1.5.3)

v1.5.3 added ANCHOR keyword scrolling but searched the whole
`document.body`. On GitHub repo pages the DOM order is header →
file tree → README → sidebar (Topics / About / Releases). If the
keyword existed anywhere outside the README (sidebar tag, file
name fragment, topic chip), tree-walker hit it first and scrolled
there. Screenshots came out showing file lists / commit history
instead of the README section the article was discussing.

User-visible repro on github.com/vectorize-io/hindsight:
  - `ANCHOR:TEMPR`        → README has no "TEMPR"; v1.5.3 scrolled to
                            commit list anyway. Now: doesn't scroll,
                            falls back to README top.
  - `ANCHOR:LongMemEval`  → README has "LongMemEval"; v1.5.3 scrolled
                            to a sidebar/file match. Now: scrolls to
                            the README's Memory Performance section.
  - `ANCHOR:memory bank`  → same story, now correct.

Fix: scope the tree walker to a prioritized list of content
containers: explicit selector → `article#readme` →
`article.markdown-body` → `.markdown-body` → `.docs-content` etc.
Bare `<main>` and bare `<article>` are intentionally excluded
because GitHub wraps both file tree and README in them.

If the keyword exists on the page but only outside the content
containers, return a `no_scroll` hit so we can warn instead of
silently misleading. If the keyword isn't on the page at all,
keep the default screenshot position.

144/144 tests still pass.

## [1.5.3] - 2026-05-08 — screenshot framing: anchor keywords + 900px cap

User report after the v1.5.2 verification run: screenshots came out at
1400px tall and didn't reflect what the surrounding article paragraph
was actually discussing. Two-part fix.

### Fix — Default screenshot height capped at 900px

`screenshot_tool.upload_to_cdn` already worked from v1.5.2, but
`capture_screenshot` had no height cap on element screenshots — a
GitHub README selector matched the entire 1400px+ `article#readme`
container and that's what got returned. `--max-height` defaulted to
`0` (no cap), so the only thing keeping screenshots reasonable was
manual user intervention.

`--max-height` now defaults to **900px** (≈ one viewport). The
`crop_to_max_height` call moved from `batch_capture`'s outer loop
into `capture_screenshot` itself, so CLI / batch / programmatic
callers all benefit equally. Verified: same GitHub repo URL that
produced 756×1400 yesterday now produces 445×900.

`--max-height 0` still disables the cap if needed.

### Feat — `ANCHOR:` placeholder syntax wires up keyword scrolling

The `article_keywords` parameter on `capture_screenshot` had been
declared in the signature for many releases but never actually used
inside the function — the local variable was set then ignored. Now
it drives a `page.evaluate` walk that scrolls the page to the first
text node containing any of the keywords (skipping elements <50px
tall so we don't anchor on sidebar nav links), then takes a viewport
screenshot at that scroll position. The result: the image shows the
part of the page that's relevant to the surrounding article
paragraph, not the page header.

New placeholder syntax (documented in both `skills/screenshot/SKILL.md`
and `skills/write/SKILL.md`):

```
<!-- SCREENSHOT: URL ANCHOR:kw1,kw2 -->     # scroll to first kw
<!-- SCREENSHOT: URL FOLD -->               # ≤ viewport height (800)
<!-- SCREENSHOT: URL MAX_HEIGHT:1200 -->    # custom height cap
```

CLI gains `--fold` (== `--max-height 800`). `--keywords` already
existed; now it actually does something.

The `write` skill is told to default-include `ANCHOR:` when emitting
a SCREENSHOT placeholder — at write time the skill already knows what
each section is about, so picking 1-3 keywords from the surrounding
paragraph is essentially free.

### E2E verification (`https://github.com/vectorize-io/hindsight`)

| Mode | Output | What it proves |
|---|---|---|
| no flags | 445×900 | Default cap kicks in |
| `--keywords TEMPR` | 1280×800, `anchor_kw_used: "tempr"` | Scrolled to TEMPR section + screenshot is viewport-sized at that scroll |
| `--fold` | 642×800 | Viewport-only screenshot |

144/144 tests pass (+5 new in `tests/test_screenshot_crop.py`).

## [1.5.2] - 2026-05-08 — orchestrator pipeline fixes from real-world run

After a full `/article-craft:orchestrator` run on a real article
yesterday (3025-char Hindsight intro), four pain points surfaced.
This release closes all four:

### Fix — `screenshot_tool.upload_to_cdn()` parsed picgo wrong

`upload_to_cdn()` assumed picgo emitted JSON, but picgo's actual stdout
is multi-line `[PicGo INFO]` log lines + a final bare URL. The old
parser called `json.loads(stdout)` (always failed) then checked
`stdout.startswith("http")` on the multi-line blob (also always
failed) and returned the local path — so callers silently treated
every screenshot as "upload failed". During the Hindsight run, both
screenshots had to be uploaded by hand and the CDN URL pasted into
the article manually.

The matching parser in `generate_and_upload_images.upload_to_picgo()`
was already doing this right (line-by-line scan, JSON fallback).
Aligned `upload_to_cdn` to the same strategy. Also promoted
`import shutil` and `import subprocess` to the top of
`screenshot_tool.py` so the function is unit-testable.

Adds `tests/test_screenshot_upload.py` (6 cases): multiline log +
bare URL, JSON dict / list output, no URL → local path, no picgo on
PATH, nonzero exit.

### Fix — `review_selfcheck.py` couldn't be invoked as a direct script

`from scripts.config import ...` (package-style import) at the top
of the file required the repo root to be on `sys.path`, so
`python3 scripts/review_selfcheck.py article.md` always failed with
`ModuleNotFoundError: No module named 'scripts'`. The Usage docstring
explicitly advertised that invocation, and the review skill kept
working around it with `cd` + `python3 -m scripts.review_selfcheck`.

Now the file inserts its own directory into `sys.path` before the
import, so all three modes work:
1. `python3 scripts/review_selfcheck.py article.md`
2. `python3 -m scripts.review_selfcheck article.md`
3. `from scripts.review_selfcheck import check_rule_17` (pytest)

### Feat — `write` skill self-checks word count before save

The Hindsight run wrote ~2000 chars on first pass against a
3000-4000 target, then needed 5 rounds of orchestrator-driven
`Update` calls to expand. New **Step 5.5: Word Count Self-Check**
in `skills/write/SKILL.md` does the count + targeted expansion
inside the write skill, with explicit guidance against padding via
restated transitions. Loops up to 2 rounds; if still under min,
saves and surfaces the shortfall in the handoff output instead of
spinning forever.

### Feat — frontmatter `author` field, resolved at write time

`share_card` auto-skipped on the Hindsight article with "missing:
author" because `write`'s frontmatter template literally never
emitted the field. New `config.author_name()` resolves
`env.json user_name > git config user.name > "Anonymous"`. The
write template now includes `author:` and shows how to fill it
inline. `env.example.json` and `ENV.md` document the new
`user_name` env field.

139/139 tests pass (+7 new: 6 screenshot, 1 author).

## [1.5.1] - 2026-05-08 — hardcoding audit + publish preflight

### Refactor — Eliminate hardcoded paths and brand strings

Project-wide audit (12 files) to remove hardcoded paths, model lists,
personal CDN domains, and `/tmp` literals. Behavior is unchanged on a
default install; the audit only opens up customization seams.

**`scripts/config.py` — four new APIs:**

- `cache_dir() -> Path` — single source for `~/.cache/article-craft/`,
  honoring `ARTICLE_CRAFT_CACHE_DIR`. `screenshot_tool.py`,
  `write_verify_cache.py`, and `review_selfcheck.py` now all flow through
  it (previously only the last one did).
- `TEXT_MODEL` — separates the prompt-expansion text model used by
  `nanobanana.py --enhance` (`gemini-2.0-flash` default) from the
  image-only `MODEL_FALLBACK_CHAIN`. Override via env.json
  `gemini_text_model`.
- `VERIFY_CDN_WHITELIST` — the CDN allowlist that used to live as a
  hardcoded `grep -v` filter inside `skills/write/SKILL.md`. Default
  excludes per-author personal domains. Override via env.json
  `verify_cdn_whitelist`.
- `share_card_logo()` — resolves card logo text from env.json >
  `.claude-plugin/plugin.json` `name` > `"article-craft"`. Forks can
  re-brand without source edits.

**Configuration template:** new `env.example.json` at repo root,
referenced by `ENV.md` (the template `install.sh` had been copying from
`~/.claude/env.example.json` was never in this repo until now).

**DRY cleanup:**

- `nanobanana.py` and `generate_and_upload_images.py` no longer carry
  parallel copies of `MODEL_FALLBACK_CHAIN` — both import from
  `config`. Standalone `try/except ImportError` fallbacks are kept.
- `generate_and_upload_images.py` model-chain construction switched from
  the buggy `[user_model, gemini-3.1-flash, gemini-2.5-flash]` (which
  silently dropped `gemini-3-pro` whenever the user picked a non-pro
  default) to `[user_model] + canonical chain` with order preserved.

**Cross-platform `/tmp`:**

- Six `/tmp/...` literals migrated to `tempfile.gettempdir()`:
  `VerificationCache` default, `gemini_probe.jpg`, `verify-tmp.txt`,
  `utils.py` demo, plus the cache-dir helpers above. Same effective path
  on Linux, now portable to Windows.

**De-personalization:**

- `skills/write/SKILL.md`: example URL `file.costalong.com` → generic
  placeholder `your-cdn.example.com` with note about
  `verify_cdn_whitelist`. Coverage-warning shell snippet now reads the
  whitelist from `config.VERIFY_CDN_WHITELIST` instead of hardcoding it.
- `scripts/share_card.py`: card-footer logo HTML uses
  `share_card_logo()` instead of the literal `"article-craft"`.

**Stale comment fixes:** `config.py` references to a non-existent
`~/.article-craft.conf` corrected to `~/.claude/env.json`. The
`screenshot_tool.py` doc comment citing
`/tmp/article-craft-verify-cache.json` corrected to the actual
`~/.cache/article-craft/verify-cache.json` path.

**Tests:** 8 new `test_config.py` cases cover defaults + env-json
overrides for all four new APIs (`cache_dir`, `TEXT_MODEL`,
`VERIFY_CDN_WHITELIST`, `share_card_logo`). Total: 132/132 pass.

### Added — Pre-publish placeholder gate

Closes the "article published with unresolved `<!-- IMAGE/SCREENSHOT/PROMPT/HARVEST: -->`
placeholders" silent-failure mode. Caught during round4 e2e testing —
running image generation with `--no-upload` produced an article that the
script reported as "1 placeholder replaced" (only the screenshot got a
local path) while 4 IMAGE placeholders remained intact, but the publish
skill would happily move that half-baked file into the knowledge base.

**New CLI subcommand**: `pipeline_state.py check-publish-ready --article PATH`

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/pipeline_state.py check-publish-ready \
    --article /abs/path/article.md
```

Exit codes:
- `0` — clean (no `<!-- IMAGE/PROMPT/SCREENSHOT/HARVEST: -->` placeholders remain)
- `1` — unresolved placeholders detected (BLOCK publish)
- `2` — article path doesn't exist

Output: JSON on stdout for machine consumption, human-readable summary
on stderr listing per-kind placeholder counts and likely cause.

**Wiring**: `skills/publish/SKILL.md` adds Step 0 — runs the preflight
gate before any directory matching or file movement. Block-with-detail
on placeholder presence; never override.

### Tests

`tests/test_pipeline_state.py` adds `CheckPublishReadyTests` (6 tests):
- clean article returns 0 + ready=true
- IMAGE/PROMPT placeholder pair blocks with both counted
- SCREENSHOT placeholder blocks
- HARVEST placeholder (Style H) blocks
- multi-kind article reports each kind separately
- nonexistent article returns exit 2

Total suite: 128 passed (122 baseline + 6 new).

### Why this layer at publish, not earlier

The pipeline already has earlier checks (write Step 7 handoff, verify-claims
post-write) but those happen *before* image generation. The preflight gate
is the last line of defense — it runs *after* all generation/upload stages
and catches any silent failure (--no-upload, CDN error, manual edit drift)
right before the article enters the knowledge base. Cheap to run (single
regex scan of the article body) and fail-loud.

### Validated

- `python3 -m pytest tests/test_pipeline_state.py -v` → 12 passed
- Manual smoke test on round4-final.md (clean) → exit 0
- Manual smoke test on round4-test-run.md (--no-upload artifact) →
  exit 1, BLOCK with "IMAGE: 4, PROMPT: 4"

---

## [Unreleased] - 2026-05-08 (image variety, v1.4.19 dev)

### Added — Per-position image variation (Layer A + C)

Closes the "image style too monotone" feedback. Two compounding causes:

1. **Within-article**: `image-guide.md` locked all 4 design tokens (palette
   / preset / mood / background) so sibling images shared camera, composition
   and framing. Visually they looked like 4 stickers from the same sheet.
2. **Cross-article**: `STYLE_TO_VISUAL` mapped 80% of articles to 2-3 presets
   with default palettes (Style A → S1 → blue+teal) — article-after-article
   looked like one branded series.

**Layer A (rule rewrite)** — `skills/images/image-guide.md` § 风格一致性
规则 split into:

- **全篇必锁**: visual_style preset, color family, mood keywords, background
- **鼓励变化** (per image): camera angle, composition, subject framing,
  visual density

Plus new "镜头/构图轮转表" documenting which directives the script injects
per image position (cover → establishing wide / centered; img 2 →
three-quarter perspective / rule-of-thirds; etc.).

**Layer C (script injection)** — `scripts/generate_and_upload_images.py`:

- `CAMERA_ROTATION` (6-tuple) + `COMPOSITION_ROTATION` (6-tuple)
- `vary_prompt_for_position(base_prompt, image_index, total)` — appends
  `Camera: ...` + `Composition: ...` based on image position
- `_CAMERA_KEYWORDS_RE` / `_COMPOSITION_KEYWORDS_RE` — detect author
  override per axis and skip injection (author wins)
- `vary_prompts: bool = True` on `generate_and_upload_batch` and
  `generate_and_upload_parallel`
- `--no-vary-prompts` CLI flag for opt-out

`skills/write/SKILL.md` updated to tell writers NOT to manually add
Camera/Composition (script handles it).

**Verified end-to-end (2026-05-08)**: 6 images with the same base PROMPT
plus varying Camera/Composition directives → Gemini produced visibly
different framings (vertical stack / wide w/ breathing / horizontal flow
/ detail dashboard / stair-step / 3D isometric) while keeping locked
palette + preset + background uniform across all 6.

**Tests**: `tests/test_image_variation.py` (11 tests) — index rotation,
locked-prefix preservation, author-override skip, partial override,
structural invariants. Total suite: 118 passed.

### Why not Layer B / D yet

Layer B (expand from 7 → 12-15 visual presets) and Layer D (cross-article
style rotation cache) are **deferred**. A + C cover within-article
monotony — the higher-impact complaint. Cross-article variety needs more
presets first (B), and shuffling needs presets to shuffle from. Decide
after 5-10 real articles run through A + C.

### Validated

- `python3 -m pytest tests/ -q` → 118 passed (107 baseline + 11 new)
- 6-image visual A/B confirmed Gemini responds to directives
- `--no-vary-prompts` opt-out path verified

---

## [Unreleased] - 2026-05-08 (calibration v1.1)

### Changed — Rule 17 threshold calibration after 4-article pilot

Drove a 4-article pilot (1 Style A neutral PostgreSQL tutorial / 1 Style D
casual Bun-vs-Node review / 1 Style G opinionated Cursor hot take / 1
deliberately-AI-flavor LangChain article) and discovered two real-world
miscalibrations in v1's starting thresholds:

- **`TONE_THRESHOLDS["neutral"]["max_summary_phrases"]: 5 → 3`.** v1's
  ceiling of 5 let the deliberately-AI-flavor article through with only 2
  warnings (passed under "warnings don't block" semantics). v1.1's ceiling
  of 3 catches that article with a clearer signal. Unit tests updated:
  `test_neutral_allows_3_summary_phrases` (was `test_neutral_allows_5_*`)
  + new regression test `test_neutral_fails_on_4_summary_phrases_v1_1_regression`.

- **`TONE_THRESHOLDS["casual"]["first_person_per_800w"]: 4 → 3`.** Real
  casual blogs in the pilot hovered at first-person density 2–3 per 800
  chars. v1's threshold of 4 was rejecting genuinely casual writing that
  read fine. Lowered to 3 to match the observed distribution.

### Fixed — Lint replacement preserves trailing punctuation

Casual + opinionated tier lexical rewrites (`在某种意义上`, `可以看到`,
`本质上`, `值得注意的是`, `综上`, `显然`) used regex `[，,]?` to consume
the optional trailing comma but the replacement string didn't put it
back. Result: `"值得注意的是，LangChain..."` → `"这地方注意LangChain..."`
(missing comma → ungrammatical join).

Switched to named capture group `(?P<sep>[，,]?)` + back-reference
`\g<sep>` in the replacement. Comma-when-present is preserved; no phantom
comma added when original had none. Tests: 3 new in
`tests/test_lint_tone_aware.py` `CommaPreservationTests`.

### Documented — Rule 17 warning-vs-error semantics

Expanded `references/self-check-rules.md` § Rule 17 with explicit
guidance on what `passed=True` with multiple warnings actually means.
Rule 17 is **detection-only with three signal levels**; warnings feed
the review skill's Phase 2 7-dimension AI-trace score, they don't gate
publication on their own. Calibrated articles can ship with warnings;
articles drowning in warnings will lose enough 7-dim points to trigger
revision. v2 may upgrade severe sub-check violations to `error`.

### Validated

- `python3 -m pytest tests/ -q` → 107 passed (103 baseline + 4 new
  calibration tests)
- 4-article pilot data preserved at `~/.cache/article-craft/tone-calibration.jsonl`
  (108 records pre-pilot, 12 added during the cross-tier matrix run)
- v2 calibration target: re-run on 20 published articles before further tuning

### Fixed (also rolled in)

- `tests/test_lint_article.py::test_main_honors_frontmatter_tone` had a
  hardcoded path to the now-removed `feat/tone-system` worktree. Replaced
  with `Path(__file__).resolve().parent.parent` so the test runs from any
  repo location (worktree or main).

---

## [Unreleased] - 2026-05-08

### Added

- **Tone system: three-tier register-aware de-AI infrastructure (`neutral` / `casual` / `opinionated`).** New `--tone` CLI flag on `/article-craft` with `flag > frontmatter > writing-style default` precedence; `STYLE_TO_TONE_DEFAULT` maps Style A/C/E → neutral, B/D/F → casual, G/H → opinionated. New `Rule 17: Register Naturalness` in `scripts/review_selfcheck.py` runs four sub-checks (first-person density / strong-opinion presence / summary-phrase ceiling / sentence-length CV) against tier-specific thresholds in `scripts/config.py TONE_THRESHOLDS`. `scripts/lint_article.py` refactored from a single rewrite list into tier-stacked `TONE_LEXICAL_REWRITES` with Vale-style severity (info / warning / error), inline `<!-- lint:disable rule_id -->` regions, and a max-pass oscillation guard. Calibration JSONL written to `~/.cache/article-craft/tone-calibration.jsonl` (opt-out via `ARTICLE_CRAFT_TONE_CALIBRATION=false`) seeds the v2 threshold-tuning pass. Closes the "register too uniform" feedback loop without coupling to AI-detection scoring tools.

### Changed (BREAKING)

- **`scripts/lint_article.py --fix` at default `tone=neutral` no longer auto-deletes paragraph-leading `首先 / 其次 / 最后 / 另外 / 此外 / 同时`.** Those replacements moved to `casual` and `opinionated` tiers. Articles previously relying on lint to strip these at neutral now keep them — set `tone: casual` in frontmatter to restore the old behavior, or run `--tone=casual` on the CLI.
- **Several v1.4.17 red-flag patterns are no longer auto-replaced at neutral**: `综上所述`, `总而言之`, `值得注意的是`, `显然` moved to opinionated/casual tiers; `实际上`, `事实上`, `众所周知`, `不难看出` are no longer in any tier (consider adding back to neutral via `TONE_LEXICAL_REWRITES["neutral"]` if your articles relied on them).

### Why

Closes the "register too uniform" pain captured in `docs/superpowers/specs/2026-05-07-tone-system-design.md`. Reading-feel for AI articles wasn't a structural problem (Rule 5/6 already managed structure) but a register one — every paragraph in the same formal book voice. The tone system gives authors three discrete dial positions and threads them through prevent (write skill) → detect (Rule 17) → fix (lint_article.py) — same architecture as the existing 16 rules, just orthogonal.

Prior-art research (blader/humanizer, hylarucoder/ai-flavor-remover, Vale prose linter, GPTZero burstiness, Zhihu Chinese de-AI consensus) informed the design; rationale and citations in the spec.

### Validated

- `python3 -m pytest tests/ -v` → 103 passed (43 baseline + 60 new across the tone system)
- 4 golden fixture integration tests (neutral / casual / opinionated + cross-tier check)
- Existing 43 baseline tests preserved (regression-protected throughout 30-task plan)
- Calibration JSONL writes verified in temp-dir test
- 16-commit history on `feat/tone-system` branch with two-stage review per task

## [Unreleased] - 2026-05-07

### Added

- **`_ParallelRateLimitCoordinator` — worker-coordinated backoff for the images parallel path.** Closes the long-standing technical debt called out in `CLAUDE.md` § Known design debt: "images parallel path still lacks coordinated backoff". The sequential `generate_and_upload_batch` path got per-image batch-level backoff (30/60/120s + jitter) in v1.4.3, but `generate_and_upload_parallel` workers had no shared rate-limit awareness — when one worker hit `RateLimitExhausted` from the model fallback chain, all the other workers continued hammering the API.

  The new coordinator gives parallel workers a shared pause window. When any worker sees `RateLimitExhausted`, it calls `signal_rate_limit(attempt)` which sets/extends a pool-wide `_pause_until` deadline; every other worker calls `wait_if_paused()` before its next `generate_image()` call and blocks until the deadline expires. Multiple concurrent signals coalesce — only the longest end-time persists, so concurrent 429s on the same wave do not stack. Per-image attempt counters preserve sequential-equivalent semantics: each image gets up to `len(BATCH_BACKOFF_DELAYS_SEC)` retries against the shared schedule, then gives up and the worker moves on with `error_type="rate_limit_exhausted"`.

  `process_single_image` inside `generate_and_upload_parallel` now wraps its `generate_image()` call in a retry loop with explicit `RateLimitExhausted` handling ahead of the generic `Exception` catch — preserving existing handoff for `FileNotFoundError`, `subprocess.TimeoutExpired`, and unknown failures (single-shot fail, no retry).

  New module-level constant `BATCH_BACKOFF_JITTER_MAX_SEC = 5.0` parameterizes the jitter range so tests can pin both delays and jitter to deterministic values. The coordinator resolves both constants at construction time (when args are `None`) so `monkeypatch` of the module attributes flows through.
- **`scripts/lint_article.py` — lightweight auto-fix for mechanical AI-style patterns.** New 484-line script invoked by `skills/lint/SKILL.md` for Rule 5 fixes. Removes roadmap filler (`本文将...` / `接下来我们将...` / `下面分别...`), empty judgement wrappers (`可以看到` / `本质上` / `从这个角度看` / `某种意义上` / `回到问题本身`), repetitive paragraph starters (`首先` / `其次` / `另外` / `此外` / `同时`), high-confidence red-flag words (`赋能` / `一站式` / `链路`), splits overlong hook paragraphs, deletes engagement-style closings, and drops standalone trailing `## 参考资料` sections. Intentionally conservative — never touches code blocks, HTML comment placeholders (`<!-- IMAGE: -->`, `<!-- HARVEST: -->`), Markdown headings, or image/link syntax lines. Reports high-risk sections (consecutive 3 paragraphs without concrete anchors, consecutive summary-tone paragraphs without anchors) that cannot be safely auto-fixed.
- **Rule 5 template-cadence detection** in `references/self-check-rules.md` and `scripts/review_selfcheck.py`. Review now flags: roadmap filler appearing 2+ times, adjacent paragraphs sharing the same starter class (transition-heavy, sequence-heavy), articles with fewer than 2 concrete anchors (numbers, version strings, command snippets, file paths, benchmark output, exact error text), any 3 consecutive body paragraphs with 0 concrete anchors, and sections with 2 consecutive summary-tone paragraphs with 0 anchors. Adds `SEQUENCE_OPENERS`, `EMPTY_JUDGEMENT_PHRASES`, `SUMMARY_TONE_PHRASES`, `ROADMAP_FILLER_PATTERNS` constants. Concrete-anchor heuristic checks for backticks, version strings, multi-segment paths, and error/metric tokens.
- **Test suites for lint and review extensions.** `tests/test_lint_article.py` (10 tests) covers auto-fix coverage, code-block / placeholder safety, hook splitting, trailing-reference deletion, high-risk-section reporting, and `--fix` writeback. `tests/test_review_selfcheck.py` (7 tests) covers Rule 5 template-cadence flagging, summary-tone detection, anchor-density heuristic, code-block break handling, personal-voice pass case, and Rule 6 / Rule 12 boundary cases.
- **`tests/test_image_parallel_backoff.py`** (13 tests) covers the parallel rate-limit coordinator: idle state, schedule exhaustion, jitter bounds, coalescing concurrent signals, pool-wide blocking under `wait_if_paused()`, longer-wave extension over a still-active shorter pause, plus two end-to-end tests of `generate_and_upload_parallel` with monkeypatched `generate_image` (one retries through a 429 then succeeds, one exhausts the schedule and gives up). Whole suite (43 tests across all files) runs in 1.57s.

### Changed

- **`skills/lint/SKILL.md` Step 4 now invokes `lint_article.py` for Rule 5.** Documents the exact `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lint_article.py --article PATH --fix` command and which mechanical patterns it touches. Adds a "High-Risk Sections" review queue to the report format for sections the auto-fix flagged but did not modify.
- **`skills/write/SKILL.md` Step 7 explicitly delegates content-quality rules to `review`.** Adds a 职责分工 block stating that Step 7 only checks downstream-skill handoff contracts (placeholder format, IMAGE / HARVEST validity), and that content-quality rules (red-flag words, template cadence, chapter depth, ending strength) are owned by `review` skill Phase 1's 11 self-check rules. Removes the duplicated instruction to call `review_selfcheck.py` from write.
- **`skills/write/style-guide.md`** picks up the same anti-template-cadence guidance so the writer model has the rule visible at generation time, not just at review.
- **`README.md`** gains an Architecture Overview section: two-layer architecture (skills = workflow, scripts = execution), module relationship tree, responsibility-by-directory table, and key runtime component glossary.

### Why

Closes both technical debt items called out in `CLAUDE.md` § Known design debt:

1. _Self-check rules duplicated across three skills._ `references/self-check-rules.md` was already canonical, but `write/SKILL.md` Step 7, `lint/SKILL.md`, and `review/SKILL.md` Phase 1 each re-stated slices of it in prose, so updating the red-flag list meant remembering three places. Now `write` defers to `review`, `lint` calls the deterministic auto-fix script, and the prose in each skill points at `references/self-check-rules.md` by rule number instead of restating it.
2. _Images parallel path lacks coordinated backoff._ The sequential path got 30/60/120s + jitter batch backoff in v1.4.3. The parallel path now matches via `_ParallelRateLimitCoordinator`. Workers no longer stampede a rate-limited Gemini quota.

### Validated

- `python3 -m pytest tests/ -q` → 43 passed in 1.57s
- Coordinator integration tests use patched `BATCH_BACKOFF_DELAYS_SEC=(0.05, 0.05)` + `BATCH_BACKOFF_JITTER_MAX_SEC=0.0` for deterministic, fast runs (<2s)
- Existing tests (`tests/test_config.py`, `tests/test_pipeline_state.py`, `tests/test_verify_claims.py`) unaffected.

## [Unreleased] - 2026-04-22

### Fixed

- **Gemini can't render Chinese text in images — articles silently produced garbled glyphs.** Two articles shipped with CDN cover images full of distorted/misspelled Chinese characters because `<!-- PROMPT: -->` lines asked Gemini to render menus, magazine covers, calligraphy scrolls, etc. with embedded Chinese text. Triple-layer fix:
  1. **Write-stage rule** in `skills/write/SKILL.md` section 3f: a new "⛔ 硬禁止：PROMPT 里绝对不能要求 Gemini 渲染任何可读文字" block with a 5-line bad/good matrix and the mandatory tail constraint `No readable text anywhere, no letters, no numbers, no labels, no captions, no logos.` Also documents the self-contradiction case (don't use Gemini to illustrate another model's text-rendering ability).
  2. **Style-guide rule** in `skills/images/image-guide.md` "Prompt 写作规则": expanded rules #5-6 from one-line soft guidance into a full hard-block with examples of visual-substitution patterns (menu → menu silhouette with column layout, calligraphy → brush-stroke marks without characters, etc.).
  3. **Self-check Rule 16** in `scripts/review_selfcheck.py` and `references/self-check-rules.md`: new automated detector that scans every `<!-- PROMPT: -->` line for (a) any CJK character `[一-鿿぀-ヿ가-힯]` — hard fail; and (b) common "render text X" instructions like `text "…"`, `title "…"`, `headline "…"` unless the prompt also contains `no readable text` / `no letters` / `no labels` as a defusing whitelist. Rule count upgraded from 15 to 16.

### How it was caught

User shipped two articles (`chatgpt-image-2-prompt-handbook.md`, `kimi-k2-6-from-k25-upgrade.md`) where cover + rhythm image CDN URLs came back with mangled Chinese characters. The old image-guide had one line ("不要写文字内容") but it wasn't enforced anywhere downstream, so Gemini still got prompts asking for things like `magazine cover titled "VOL.08 慢生活"`, `menu with items "招牌菜 ¥68"`, `calligraphy scroll saying "静"`. Rule 16 now catches these pre-generation.

### Validated

- `review_selfcheck.py` on the fixed text-free articles → Rule 16 PASS ✅
- Synthetic test with CJK in PROMPT → Rule 16 FAIL with specific character samples in the suggestion
- Synthetic test with `text "X"` + `no readable text` whitelist → Rule 16 PASS (correctly defused)

## [1.4.17] - 2026-04-16

### Fixed

- **Screenshot skill was capturing entire scrolling pages instead of the relevant content.** Two compounding bugs:
  1. `suggest_selector()` for `github.com/<user>/<repo>` returned `#repo-content-pjax-container` (the entire repo content pane incl. file tree + sidebar = basically full page). Changed to `"article#readme, #readme, article.markdown-body, .markdown-body"` — try in order, pick the first that exists and is ≥ 400px tall.
  2. When `suggest_selector()` returned an empty string (no pattern matched), `capture_screenshot()` fell through to `full_page=True`. For an unknown URL with no writer-supplied selector, this silently produced a giant scrolling capture. Changed default to `full_page=False` (viewport only / above-the-fold) so the image stays manageable and obviously "the main thing" on that page.
- **Candidate selector iteration.** Previously `.split(",")[0]` used only the first comma-separated candidate; if it didn't match, the code stopped. Now iterates all candidates, rejecting any whose bounding box height is < 400px so too-narrow elements (e.g., a single feature card) don't get picked as the "content zone" on landing pages.
- **Extended doc-pattern match list** in `suggest_selector()`: adds `official.`, `/guide/`, `/reference/`, `/getting-started`, `/quickstart`, `/tutorial`, `/manual` so product docs sites like `mempalaceofficial.com/guide/hooks.html` resolve to `article, main, ...` instead of falling through to the viewport fallback.

### Added

- **Recommended-selectors table in `skills/write/SKILL.md`** Section 3f — writer now has an explicit reference for which selectors to pair with which URL types (GitHub repo → `#readme`, docs site → `main` or `article`, Twitter status → `[data-testid="tweet"]`, etc.).

### How it was caught

User reported that a published tutorial article (`mempalace-local-memory-tutorial.md`) had two screenshots captured as entire scrolling pages instead of the key sections described in their captions ("README with scam alert + benchmark", "docs homepage hero"). Live end-to-end rescreenshot validated:
- `github.com/MemPalace/mempalace` → `article.markdown-body` (3597px tall — the full README, matching caption)
- `mempalaceofficial.com` → viewport (1280×800 hero section — the actual landing page, not a feature card)

### Takeaway

Any "smart selector" path that returns nothing or a null-match needs an opinionated narrow-ish default (viewport beats full-page for unattended captures). Writer guidance table prevents this from recurring as a quiet regression.

## [1.4.16] - 2026-04-16

### Fixed

- **`rehost` and `expand-harvest` subcommands: stdout no longer polluted by upload progress.** Every CDN upload (PicGo / S3) prints "📤 上传图片: ..." / "✅ Upload successful" / etc. to stdout. `expand-harvest` also writes its JSON result to stdout, so downstream `| jq` / automated consumers got an interleaved text+JSON stream that couldn't be parsed. Both CLI dispatchers now wrap their work in `contextlib.redirect_stdout(sys.stderr)` — progress goes to stderr (still visible when you're running interactively), and stdout is guaranteed pure JSON.

### How it was caught

Running a real end-to-end Style H integration test (3 HARVEST placeholders → rehost → upload → substitute) against a real WeChat Style H article URL. The article.md output was correct — all 3 CDN URLs present, GIF preserved as `.gif`, cover right — but piping `expand-harvest` stdout to `jq` in the test harness failed with `JSONDecodeError: Expecting value`. The end-to-end test is what surfaced it; unit tests with mocked upload never saw the noise.

### Takeaway

Any subcommand that emits JSON for machine consumption needs to keep stdout clean. Rule: progress → stderr, result → stdout. Checked by `subcommand | jq . > /dev/null && echo ok`. Other candidates in the repo (not fixed here — no JSON output yet): `check`, `screenshot`, `harvest` already either go to stdout intentionally or write to files; `batch` writes to a dir; `harvest-menu --json` doesn't invoke upload paths.

## [1.4.15] - 2026-04-16

### Added

- **Publish copies Style H sidecars to the KB.** New publish Step 3.5: if `_evidence.json` or `_harvest_menu.md` exist alongside `article.md` in the source directory, `cp` them into the same target subdirectory in the KB. Preserves the full HARVEST picking context so a future `/article-craft --upgrade /kb/path/article.md` can resume operations (re-rehost a rotted CDN URL, regenerate menu, verify placeholders) without the user chasing down the original materials dir.
- **`pipeline_state.py` infers Style H from sidecars** in heuristic mode. When no state file exists (post-publish cleanup, or articles predating v1.4.2), `_scan_article()` now also checks for `_evidence.json` and `_harvest_menu.md` next to the article. `_stage_done_heuristic("evidence", scan)` returns true when the sidecar is present; `_compute_missing()` treats `writing_style="H"` as inferred in that case, so the evidence stage stays in the `want` list instead of being pruned.
- **Publish summary shows sidecar status** (`_evidence.json`, `_harvest_menu.md` — copied / none).

### Why

The "11 releases from one WeChat article" streak shipped evidence, menu, preflight, and drop-in placeholders — all fantastic at write time. But publish silently stranded them in the source dir. Net effect: published Style H articles couldn't be re-upgraded. Fixing it is one `cp` loop in publish + two small helpers in `pipeline_state.py`.

### What this unlocks

- `/article-craft --upgrade /kb/2026-04/article.md` on a published Style H article now finds `_evidence.json` via heuristic, correctly identifies Style H, keeps `evidence` stage as done, and re-runs only what's genuinely stale (e.g., a broken CDN URL).
- Re-running `harvest-menu --evidence /kb/path/_evidence.json` still works post-publish (file is where the article is).
- `expand-harvest` still works because `--evidence` defaults to article dir.

### Design note

Policy split:
- **`.article-craft-state.json`**: pipeline-run-scoped, deleted on publish (v1.4.2 rule unchanged)
- **`_evidence.json` + `_harvest_menu.md`**: article-scoped, follow the article (v1.4.15 new rule)

Hyphen vs underscore in filenames reflects the divide: `.state` (hidden, ephemeral) vs `_evidence`/`_harvest_menu` (visible, per-article artifacts).

## [1.4.14] - 2026-04-16

### Added

- **Drop-in HARVEST placeholder block** in `_harvest_menu.md`. For each source, a fenced markdown code block renders the recommended picks as ready-to-paste `<!-- HARVEST: url idx=N caption="..." -->` lines. Writer copies the block, replaces `...` with actual captions, deletes unused lines. GIF picks carry an inline `# GIF / 动图` comment.

### Why

v1.4.13 gave the writer recommended idx values. But the writer still had to manually compose `<!-- HARVEST: {url} idx={N} caption="..." -->` — typing the URL, remembering `--cover` syntax, deciding GIF vs still. This removes all that boilerplate. The full recommendation structure (1 cover + up to 5 main + all GIF demos) ships pre-wired; writer only types captions.

### Impact

Pipeline progression for the writer now looks like:
1. `cat _harvest_menu.md` — see 28 images summarized + recommendations
2. Copy the "🧱 Drop-in HARVEST placeholders" block
3. Paste into article.md at the chosen narrative positions
4. Replace `...` with captions (the only non-mechanical step)
5. Delete unused lines
6. Save — write Step 7 Check C validates against `_evidence.json` via `expand-harvest --dry-run --strict`

Zero URL typing, zero idx guessing, zero cover-syntax recall. The remaining cognitive load is exactly what it should be: where each image goes in the narrative and what its caption says.

## [1.4.13] - 2026-04-16

### Added

- **Recommended picks in `harvest-menu`**. Each source now gets a `📌 Recommended picks` block with four curated groups:
  - **Cover** — prefers `--cover` when source has og:image, else picks the biggest wide non-GIF
  - **Main visuals** — up to 5 non-GIF idx values ≥400×200, ranked by area
  - **Animation demos** — every GIF idx, ranked by area
  - **Likely avoid** — tiny images (<400×200) that are probably icons, QR codes, or decorative flourishes
- **JSON output gains `recommend` field** per source with `{use_cover_flag, cover_idx, main, demo, avoid}`.

### Why

v1.4.12 gave writers a menu file. But reading a 28-row image table and mentally finding "biggest jpg with good aspect ratio for cover" is still work Claude has to do, which means inconsistency. The recommendation block converts the raw listing into a "point at what to copy" guide — for the real WeChat article this surfaced cover=--cover, 4 correct GIF demos, and 5 icon-sized images to skip, all without writer judgement.

### Design note

Recommendations are **soft hints**, phrased as "guidance — not exhaustive, override freely". They don't prune the full image table; writers can still pick any idx. The goal is to reduce cognitive load, not lock writers in.

Thresholds chosen from observed behavior on a real WeChat Style H article:
- wide enough: ≥400×200 (filters out WeChat QR codes at 272×272 and follow-up cards at 252×214)
- cover candidate aspect: ≥1.3 (landscape bias for hero images)
- main visuals top-5 (enough for a long article, not spam)

## [1.4.12] - 2026-04-16

### Added

- **`evidence.py collect` now also emits `_harvest_menu.md`** next to `_evidence.json`. Calls `screenshot_tool.harvest_menu()` as a side effect; failure is non-fatal (printed warning, evidence still written).
- **write Step 3d-H now reads `_harvest_menu.md` by `cat`**, with CLI fallback when the file is missing (compat for legacy evidence output or manual invocations).

### Why

v1.4.11 gave writers a cheat-sheet command (`harvest-menu`) but relied on the writer to remember to run it. That's another step between "evidence exists" and "writer knows what's available" — one the writer can skip. Making the menu a **file** next to `_evidence.json` means it's always present, always fresh, and write skill consumes it with a trivial `cat` rather than a subcommand call.

### Design note

The menu is a pure view of `_evidence.json`. When someone regenerates evidence, menu regenerates too; when evidence is up-to-date, menu is up-to-date. Coupling generation this way avoids "menu out of sync with evidence" — a failure mode you'd otherwise need cache invalidation to prevent.

## [1.4.11] - 2026-04-16

### Added

- **New `harvest-menu` subcommand** — emits a writer-facing cheat-sheet from `_evidence.json` listing every HARVEST option with its exact `idx=N` value. Default output is markdown (a table per source with `idx | dim | fmt | alt` + ready-to-paste placeholder examples); `--json` emits structured data. Cover availability, paywall citations, and local manual files are each their own section.
- **write Step 3d-H now requires reading the menu** before emitting HARVEST placeholders. Replaces the previous "consume `_evidence.json` from memory" approach with a mechanical lookup: `idx` values in the menu are guaranteed to match what `expand-harvest --dry-run --strict` will validate downstream. write is explicitly told: cover from menu example, main images by scanning the `dim` column for the largest, GIFs by filtering `fmt=gif`, and to **not** use `alt="..."` matching for WeChat sources (where all alts are the generic "图片").

### Why this was needed

Running `harvest-menu` against real WeChat evidence surfaced a subtle systemic issue: all 28 WeChat `<img>` alts come back as "图片" (the generic fallback). A writer guessing "pick the Claude Code UI image by alt" would never match. The menu makes this visible — writer sees 27 identical "图片" alt entries and automatically switches to `idx=` by dimension. No more silent mismatches piling up for v1.4.10's Check C preflight to catch.

### Design note

Three-way purpose split now locked in:
- `harvest`: crawls a source page, returns list + cover to evidence.py
- `harvest-menu`: formats that list for the writer, no side effects
- `expand-harvest`: consumes the placeholders the writer emitted, applies rehost

Each speaks to exactly one actor (collector, writer, expander) and never crosses wires.

## [1.4.10] - 2026-04-16

### Added

- **Write Step 7 gains Check C: HARVEST preflight for Style H.** After article.md is saved and the existing Check A / B pass, if `_evidence.json` exists next to the article (Style H signal), Check C runs `expand-harvest --dry-run --strict` to verify every `<!-- HARVEST: -->` placeholder resolves against evidence. On failure, the trace is parsed and each broken placeholder gets a specific remediation hint:
  - `source_not_in_evidence` → register the URL in materials.md or switch to a registered one
  - `no_matching_image` with `idx=N` → `idx` is out of range, pick a valid index
  - `no_matching_image` with `alt="…"` → alt substring didn't match; use a matching substring
  - `no_matching_image` with `--cover` → source has no og:image; use `idx=` instead
- The writer iterates: fix placeholders → re-save → re-run preflight → until exit 0 before leaving write stage.

### Why this was needed

Without this check, a writer confidently typing `idx=7` (when evidence only has 5 filtered images) produces an article that silently carries unresolved `<!-- HARVEST: -->` comments into the images stage. The article ships with visible placeholder comments. Check C closes this failure mode **at write time**, where the fix is cheap — no images-stage quota burned, no expensive round trip.

### Design note

Check C is **Style H-triggered** (gated on `_evidence.json` existence), not style-triggered, so it also runs for any non-Style-H article that happens to use HARVEST. The `--dry-run` means zero network calls during the check. `--strict` means a single broken placeholder blocks completion, keeping the failure surface sharp.

## [1.4.9] - 2026-04-16

### Added

- **`expand-harvest --dry-run`** — preview mode. Parses placeholders, resolves images against `_evidence.json`, and reports what would happen (including whether each URL matches the rehost whitelist), but **skips all network calls and never writes `article.md`**. Added after an integration test accidentally uploaded 3 real images to the project's CDN during a hand-run check — `--dry-run` is the "no side effects" escape hatch.
- **`expand-harvest --strict`** — preflight quality gate. If any placeholder resolves to `source_not_in_evidence` or `no_matching_image`, the subcommand exits `1` and **does not modify `article.md`**. Intended as an orchestrator / CI gate before the (irreversible, network-spending) real expand. Works in combination with `--dry-run` to validate materials.md correctness without any upload.
- **New `trace[].rehost` states for dry-run**: `would_rehost` / `skipped_mode_never` / `skipped_not_whitelisted`. Makes the preview output actionable — you can see exactly which images would flow through rehost vs pass through.
- **Summary fields `dry_run` / `strict` / `would_write`** in the JSON output, so downstream tooling can distinguish preview from real runs.

### Design note

`--strict` wraps around `--dry-run` cleanly: one to confirm the article parses correctly, the other to commit. Recommended orchestrator flow:

```bash
# preflight
expand-harvest --dry-run --strict   # exit 1 → fix materials first
# real run
expand-harvest                       # network calls + article mutation
```

## [1.4.8] - 2026-04-16

### Fixed

- **Lazy-loaded image harvest on WeChat pages was dropping ~80% of images.** Playwright extracted `<img>` tags before scrolling, so only above-the-fold images had their `src` / dimensions populated — a 31-image WeChat article returned 6. `harvest_images()` now scrolls the page top → bottom in `innerHeight`-sized steps with 150ms pauses between scrolls, waits for network idle, then runs the extraction. On the same WeChat article this lifts recall from 6 to 28 (90% vs baoyu-fetch's 31-link reference).
- **0×0 `<img>` entries leaking into evidence**. Invisible shares / profile / decorative `<img>` elements sometimes report both `width` and `height` as 0 (no box model). `_filter_harvest_images()` now drops these unconditionally. Previously they'd show up in `_evidence.json` and could be selected by a `HARVEST idx=N` that happened to land on one.

### Verified

Real integration run against `https://mp.weixin.qq.com/s/ZeQ8VOEC53rmXB4jPSfPDw`:

- Before: 6 images, cover populated ✅
- After: 28 images, cover populated ✅
- Width distribution: min 252, max 1280, median 661 — no stub images or tiny icons

### Design note

The scroll loop is defensive: wrapped in a broad `try / except`, a failure falls through to the existing extraction. For short pages (≤ 1 viewport), the loop runs once with 150ms overhead. For very long pages (10+ viewports), it adds ~2–3s of wall time. Worth the trade on WeChat / Weibo / Zhihu where lazy-load is the norm.

## [1.4.7] - 2026-04-16

### Added

- **`--cover` HARVEST syntax** (gap 3 from the v1.4.6 scoping). Source pages' cover image is now extracted during `harvest` (Playwright reads `og:image` / `twitter:image` meta tags; baoyu-fetch fallback reads `document.coverImage` / `media[]` role=cover) and stored at `source.cover` in `_evidence.json`. HARVEST placeholders gain `--cover` / `cover=1` to pick this instead of an `images[N]` entry. Priority: `--cover` > `idx=` > `alt=`.
- **`expand-harvest` subcommand** on `scripts/screenshot_tool.py` — real Python implementation of what used to be pseudocode in `screenshot/SKILL.md`. Takes `--article` and optional `--evidence`, reads `_evidence.json`, walks every `<!-- HARVEST: ... -->` placeholder, resolves the image (`--cover` / `idx=` / `alt=`), invokes `rehost_image()` per the placeholder's mode, rewrites `article.md` in place. Returns a JSON summary with per-placeholder trace: `status ∈ {expanded, source_not_in_evidence, no_matching_image}`, plus counts for `expanded` / `rehosted` / `failed`.
- **HARVEST opts parser** `_parse_harvest_opts()` — handles `idx=N`, `alt="…"`, `caption="…"`, `rehost=auto|always|never`, and `--cover` / `cover=1|true|yes`. Tested against 11 syntax variants.
- **`_pick_harvest_image()`** resolver with explicit priority: cover beats idx beats alt. alt uses case-insensitive substring match against `images[].alt`.

### Changed

- **screenshot/SKILL.md**: the HARVEST expansion section drops the ~25 lines of Python pseudocode, replaced by a single `subprocess.run` against `expand-harvest`. The SKILL.md now just documents what the subcommand does and what its JSON trace means — the actual loop / rehost / substitute logic lives in a testable Python function.
- **`harvest` CLI output**: result JSON now includes a `cover` field (empty string when not available).
- **`evidence.py` `_evidence.json` schema**: `sources[i]` gains `cover` field, pass-through from `harvest_images()` result.

### Why this pairs well

The v1.4.6 rehost pipeline added non-trivial decision logic (whitelist matching, per-placeholder mode override, graceful degradation). Leaving that logic as pseudocode in SKILL.md meant Claude would re-derive the flow each run, with risk of drift. Moving it into a subcommand:

1. Makes rehost failures observable per-placeholder via the `trace[]` array
2. Lets `--cover` slot in as one more resolver case with zero prompt-engineering
3. Reduces SKILL.md token cost (~25 lines of code → 1 subprocess call)
4. Unit-testable: the 7-placeholder end-to-end run exercises expanded / source-missing / idx-out-of-range / alt-substring / --cover / rehost=never / graceful-degradation in one article

## [1.4.6] - 2026-04-16

### Added

- **HARVEST rehost pipeline** — `scripts/screenshot_tool.py` gains `rehost_image()` + `rehost` CLI subcommand. When a HARVEST placeholder points at a hotlink-protected CDN (WeChat mmbiz, Weibo sinaimg, Zhihu zhimg), article-craft now downloads the original image with the correct `Referer` and re-uploads it via the existing PicGo / S3 pipeline before substituting into the article. Non-whitelist URLs pass through unchanged, preserving the v1.4.0 "远端 CDN 保持真源" philosophy where safe.
- **Per-placeholder `rehost=auto|always|never` override** in HARVEST syntax. Default `auto` = rehost only the whitelisted CDNs. Writers who know their target platform is hotlink-friendly can opt out per image with `rehost=never`.
- **`REHOST_CDN_WHITELIST` constant** mapping CDN substring → canonical Referer. Initial list: `mmbiz.qpic.cn` (WeChat article images), `mmbiz.qlogo.cn` (WeChat avatars), `sinaimg.cn` (Weibo, covers ww1/ww2/tva*/wx1-4 subdomains), `zhimg.com` (Zhihu, covers pic1-4).

### Fixed

- **`upload_to_s3` hard-coded `ContentType: 'image/jpeg'` regardless of file extension** — broke GIFs uploaded via rehost (served as JPEG, silently). Now infers `Content-Type` via `mimetypes.guess_type()`, falling back to `image/jpeg` only if inference fails or returns non-image.

### Design notes

- **Why rehost exists**: empirical test against a live mmbiz image confirmed the CDN returns **HTTP 200** with a ~2KB silent placeholder JPEG when the `Referer` is wrong (e.g., `google.com`), and the full 96KB image when Referer is `mp.weixin.qq.com` or absent. Since the final article will be read from a different origin (Obsidian vault / blog / Zhihu), the reader's browser sends *that* origin as Referer → silent stub. No HTTP error, no way to detect visually except by looking. rehost sidesteps the whole Referer dance by moving the image to our CDN.
- **GIF preservation**: `_infer_image_extension()` detects GIF via `wx_fmt=gif`, `.gif` suffix, or `Content-Type: image/gif`. rehost writes bytes through to tempfile with `.gif` extension, `upload_image()` picks the file up with correct MIME (now that upload_to_s3 respects extension). Bypasses Pillow compression entirely — animated GIFs stay animated.
- **Graceful degradation**: any failure in rehost (download timeout, HTTP error, upload failure, suspected hotlink stub) returns `ok=False` with `final_url == original_url`. The HARVEST expander keeps the remote URL and logs a warning. No pipeline aborts.
- **Stub-detection bar**: 4KB. Real Style H source images are typically 20–100KB. The 2086B mmbiz stub we measured is well under the bar.

### Scope

Fixes the two top gaps identified from reading a real WeChat Style H article (31 images, 4 GIFs, all `mmbiz.qpic.cn`):

1. mmbiz silent-hotlink breakage on non-WeChat platforms
2. GIF content-type mishandling in S3 path

The third identified gap — `--cover` shorthand for grabbing a source article's cover via `baoyu-fetch` metadata instead of the `<img>` list — is intentionally deferred as a low-priority convenience.

## [1.4.5] - 2026-04-16

### Added

- **New `verify-claims` skill + `scripts/verify_claims.py`.** Post-write stage that scans the article body for shell commands (bash / sh / shell / zsh blocks) and checks each named tool against PATH via `shutil.which`. Runs **after images, before review** in standard mode. Standalone invocation: `/article-craft:verify-claims /abs/path/article.md`.
- **New `commands/article-craft/verify-claims.md`** sub-command wrapper for the skill.
- **orchestrator Step 3.6** — new stage. Returns `PASS` / `PASS_WITH_MARKS` (user edited article to tag unknown tools with `[需要验证]`) / `ABORT`. Skipped in quick / draft modes.

### Changed

- **`write` Step 7 Check C removed.** Command correctness is no longer validated inline during write; it's been lifted into the dedicated verify-claims stage. Step 7 now runs 2 handoff contract checks (placeholder format + IMAGE double-line format) instead of 3. Rationale: Check C was a grep-level approximation that competed with a proper post-write scan for the same job.
- **Role clarification (no directory rename):** the pre-write `verify` stage is a **source vetter** (URL reachability, T0–T5 trust tiering). The post-write `verify-claims` stage is a **body vetter** (shell command existence). The two are complementary and non-overlapping. Skill directory names stay stable for command compat — `/article-craft:verify` still works and still does source vetting.
- **`scripts/pipeline_state.py`** — `verify_claims` added to the stage allowlist and to `MODE_STAGES["standard"]` / `MODE_STAGES["series"]`. `--upgrade` now correctly accounts for this stage when reporting missing / done.
- **orchestrator Step 3.7 (Publish) renumbered to 3.8** to make room for verify-claims at 3.6.
- **CLAUDE.md** — introductory paragraph clarifies the two verification stages; skill count updated from 11 to 12.

### Scope notes

- verify-claims MVP covers shell-language code blocks only. Flag-level validation, API endpoint reachability, version-string claims in prose, and Python / JS imports are explicitly out of scope — each is a future enhancement, not a bug. See `skills/verify-claims/SKILL.md` "Out of scope" list.
- Closes the "Verify stage is misnamed and incomplete" item in CLAUDE.md's "Known design debt". **All 5 original debt items are now closed.**

## [1.4.4] - 2026-04-16

### Changed

- **Review Phase 2 is now diagnostic-only.** Dropped the embedded 3-round auto-modify loop + oscillation guard. The new flow: score on 7 dimensions → produce per-dimension feedback (what failed / where / suggested action) → AskUserQuestion with 3 options (Publish anyway / Re-run write with hints / Abort). Each fix is a new explicit decision; review never mutates article content during Phase 2.
- **orchestrator Step 3.6** now recognizes a third return value from review: `NEEDS_REVISION_RERUN_WRITE` (user chose "Re-run write with hints"). On that outcome the orchestrator loops back to Step 3.3 (write), passing review's feedback list as targeted hints, then continues screenshot → images → review as normal. A loop guard caps this at 2 reruns per pipeline (the 3rd NEEDS_REVISION drops the "rerun" option from AskUserQuestion).

### Why

The `<dim-score><7` → "fix corresponding issues" instruction was too open-ended to converge reliably. In practice rounds often regressed one dimension while fixing another (the very oscillation the guard was built to detect), and — worse — auto-modify happened **after** the images stage, so edits could orphan `<!-- IMAGE: -->` placeholders or invalidate CDN references. Diagnostic-only sidesteps both failure modes.

### Design notes

- Handoff-contract comments and CDN URLs are now hard invariants: review never touches them in any code path.
- Phase 1 self-check (auto-fix for mechanical violations) is unchanged — it fixes red-flag words / hook length / closings / transitions per `references/self-check-rules.md` before Phase 2 scores.
- Closes the "Review Phase 2 auto-modify is underspecified" item in CLAUDE.md's "Known design debt". 1 item remains: verify rename/split (source-vet + verify-claims).

## [1.4.3] - 2026-04-16

### Added

- **Batch-level 429/503 backoff** in the sequential image pipeline. `scripts/generate_and_upload_images.py` now distinguishes "all models in the fallback chain exhausted with rate-limit errors" from "generic failure": the former raises a new `RateLimitExhausted` exception that the batch loop catches, then sleeps 30 / 60 / 120 seconds (with up to 5s jitter) before retrying the same image. After 3 exhausted backoffs, the image is skipped and the batch continues — no more "half the placeholders ship unresolved" when Gemini throttles mid-run.
- **`_generate_with_batch_backoff` helper** inside `generate_and_upload_images.py` isolates the backoff policy from the model fallback chain. Non-rate-limit failures still fail immediately (preserves existing "fail that image, continue the batch" semantics).

### Changed

- **`generate_image()` now raises `RateLimitExhausted`** instead of silently returning `False` when every model in the chain (`gemini-3-pro-image-preview` → `gemini-3.1-flash-image-preview` → `gemini-2.5-flash-image`) hit 429/503/rate-limit/resource_exhausted. Callers that don't want batch backoff can still catch the exception and treat it as a plain failure.

### Design notes

- Fixes the sequential path only. The parallel path (`generate_and_upload_parallel`, activated by `--parallel`) still has probe-layer retries only; coordinating batch-level backoff across a thread pool is a separate refactor and not currently on the orchestrator's hot path.
- Worst-case added wall time per image: 30 + 60 + 120 + ~15s jitter ≈ 3.5 minutes before giving up. This is intentional — Gemini quota resets on a 1-minute window, so the 30s first retry usually clears it.
- Closes the "Images batch has no per-image 429 backoff" item in CLAUDE.md's "Known design debt" list (sequential path). 2 items remain: verify rename/split (source-vet + verify-claims) and review Phase 2 auto-modify → scoring-only.

## [1.4.2] - 2026-04-16

### Added

- **Persistent cross-stage state file** — `.article-craft-state.json`, co-located with each article. The orchestrator writes stage status (running / completed / failed / skipped) with per-stage result payloads at every pipeline boundary. Resurrects `scripts/pipeline_state.py` (deleted in v1.3.4) with a real CLI, proper schema versioning, atomic writes, and now actually wired into the orchestrator.
- **`pipeline_state.py` CLI** with subcommands: `init`, `start`, `complete`, `fail`, `skip`, `show`, `missing-stages`, `cleanup`, `reset`, `artifact`. The `missing-stages` command is the primary `--upgrade` entry point — it returns structured JSON with `missing` / `done` / `stale` / `skipped` lists plus a `source` field (`state_file` / `hybrid` / `heuristic`).
- **State-file conflict resolution**: article content remains ground truth. If state says `images: completed` but the body still has `<!-- IMAGE: -->` placeholders, the stage is flagged `stale` and re-runs. `source: "hybrid"` in the output makes the disagreement visible.

### Changed

- **`--upgrade` mode** now reads `.article-craft-state.json` first and falls back to content heuristics only when the file is absent. Articles predating v1.4.2 still work through the heuristic path (pure `source: "heuristic"` result).
- **orchestrator/SKILL.md Step 2** now initializes the state file after `write` produces an article path. A new "State Write Protocol" section documents `start`/`complete`/`fail`/`skip` calls + per-stage result payload shapes for all 9 stages.
- **`publish` stage cleanup**: in standard mode, the state file is deleted after `publish` completes successfully — the pipeline is done, no state needed. `draft` and `quick` modes preserve the state file so future `--upgrade` can resume from it.

### Design notes

- State file lives next to `article.md` so it survives `git mv`. Schema is versioned (`schema_version: "1"`) for future migrations; the current `pipeline_version` is recorded for audit.
- Standalone skill invocations (`/article-craft:lint`, `/article-craft:review`) do not write state. State is orchestrator-only, since it only has meaning for multi-stage pipeline runs.
- Closes the "No persistent cross-stage state file" item in CLAUDE.md's "Known design debt" list. 3 items remain: verify rename/split (source-vet + verify-claims), images batch 429 backoff, and review Phase 2 auto-modify → scoring-only.

## [1.4.1] - 2026-04-16

### Changed

- **Self-check rules are now single-sourced** in `references/self-check-rules.md`. The `write`, `lint`, and `review` skills previously re-stated the 11 rules inline — ~241 lines of duplication across 3 skills. They now reference the canonical source by rule number, declaring only their enforcement role (pre-save GATE vs auto-fix vs detect-only). New "Who enforces what" matrix at the top of the rules file makes ownership unambiguous.
- **`references/self-check-rules.md` rewritten** (201 → 433 lines). Each rule now carries explicit `Severity` / `Auto-fix` / `Escalation` metadata. Rule 1 auto-fix mapping, Rule 5 transition-word list (5 words), Rule 11 ASCII-diagram grep (12 canonical single chars) all live here once.
- **Rule 7b (minimum AI image count) migrated from review to the canonical source**, including the degradation-detection pre-check that downgrades to WARNING when unresolved `<!-- IMAGE: -->` placeholders exist (prevents orphan-placeholder injection when images stage degraded).
- **Rule 11 (ASCII diagrams) split into three-role semantics**: write Step 6 pre-save GATE auto-converts; lint reports only (may run anywhere in pipeline); review detect-only and blocks Phase 2 via AskUserQuestion. Previously this distinction lived in review's inline copy.

### Fixed

- **lint's ASCII grep drift**: was `│|├|└|┌|┐|─|▼|▶|←→|──→|←──` (12 chars + 3 useless combined sequences, missed `↑↓`). Now uses the canonical single-character set `│|├|└|┌|┐|─|▼|▶|←|→|↑|↓` shared with write and review.
- **Transition-word list divergence**: lint had 5 words, rules.md + review had 4. Unified to 5 (`此外|另外|同时|值得注意的是|除此之外`) as the canonical list.
- **Rule 11 auto-fix instructions in rules.md** contradicted review's v1.3.2 "detect-only" architecture fix. Rewrote to match actual behavior: only write Step 6 auto-converts (pre-images), everyone downstream either reports or blocks.

### Design notes

- The rules.md file is now the **only** place rule bodies, grep patterns, and auto-fix mappings live. SKILL.md files declare *which rules they enforce and how* but do not re-type the rules. Adding or changing a rule is now a one-file edit.
- Phase 2 scoring (7 dimensions), oscillation guard, write Step 6/7 gates, and handoff-contract invariants are unchanged. This is purely a deduplication refactor.

## [1.4.0] - 2026-04-15

### Added

- **Style H — 爆料自媒体 / 公众号爆款** in `references/writing-styles.md`: new writing style modeled on AI-news 公众号 voice (dramatic headlines, short hook paragraphs, source-image reuse) — 戏剧性标题、H2 钩子句、源图直引、竞争对垒叙事、泄露代号对照、极短段落。Includes auto-detect signals ("曝光"、"爆料"、"突袭"、"泄露"、"一夜"、"硬刚"、股价/竞品对垒) and hard constraints enforced by the write skill.
- **New `evidence` skill** (`skills/evidence/SKILL.md` + `commands/article-craft/evidence.md` + `scripts/evidence.py`): collects source evidence for Style H. Parses `materials.md` (public URLs / local paths / gated citations), batches `harvest` calls across all public sources, outputs `_evidence.json` consumed by write. BLOCKS the pipeline for Style H when materials are missing or evidence-image count < 2.
- **`screenshot_tool.py harvest` subcommand**: extracts all `<img>` URLs + alt + width/height + surrounding context from a source URL. **Playwright primary** (fast, JS-rendered) with **baoyu-fetch fallback** for CAPTCHA / login walls / paywalls (auto-detects 微信公众号 / Cloudflare gates and switches engines). Output JSON is directly consumed by `evidence.py`.
- **`<!-- HARVEST: url idx= | alt= [caption=] -->` placeholder**: expands in-place to `![caption](远端 url)` without downloading or re-uploading. Implements the WeChat-爆款-style "直引源站图片" pattern — the remote CDN stays the source of truth, article-craft never becomes the image host. Processed by screenshot skill alongside existing `<!-- SCREENSHOT: -->` placeholders.

### Changed

- **orchestrator/SKILL.md**: pipeline is now 8 skills (added `evidence` between `verify` and `write`). Style H makes `evidence` mandatory in every mode (standard / quick / draft); other styles mark it `skipped`. Pipeline BLOCKS if `_evidence.json` is missing or has < 2 images when Style H is selected.
- **write/SKILL.md**: adds Style H branch — 【导读】加粗 H5 替代 `> [!abstract]` callout, consumes `_evidence.json`, enforces ≥2 evidence images, requires hook-style H2 titles (感叹号 / 动词 / 代号 / 数字), forbids Obsidian callouts + "综上所述" collider phrases + 客观中性 H2 描述, requires 参考资料 section + 公众号三板斧 ending.
- **screenshot/SKILL.md**: adds HARVEST placeholder scan alongside SCREENSHOT; documents the remote-URL inlining contract; adds `harvest` subcommand docs.

### Design notes

- HARVEST vs SCREENSHOT distinction is now the canonical way to decide "reuse remote image" vs "capture new image". Use HARVEST for 源文章已有的图; SCREENSHOT for 空的页面需要自己截；manual 本地路径走 `SCREENSHOT: /abs/path`.
- baoyu-fetch fallback is opt-out (`--no-fallback`) but only triggers when Playwright hits an auto-detected gate (CAPTCHA markers, HTTP >= 400, login walls). Keeps the happy path fast while giving the unhappy path a real escape hatch.

## [1.3.4] - 2026-04-13

### Fixed

- **CI workflow** (`tag-release.yml`): removed buggy auto-bump logic where the `if: skipping == 'false'` condition on the Bump step was inverted — the workflow was bumping the patch version on every push whose version didn't yet have a release (rather than only when a release collision existed), and the bump was never committed back to the repo, so `plugin.json` and the published tag drifted apart. The workflow is now a clean "read plugin.json → create tag + release, or skip if already released" no-auto-bump loop. `plugin.json` is authoritative.
- **marketplace.json**: synced `plugins[0].version` from stale `1.1.0` to the plugin version. It had drifted since March 2026 and was not surfaced until the v1.3.4 version audit.

### Changed

- All version-carrying files bumped in lockstep to `1.3.4`: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, and all 11 `skills/*/SKILL.md` frontmatter. When bumping in the future, touch all 13 in the same commit (the workflow will not do this for you).

## [1.3.2] - 2026-04-10

### Fixed (runtime + contract)

- **publish**: repaired broken `os.path.expanduser("${CLAUDE_PLUGIN_ROOT}/...")` Python snippet that would fail at runtime; added missing `import os, sys`.
- **orchestrator / images**: fixed unbalanced markdown code fences that broke rendering of the status tracker and image script examples.
- **review**: removed orphaned `Rule 12–15` references from the output template; aligned rule count header to 11.
- **orchestrator**: removed the outer review retry loop that compounded review's internal 3-round loop into up to 9 rounds.
- **write**: replaced direct `review_selfcheck.py` invocation with inline Grep/Bash handoff checks; renamed "Rule X" to "Check X" to stop colliding with review's rule numbering.
- **review / orchestrator / lint**: purged stale `content-reviewer` references (review is now self-contained).

### Fixed (architecture + design)

- **review Rule 11 (ASCII diagram check)**: stopped auto-converting to `<!-- IMAGE: -->` placeholders. Review runs after the images stage, so any new placeholder would be orphaned (never generated). Now detect-only with `FAIL — escalate`; conversion remains `write` Step 6's responsibility.
- **review Rule 7b (min image count)**: added degradation detection. If the article has unresolved `<!-- IMAGE: -->` placeholders (meaning images stage failed), rule downgrades to WARNING and skips placeholder injection instead of adding more orphans.
- **review auto-revision loop**: added oscillation guard — break early if `score_{round} <= score_{round-1}` — to prevent ping-pong between conflicting fixes. Revisions must also preserve handoff-contract comments (IMAGE / PROMPT / SCREENSHOT / CDN URLs).
- **orchestrator Step 0 Preflight**: verify Gemini key, Playwright chromium, and PicGo before running any skill. Fail fast instead of wasting 60–120 s to explode at the images stage.
- **orchestrator quick mode**: emits `UNVERIFIED CITATIONS` warning block in the completion summary when T3–T5 community sources were cited without `verify`.
- **orchestrator share_card**: removed mid-pipeline `AskQuestion`; auto-infer from frontmatter completeness and accept `--share-cards=yes|no|auto` flag. Autonomous runs no longer block.
- **write draft mode**: prints `/article-craft --upgrade PATH` resume hint in the completion message so users know how to finish a draft.
- **publish**: added `--output DIR` override as an escape hatch from KB auto-detection; Step 1 splits into Mode A (explicit) and Mode B (auto-detect).
- **verify**: made cache TTL configurable via `env.json` key `verify_cache_ttl_seconds`; `--series` auto-extends to 24 h so multi-article runs share vetting.
- **write Step 7**: deduped handoff checks. Removed Check 1 (red-flag), Check 3 (template summary), Check 5 (chapter depth) — these are `review`'s job. Kept only Check A (placeholder format), Check B (IMAGE double-line contract), Check C (command verification).

### Added

- **All 10 non-orchestrator skills**: declare `allowed-tools` in frontmatter (previously only orchestrator did).
- **CLAUDE.md**: introduced with project overview, key scripts, cross-skill data flow, conventions, and a "Known design debt" section documenting intentionally deferred refactors (verify rename/split, images batch 429 retry, rule deduplication across 3 skills, review Phase 2 scoring-only redesign, persistent cross-stage state file).

### Removed

- **`scripts/pipeline_state.py`**: deleted 150 lines of dead code — never imported by any skill. `--upgrade` mode continues to use text heuristics until a real state file is designed (see Known design debt).

### Housekeeping

- Aligned all 11 skill versions to the plugin version (previously drifted at 1.2.0 / 1.3.0 / 1.3.1).
- Normalized `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*.py` invocations across `screenshot` skill (some were bare `python3 script.py`).
- Removed duplicate `## Verification Philosophy` section from `verify/SKILL.md`.
- Fixed `Three modes` / 5-row table contradiction in `orchestrator/SKILL.md`.
- Deleted trailing stale version note in `write/SKILL.md`.

## [1.1.0] - 2026-03-31

### Changed

- **Path compatibility**: All hardcoded paths replaced with `${CLAUDE_PLUGIN_ROOT}` dynamic variable across all 12 command files, 11 SKILL.md files, scripts, and hooks.
- **SKILL.md frontmatter**: Added `version` and `allowed-tools` fields to all 11 skills for better Claude Code integration.
- **README.md**: Rewritten to match Claude Code plugin marketplace standard with marketplace installation instructions.
- **plugin.json**: Added `license` and `keywords` fields, removed `install` field (dependencies handled by `install.sh`).
- **marketplace.json**: Updated owner info and synchronized version to 1.1.0.
- **hooks.json**: Extended SessionStart matcher to include `error` event.
- **hooks/run-hook.sh**: Replaced hardcoded path with `${CLAUDE_PLUGIN_ROOT}` fallback.
- **lib/article-core.js**: Replaced hardcoded path with `CLAUDE_PLUGIN_ROOT` environment variable.
- **INSTALL.md**: Streamlined to two-screen quickstart, prioritizing `install.sh` one-command setup.
- **scripts/README.md**: Updated path references.

### Added

- **install.sh**: Interactive one-command installer covering Python deps, shot-scraper, PicGo, Gemini API key, and verification.

## [1.0.0] - 2026-03-22

- Initial release with 11 composable skills for the full article lifecycle.
