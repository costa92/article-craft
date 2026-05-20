# article-craft 安装指南

## 环境要求

| 组件 | 最低版本 | 说明 |
|------|---------|------|
| Python | 3.10+ | 运行图片生成脚本 |
| Node.js | 18+ | PicGo CLI 依赖（可选） |
| Claude Code | 最新版 | 插件宿主 |

---

## 快速安装（推荐）

### 1. 克隆插件

```bash
git clone https://github.com/costa92/article-craft.git ~/.claude/plugins/article-craft
```

### 2. 一键安装

```bash
cd ~/.claude/plugins/article-craft
bash install.sh
```

`install.sh` 会自动完成：
- 检查系统依赖
- 安装 Python 依赖
- 安装 shot-scraper + Playwright
- 安装 PicGo CLI（图床上传）
- 配置 Minimax API Key
- 可选配置 Gemini fallback Key
- 验证安装结果

---

## 手动安装（可选）

如果不使用 `install.sh`，可手动完成以下步骤：

### Python 依赖

```bash
pip3 install -r ~/.claude/plugins/article-craft/scripts/requirements.txt
```

### shot-scraper（必选）

```bash
pip3 install shot-scraper
shot-scraper install   # 下载 Playwright 浏览器，约 100-200MB
```

### PicGo CLI（图片上传用）

```bash
npm install -g picgo
picgo set uploader    # 配置图床（推荐 github + jsDelivr CDN）
```

支持的图床：github / aliyun-oss / cos / qiniu / smms

### yt-dlp（可选，YouTube 转文章用）

```bash
pip3 install yt-dlp
```

### NotebookLM CLI（可选，长文调研/资料整理用）

推荐安装：

```bash
uv tool install notebooklm-cli
```

或：

```bash
pip3 install notebooklm-cli
```

安装完成后验证：

```bash
nlm --help
```

如果你的环境额外提供了 `notebooklm` 包装命令，也可以直接运行 `notebooklm --help`。

如果你需要的是 MCP 服务端兼容层，而不是研究 CLI，本项目也兼容：

```bash
uv tool install notebooklm-mcp-cli
notebooklm-mcp --help
```

### Minimax API Key

编辑 `~/.claude/env.json`：

```json
{
  "minimax_api_key": "YOUR_KEY_HERE"
}
```

可选再补充 Gemini fallback：

```json
{
  "minimax_api_key": "YOUR_MINIMAX_KEY",
  "gemini_api_key": "YOUR_GEMINI_KEY"
}
```

---

## 目录结构

```
~/.claude/plugins/article-craft/
├── install.sh                    # 一键安装脚本
├── .claude-plugin/             # 插件元数据
│   ├── plugin.json             # 插件配置
│   └── marketplace.json
├── skills/                     # 13 个 Skill 模块（orchestrator + 12 子技能）
│   ├── orchestrator/          # 主编排器
│   ├── write/                 # 文章生成
│   ├── images/                 # 图片生成
│   ├── screenshot/            # 网页截图
│   ├── requirements/           # 需求采集
│   ├── verify/                # 预写验证（源信任分级）
│   ├── verify-claims/         # 写后命令校验
│   ├── evidence/              # Style H 证据采集
│   ├── review/                # 质量评分
│   ├── publish/               # 发布入库
│   ├── lint/                 # 风格检查
│   ├── series/               # 系列管理
│   └── youtube/              # 视频转文章
├── commands/                   # Slash 命令入口（顶层 flat 布局）
├── scripts/                    # Python 自动化脚本
│   ├── doctor.py                       # 运行时健康检查（v1.6.0）
│   ├── nanobanana.py                  # 单张图片生成
│   ├── generate_and_upload_images.py  # 批量图片处理
│   ├── screenshot_tool.py              # Playwright 截图 + CDN 上传
│   ├── share_card.py                  # 社交分享卡片
│   ├── publish_plan.py                # 发布规划 + 碰撞检测（v1.6.0）
│   ├── series_state.py                # 系列状态机（v1.6.0）
│   ├── pipeline_state.py             # 流水线状态
│   ├── review_selfcheck.py           # 自检规则
│   ├── verify_claims.py               # 命令存在性校验
│   ├── lint_article.py                 # 文章 lint
│   ├── config.py                      # 配置常量
│   ├── utils.py                       # 工具函数
│   ├── setup_dependencies.py          # 依赖检测
│   └── requirements.txt              # Python 依赖列表
├── lib/                       # Node.js 共享库
│   └── article-core.js
├── hooks/                     # Session 钩子
│   ├── hooks.json
│   └── run-hook.sh
└── references/               # 写作规范文档
    ├── knowledge-base-rules.md
    ├── verification-checklist.md
    ├── writing-styles.md
    ├── self-check-rules.md
    └── gemini-models.md
```

---

## 快速开始

安装完成后，在 Claude Code 中使用：

```bash
# 完整流水线
/article-craft 写一篇关于 Go 并发编程的技术文章

# 单独使用（任一子命令都可独立调用）
/article-craft:requirements   # 需求采集
/article-craft:verify         # 源信任分级 + 链接验证
/article-craft:evidence       # Style H 证据采集
/article-craft:write          # 生成文章
/article-craft:screenshot     # 网页截图 + 分享卡片
/article-craft:images         # 生成图片
/article-craft:verify-claims  # 写后命令校验
/article-craft:review         # 审核评分
/article-craft:publish        # 入知识库
/article-craft:lint           # 风格检查
/article-craft:series         # 系列管理
/article-craft:youtube        # YouTube 转文章
/article-craft:doctor         # 运行时健康检查（v1.6.0+）
/article-craft:upgrade        # 升级 draft/quick 文章到标准
```

### 四种工作流模式

| 模式 | 命令 | 说明 |
|------|------|------|
| standard | `/article-craft` | 完整流水线（默认） |
| quick | `/article-craft --quick` | 跳过图片生成 |
| draft | `/article-craft --draft` | 仅生成初稿 |
| series | `/article-craft --series FILE` | 多篇系列文章（或独立用 `/article-craft:series`） |

---

## 依赖清单

### 必选

| 依赖 | 安装命令 | 用途 |
|------|---------|------|
| Python 3.10+ | — | 运行时 |
| shot-scraper | `pip3 install shot-scraper` | 网页截图 |
| Playwright | `shot-scraper install` | 浏览器引擎 |
| MINIMAX_API_KEY | `~/.claude/env.json` | 图片生成主链路 |

### 可选

| 依赖 | 安装命令 | 用途 |
|------|---------|------|
| PicGo CLI | `npm install -g picgo` | 图片 CDN 上传 |
| GEMINI_API_KEY | `~/.claude/env.json` | Gemini fallback / `--enhance` |
| yt-dlp | `pip3 install yt-dlp` | YouTube 视频解析 |
| NotebookLM CLI | `uv tool install notebooklm-cli` | 长文调研 / 资料整理 |

---

## 常见问题

### Q: shot-scraper install 报错

```bash
pip3 install playwright
playwright install chromium
```

### Q: PicGo 上传失败

确保 GitHub Token 有 `repo` 权限，格式为 `ghp_xxxxxxxxxxxx`。

### Q: Gemini API 403/429

- 403：API Key 无效，检查 [Google AI Studio](https://aistudio.google.com/app/apikey)
- 429：配额超限，等待后重试

### Q: 找不到插件命令

确保插件在 `~/.claude/plugins/article-craft/`，重启 Claude Code。

---

## 升级

```bash
cd ~/.claude/plugins/article-craft
git pull
bash install.sh
```

---

## 卸载

```bash
rm -rf ~/.claude/plugins/article-craft
```
