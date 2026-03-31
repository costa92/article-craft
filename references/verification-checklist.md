# Pre-Writing Verification Checklist

> Adapted from article-generator v3.3 for article-craft plugin

**核心原则：验证先行，绝不编造。只报告失败项，通过的不输出。**

## 批量验证策略（减少 bash 调用次数）

**链接验证：一次 bash 调用验证所有 URL（含 HEAD→GET 降级）**
```bash
for url in \
  "https://example1.com" \
  "https://example2.com" \
  "https://example3.com"; do
  code=$(curl -sI -o /dev/null -w "%{http_code}" --max-time 10 "$url")
  if [ "$code" = "405" ] || [ "$code" = "000" ]; then
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url")
  fi
  [ "$code" != "200" ] && echo "FAIL $code $url"
done
# 无输出 = 全部通过
# 405 = 服务器不支持 HEAD，自动降级 GET 重试
```

**命令验证：有依赖的链式执行，无依赖的并行调用**
```bash
# 有依赖关系的命令 → 一条 bash 用 && 链接
cd /tmp && rm -rf test-proj && mkdir test-proj && cd test-proj && \
  uv init --name test && uv add requests && \
  uv run python -c "import requests; print(requests.__version__)" && \
  uv tree

# 无依赖的验证 → 多个 bash 调用并行发起
```

**301 重定向处理**
```bash
curl -sI -o /dev/null -w "%{http_code} %{redirect_url}" --max-time 10 URL
# 301 → 跟踪目标，使用最终 URL
```

## Trusted Tools Whitelist (Skip Verification)

**Development Tools:**
- Docker, Kubernetes, Git, npm, yarn, pnpm, pip, cargo, Maven, Gradle
- Node.js, Python, Go, Rust, Java, TypeScript, Ruby

**OS & Package Managers:** apt, yum, dnf, brew, pacman, apk, snap

**Common CLI Tools:** curl, wget, ssh, scp, rsync, grep, sed, awk, tar, gzip

**When to verify anyway:**
- Niche flags or options (e.g., `docker run --gpus`)
- Version-specific features (e.g., "Docker 24.0+ only")
- Deprecated commands
- Any command you're unsure about

## Step 0: Feature Discovery (MANDATORY for tool/project articles)

写工具类文章时，必须先摸清工具的完整功能面，避免遗漏重要新功能。

**判断路径**：先检查工具是否本地已安装，再选择对应的发现方式。

### 路径 A：工具已安装

```bash
# 1. 检查是否已安装
which tool 2>/dev/null && tool --version

# 2. 全量扫描子命令
tool --help

# 3. 逐个检查不熟悉的子命令
tool subcommand --help
```

### 路径 B：工具未安装 → Docker 临时环境（优先）

本地没有的工具，用 Docker 创建临时环境来获取**真实命令输出和截图**，比从文档抄来的更可信。

```bash
# 1. 查找官方 Docker 镜像
docker search tool-name --limit 5
# 或直接查 Docker Hub
curl -s "https://hub.docker.com/v2/repositories/library/tool-name" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('description','')[:200])"

# 2. 启动临时容器（用完即删）
docker run --rm -it tool-image:latest sh
# 或后台运行用于截图
docker run --rm -d --name tool-test -p 8080:8080 tool-image:latest

# 3. 在容器中执行功能发现
docker exec tool-test tool --help
docker exec tool-test tool subcommand --help

# 4. 获取真实命令输出（写入文章）
docker exec tool-test tool version
docker exec tool-test tool list

# 5. 用完清理
docker stop tool-test 2>/dev/null; docker rm tool-test 2>/dev/null
```

**Docker 环境的额外价值**：
- 命令输出是真实的，不是从文档复制的
- 可以对容器内的 Web UI 做截图（`shot-scraper http://localhost:8080`）
- 代码示例可以在容器内实际运行验证
- 读者也能用同样的 Docker 命令复现

**没有官方 Docker 镜像时的降级**：

```bash
# 用基础镜像手动安装
docker run --rm -it ubuntu:22.04 bash -c "
  apt-get update && apt-get install -y curl &&
  curl -fsSL https://install.tool.com | sh &&
  tool --help
"

# 或用 Python 工具
docker run --rm -it python:3.12-slim bash -c "
  pip install tool-name &&
  tool --help
"
```

### 路径 B 降级：无法 Docker 时用远程信息源

```bash
# 1. GitHub 仓库 README（最权威的功能概览）
curl -s "https://api.github.com/repos/org/repo/readme" | \
  python3 -c "import sys,json,base64; print(base64.b64decode(json.load(sys.stdin)['content']).decode())" | head -100

# 2. 官方文档 CLI 参考页
curl -s "https://docs.tool.com/cli" | sed 's/<[^>]*>/ /g' | tr -s ' \n' | head -80

# 3. GitHub releases（最近版本的新功能）
gh api repos/org/repo/releases --jq '.[0:3][] | "\(.tag_name): \(.name)"'
```

**选择优先级**：本地 `--help`（最准确）→ Docker 临时环境（真实数据）→ GitHub README → 官方文档 → WebSearch

### 通用：官方博客/Changelog 扫描

```bash
# 抓取最近博客标题（识别新功能）
curl -s "https://tool-website.com/blog" | \
  sed 's/<[^>]*>/ /g' | tr -s ' \n' | \
  grep -i "new\|launch\|release\|feature" | head -10
```

### 功能清单对比

- 列出所有子命令/功能（来自 --help 或 README）
- 标记"已知基础功能" vs "新功能/不确定功能"
- 新功能必须纳入文章章节规划
- 不确定的功能 → 查官方文档确认后再决定是否纳入

**触发条件**：文章主题是某个工具/项目/框架时必须执行。纯概念性文章（如"微服务架构"）可跳过。

## Step 1: Tool/Project Research (MANDATORY for non-whitelisted tools)

1. **使用 WebSearch 查找官方文档**
   ```
   WebSearch(search_term="[tool_name] official documentation")
   WebSearch(search_term="[tool_name] GitHub repository")
   ```

2. **验证工具真实存在**
   - 检查官方网站
   - 确认 GitHub 仓库（星标数、维护状态）
   - 阅读 README 和官方文档

3. **理解实际功能**
   - 不要根据工具名称推测功能
   - 不要根据"常识"假设用法
   - 必须从官方文档确认功能

## Step 2: Command/Feature Verification (MANDATORY)

1. **命令存在性验证**
   - 在官方文档中找到该命令
   - 参数、选项与官方文档一致
   - 无法找到文档 → 该命令不存在，不要包含

2. **代码示例验证**
   - 代码是完整可运行的
   - API 用法与官方示例一致
   - 依赖版本明确标注

3. **配置文件验证**
   - 配置项在官方文档中存在
   - 值的格式正确

**Exception**: Whitelisted tools' basic commands can be trusted

## Step 3: Workflow Validation (MANDATORY)

1. **步骤完整性** - 每一步都有官方文档支持
2. **依赖关系验证** - 前置条件、版本兼容性、环境要求
3. **潜在问题标记** - 不确定 → 标记 "[需要验证]"，绝不用"合理假设"填补空白

## Step 4: Link Verification (MANDATORY)

1. **验证链接可用性**（按可靠性排序）
   ```bash
   # 首选：curl 直接验证（最稳定，不受 MCP 余额/网络限制）
   curl -sI -o /dev/null -w "%{http_code}" --max-time 10 https://example.com
   # 200 = OK, 301/302 = 重定向（需跟踪目标确认），404 = 不存在

   # 备选：WebFetch（可能受网络限制或余额不足）
   WebFetch(url="https://example.com")
   ```
2. **链接类型要求**
   - 官方文档链接（优先）
   - GitHub 官方仓库
   - 经验证的技术博客
   - 社交媒体链接（X/Twitter、微博等）→ 改为纯文字引用（作者 + 平台 + 日期），不放 URL
3. **链接格式** - 使用 `**名称**: https://url`，不使用 `[[Obsidian links]]`
4. **301 重定向处理** — 跟踪重定向目标，使用最终 URL：
   ```bash
   curl -sI -o /dev/null -w "%{http_code} %{redirect_url}" --max-time 10 URL
   ```

## Step 5: Pre-Generation Report (MANDATORY)

验证完成后，**只报告失败和待处理项**，通过的不输出：

```markdown
## 验证结果

### 失败项
- [URL] 返回 404，已替换为 [新URL]
- [命令X] 在官方文档中未找到，已移除

### 待确认
- [工具Y] 的高级配置选项无法验证，标记为 [需要验证]

（无失败项时输出：全部验证通过）
```

## Enforcement Rules

| 情况 | 处理方式 |
|------|---------|
| 编造的命令/功能 | **拒绝整篇文章** |
| 未验证的声明 | **询问用户或省略该部分** |
| 无法验证的工作流 | **标记或移除** |
| 404 链接 | **移除或替换** |
| 有疑问的内容 | **询问用户，绝不猜测** |

## Quick Reference

生成文章前，确保：
- [ ] 所有非白名单工具已通过官方文档验证
- [ ] 所有命令在官方文档中存在
- [ ] 所有代码示例完整可运行
- [ ] 所有链接已通过 `curl -sI` 验证（HTTP 200）
- [ ] 多步骤教程每一步都有文档支持
- [ ] 失败项已修复或移除，通过项不输出

## 优化建议

### 1. 会话级验证缓存（待实现）
- 使用临时文件或内存存储已验证的工具/命令信息
- 缓存结构：`{tool_name: {commands: [cmd1, cmd2], timestamp: 1710000000}}`
- 同一会话内，已验证的工具/命令无需重复验证
- 会话结束后自动清理缓存，确保信息新鲜度

### 2. 图片生成与文章写作并行（待实现）
- 支持边写边生成常用图片（如封面图）
- 提高整体创作效率

### 3. 智能图片占位符管理（待实现）
- 自动检测并保留有价值的图片提示词
- 快速模式下自动优化占位符维护

### 4. 知识库目录匹配优化（待实现）
- 基于文章内容自动学习和调整目录匹配策略
- 支持用户自定义目录映射规则
