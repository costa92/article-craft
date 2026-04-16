---
name: article-craft:evidence
version: 1.4.5
description: "Collect source evidence (images, quotes, leak references) for Style H (爆料自媒体). Parses materials.md, runs batch harvest on public sources, records manual screenshots and paywalled citations, outputs _evidence.json for write skill."
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
  - AskUserQuestion
---

# Evidence — 爆料证据包采集（Style H 专用）

Style H（资讯爆料/公众号爆款）的命脉是**证据截图**：源推文、官方博客图、
泄露代码/文件、股价反应、产品界面 GIF。新智元等公众号的做法是**直引源站图片**
（`mmbiz.qpic.cn` / `pbs.twimg.com` …），不重截。本 skill 把这层自动化。

> 本 skill **只在 Style H 时必跑**，其它风格可选。用户明确 `--style=H`
> 或风格自动判断命中 H 时触发。

---

## 核心流程

```
用户提供 materials.md
    │
    ▼
┌─────────────────────────────┐
│ 1. 解析 materials.md         │  → public / local / gated 三类
└────────┬────────────────────┘
         ▼
┌─────────────────────────────┐
│ 2. 批量 harvest 公开源       │  ← Playwright 优先 + baoyu-fetch 兜底
│    （从 HTML 抓 <img> 清单）  │
└────────┬────────────────────┘
         ▼
┌─────────────────────────────┐
│ 3. 校验本地截图路径存在      │
└────────┬────────────────────┘
         ▼
┌─────────────────────────────┐
│ 4. 登录墙/付费墙源仅记引用   │  ← 不 harvest，供 write 引用原文
└────────┬────────────────────┘
         ▼
     输出 _evidence.json → 交给 write skill
```

---

## 输入：materials.md 格式

用户在 requirements 阶段提供（若 requirements 检测到 Style H 会主动索取）。
放在 article.md 同目录或 `/tmp/materials.md`。

```markdown
# Evidence Materials

## 公开源（auto-harvest）

- https://mp.weixin.qq.com/s/xxx  tier=T3 note="新智元爆料原文"
- https://x.com/anthropic/status/123  tier=T0
- https://claude.com/blog/introducing-routines-in-claude-code  tier=T0

## 本地截图（manual paths）

- /abs/path/leaked-kairos.png  desc="3 月泄露的 .map 文件 KAIROS 段"
- /abs/path/adobe-stock-chart.png  desc="Adobe 股价 4/14 跌 2.3%"

## 登录墙/付费墙（cite-only）

- https://www.theinformation.com/briefings/xxx  desc="The Information 独家，引用原文 3 段"
- https://discord.com/channels/xxx/yyy/zzz  desc="Anthropic 员工 Discord 发言"
```

**关键语法：**
- URL 后可选 `tier=T0..T5`（不写默认 T5）
- 后缀 `note="..."`（harvest 上下文说明）
- 后缀 `desc="..."`（最终写入文章的图注）
- H2 小节头含"本地/manual/截图/screenshot/local" → 归为 local
- H2 小节头含"登录/付费/gated/paywall/墙" → 归为 gated
- 其它 → public（auto-harvest）

---

## 使用方式

### 标准调用（由 orchestrator 触发）

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/evidence.py collect \
  /ABSOLUTE/PATH/materials.md \
  -o /ABSOLUTE/PATH/_evidence.json \
  -w 2 \
  --min-width 200
```

### 只解析，不 harvest（调试）

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/evidence.py parse /path/to/materials.md
```

---

## 输出：_evidence.json

```json
{
  "materials_path": "/abs/path/materials.md",
  "collected_at": "2026-04-15T10:42:00Z",
  "sources": [
    {
      "url": "https://mp.weixin.qq.com/s/xxx",
      "tier": "T3",
      "note": "新智元爆料原文",
      "title": "Claude Opus 4.7 刚刚曝光…",
      "method": "baoyu-fetch",
      "images": [
        {
          "idx": 0,
          "url": "https://mmbiz.qpic.cn/mmbiz_jpg/.../640?wx_fmt=jpeg",
          "alt": "",
          "context": "Claude Code 桌面端彻底进化",
          "width": 1080,
          "height": 540
        }
      ]
    },
    {
      "url": "https://www.theinformation.com/xxx",
      "tier": "T5",
      "method": "gated",
      "images": [],
      "desc": "The Information 独家"
    }
  ],
  "manual": [
    { "path": "/abs/path/leaked-kairos.png", "desc": "3 月泄露 .map KAIROS 段" }
  ],
  "summary": {
    "public_count": 3,
    "manual_count": 1,
    "gated_count": 1,
    "total_images": 27,
    "failed": []
  }
}
```

---

## 失败处理

| 场景 | 处理 |
|------|------|
| materials.md 缺失 | **BLOCK** — 提示用户补 materials.md（Style H 硬约束） |
| public 源全部 harvest 失败 | 警告但不 block；若 manual 为空则 block |
| 某条 public 源 CAPTCHA | baoyu-fetch 自动 `--wait-for interaction` 兜底 |
| 本地截图路径不存在 | 警告，保留 `desc` 供文章引用 |
| 总图片数 = 0 | **BLOCK** — Style H 至少需要 2 张证据图 |

---

## 与 write skill 的契约

write 在 Style H 模式下必须：
1. 读 `_evidence.json`，选取 ≥2 张图片插入正文（`![desc](远端 url)`）
2. 每张图前后放上下文段落（不允许孤立配图）
3. 对 `gated` 源采用 "据 [媒体名] 爆料" / "[媒体] 独家报道称" 的引用句式
4. 对 `manual` 本地图走正常 `<!-- SCREENSHOT: path -->` 占位符（截图阶段直接复制）
5. 在末尾"参考资料"列出所有 `sources[].url`（按 tier 排序）

---

## 与其他 skill 的关系

| 上游 | 下游 |
|------|------|
| **requirements** 检测到 Style H → 询问用户 materials.md 路径，写进 context | **write** 在 Style H 分支下首先读 `_evidence.json` |
| **verify** 可选预先验证 public URL 可用性（evidence 也会跑，但 verify 更轻） | **screenshot** 处理 `manual` 本地截图引用时接力 |

---

## 独立使用

```
/article-craft:evidence /path/to/materials.md
```

独立调用时：
- 无参数 → AskUserQuestion 索取 materials.md 路径
- 输出默认放在 materials.md 同目录 `_evidence.json`
- 自动打印摘要统计

---

## 依赖

- Python 3.8+（argparse, json, re）
- Playwright chromium（首选 harvest 引擎）
- bun + baoyu-fetch CLI（兜底；`baoyu-skills` 插件已安装时自动发现）

若两者均不可用，只能处理 manual + gated 类材料，public 会标记为失败。
