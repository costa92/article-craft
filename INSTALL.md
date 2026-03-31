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
- 配置 Gemini API Key
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

### Gemini API Key

编辑 `~/.claude/env.json`：

```json
{
  "gemini_api_key": "YOUR_KEY_HERE"
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
├── skills/                     # 11 个 Skill 模块
│   ├── orchestrator/          # 主编排器
│   ├── write/                 # 文章生成
│   ├── images/                 # 图片生成
│   ├── screenshot/            # 网页截图
│   ├── requirements/           # 需求采集
│   ├── verify/                # 预写验证
│   ├── review/                # 质量评分
│   ├── publish/               # 发布入库
│   ├── lint/                 # 风格检查
│   ├── series/               # 系列管理
│   └── youtube/              # 视频转文章
├── commands/                   # CLI 命令封装
├── scripts/                    # Python 自动化脚本
│   ├── nanobanana.py                  # 单张图片生成
│   ├── generate_and_upload_images.py  # 批量图片处理
│   ├── config.py                      # 配置常量
│   ├── utils.py                       # 工具函数
│   ├── setup_dependencies.py          # 依赖检测
│   ├── pipeline_state.py             # 流水线状态
│   ├── review_selfcheck.py           # 自检规则
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

# 单独使用
/article-write       # 生成文章
/article-images      # 生成图片
/article-review      # 审核评分
/article-lint        # 风格检查
/article-screenshot  # 网页截图
/article-youtube     # YouTube 转文章
```

### 四种工作流模式

| 模式 | 命令 | 说明 |
|------|------|------|
| standard | `/article-craft` | 完整流水线（默认） |
| quick | `/article-craft --quick` | 跳过图片生成 |
| draft | `/article-craft --draft` | 仅生成初稿 |
| series | `/article-series` | 多篇系列文章 |

---

## 依赖清单

### 必选

| 依赖 | 安装命令 | 用途 |
|------|---------|------|
| Python 3.10+ | — | 运行时 |
| shot-scraper | `pip3 install shot-scraper` | 网页截图 |
| Playwright | `shot-scraper install` | 浏览器引擎 |
| PicGo CLI | `npm install -g picgo` | 图片 CDN 上传 |
| GEMINI_API_KEY | `~/.claude/env.json` | 图片生成 |

### 可选

| 依赖 | 安装命令 | 用途 |
|------|---------|------|
| yt-dlp | `pip3 install yt-dlp` | YouTube 视频解析 |
| content-reviewer | Claude Code skill | 7 维度文章评分 |

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
