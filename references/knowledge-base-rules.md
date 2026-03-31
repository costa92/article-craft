# Knowledge Base Integration (知识库目录规则)

> Adapted from article-generator v3.3 for article-craft plugin

**当用户的工作目录是 Obsidian 知识库时，文章必须保存到对应的分类目录，而非当前目录。**

## 知识库识别

通过以下特征判断用户是否在知识库项目中工作：
- 存在 `01-工作/`、`02-技术/`、`03-创作/` 等编号目录
- 存在 `.obsidian/` 目录
- 用户明确指定了知识库路径

## 目录映射规则

**Markdown 源文件 → `02-技术/` 下对应子目录：**

| 文章主题 | 保存目录 | 示例 |
|----------|---------|------|
| AI 工具/产品 | `02-技术/AI-生态/工具/` | Cursor、Windsurf 评测 |
| AI 模型评测 | `02-技术/AI-生态/模型评测/` | GPT-5、Claude 4 对比 |
| AI Agent | `02-技术/AI-生态/Agent/` | Agent 架构、MCP 协议 |
| Claude Code | `02-技术/AI-生态/Claude-Code/` | Claude Code 技巧、Skills、插件 |
| ClawdBot | `02-技术/AI-生态/ClawdBot/` | ClawdBot 使用指南 |
| Ollama | `02-技术/AI-生态/Ollama/` | 本地模型部署 |
| OpenClaw | `02-技术/AI-生态/OpenClaw/` | OpenClaw 部署和使用 |
| RAG | `02-技术/AI-生态/RAG/` | 检索增强生成 |
| Go 语言 | `02-技术/基础设施/Go/` | Go 教程、源码分析 |
| Cloudflare | `02-技术/基础设施/Cloudflare/` | CDN、Workers、Pages |
| Docker/K8s 等 | `02-技术/基础设施/<工具名>/` | 自动创建对应子目录 |
| Obsidian | `02-技术/工作流/Obsidian/` | Obsidian 插件、工作流 |
| n8n 自动化 | `02-技术/工作流/n8n/` | 工作流自动化（按需创建） |
| 漫画生成 | `02-技术/工作流/漫画生成/` | AI 漫画 |
| **新主题** | `02-技术/<新建目录>/` | 自动创建 |

## 执行规则

1. **自动匹配**：根据文章内容关键词自动匹配最佳目录
2. **自动创建**：目录不存在时用 `mkdir -p` 创建
3. **绝不硬编码路径**：使用知识库根目录变量拼接路径，不写死绝对路径
4. **在知识库目录执行**：所有命令（图片生成、文件保存等）都在知识库根目录下执行
5. **微信 HTML 输出**：转换后的 HTML 统一保存到 `03-创作/已发布/<年月>/`（如 `03-创作/已发布/2026-03/`）

## 示例流程

```bash
# 假设知识库根目录为 PROJECT_ROOT
PROJECT_ROOT=/home/user/onedrive/docs  # 从用户 pwd 或参数获取

# 写一篇 Claude Code 技巧文章 → 匹配 02-技术/AI-生态/Claude-Code/
ARTICLE_DIR="${PROJECT_ROOT}/02-技术/AI-生态/Claude-Code"
mkdir -p "${ARTICLE_DIR}"
# Write tool → ${ARTICLE_DIR}/claude-code-tips.md

# 写一篇 Docker 教程 → 自动创建 02-技术/基础设施/Docker/
ARTICLE_DIR="${PROJECT_ROOT}/02-技术/基础设施/Docker"
mkdir -p "${ARTICLE_DIR}"
# Write tool → ${ARTICLE_DIR}/docker-tutorial.md
```
