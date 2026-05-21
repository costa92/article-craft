# env.json 配置指南

article-craft 通过 `~/.claude/env.json` 统一管理所有配置项。这是 Claude Code 插件的共享配置中心，所有 API Key 和偏好设置都集中存放于此。

## 文件位置

```
~/.claude/env.json
```

如果文件不存在，请手动创建，或从项目内的 [env.example.json](./env.example.json) 模板复制：

```bash
cp ${CLAUDE_PLUGIN_ROOT:-~/.claude/plugins/article-craft}/env.example.json ~/.claude/env.json
# 然后编辑 ~/.claude/env.json 填入真实 API Key
```

## 完整配置示例

完整模板见仓库根的 [`env.example.json`](./env.example.json)。下面是同一份示例的内联版：

```json
{
  "minimax_api_key": "YOUR_MINIMAX_API_KEY",
  "image_model": "minimax-image-01",
  "minimax_image_model": "minimax-image-01",
  "gemini_api_key": "YOUR_GEMINI_API_KEY",
  "gemini_image_model": "gemini-3-pro-image-preview",
  "gemini_text_model": "gemini-2.0-flash",
  "openai_api_key": "YOUR_OPENAI_API_KEY",
  "stable_diffusion_endpoint": "http://127.0.0.1:7860",
  "user_name": "",
  "share_card_logo": "",
  "verify_cdn_whitelist": [
    "cdn.jsdelivr.net",
    "mmbiz.qpic.cn",
    "pbs.twimg.com"
  ],
  "timeouts": {
    "image_generation": 120,
    "upload": 60,
    "dependency_check": 5,
    "npm_install": 120
  },
  "s3": {
    "enabled": false,
    "endpoint_url": "",
    "access_key_id": "",
    "secret_access_key": "",
    "bucket_name": "",
    "public_url_prefix": ""
  }
}
```

## 配置项说明

### 必需配置

| 字段 | 类型 | 说明 |
|------|------|------|
| `minimax_api_key` | string | Minimax API Key，用于图片生成 |

### 推荐配置

| 字段 | 类型 | 说明 |
|------|------|------|
| `gemini_api_key` | string | Gemini API Key，用于 fallback / `--enhance` |
| `openai_api_key` | string | OpenAI API Key（B7 Phase 2 起支持）— 用于 `openai-gpt-image-1`。Minimax / Gemini 都不可用时的兜底链末位。可在 [platform.openai.com](https://platform.openai.com/api-keys) 申请。 |
| `stable_diffusion_endpoint` | string | 自建 SD 后端 URL（B7 Phase 3 起支持）— 用于 `sd-local` 模型。指向 Automatic1111 webui（默认 `http://127.0.0.1:7860`）。不在默认 chain 里 —— 显式 `image_model: "sd-local"` 才会用。无需 API Key（本地端点）。 |

### 可选配置

#### 图片模型

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `image_model` | string | `minimax-image-01` | 图片生成默认模型，优先级最高 |
| `minimax_image_model` | string | `minimax-image-01` | Minimax 图片生成模型 |
| `gemini_image_model` | string | `gemini-3-pro-image-preview` | Gemini 回退模型 |

可用模型（按优先级）：
- `minimax-image-01` — 默认首选
- `gemini-3-pro-image-preview` — Gemini 首个回退
- `gemini-3.1-flash-image-preview` — 快速版本
- `gemini-2.5-flash-image` — 轻量级兜底
- `openai-gpt-image-1` — OpenAI 兜底（B7 Phase 2 起；需要 `openai_api_key`）
- `sd-local` — 自建 Stable Diffusion (B7 Phase 3 起；需要 `stable_diffusion_endpoint`)。**不在默认 chain 里**，显式 `image_model: "sd-local"` 才会用。

`filter_chain_by_available_keys` 在生成前会把没有对应 API Key 的模型从链路里剔除，所以即使链路里列了 5 个模型，只配了 OpenAI Key 的用户会直接从 `openai-gpt-image-1` 开始尝试，不会浪费 4 次失败请求。

#### 文本模型（用于 Prompt 扩写）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `gemini_text_model` | string | `gemini-2.0-flash` | `nanobanana.py --enhance` 用于把短提示词扩写成详细图像生成 Prompt 的文本模型 |

仅在显式调用 `nanobanana.py --enhance` 时生效，主流水线（`/article-craft:images`）不依赖。

#### 作者署名

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `user_name` | string | `""`（空） | 文章 frontmatter 的 `author` 字段在 write 阶段从 `config.author_name()` 取值；空时回落到 `git config user.name`，再回落到 `"Anonymous"`。设这个字段就能让 share_card 等下游 skill 不再因为 `author` 缺失而 auto-skip。 |

#### Share Card 品牌 logo

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `share_card_logo` | string | `""`（空） | 分享卡片底部的品牌文字。空时回落到 `.claude-plugin/plugin.json` 的 `name` 字段（默认 `article-craft`）。fork 时无须改源码即可换 logo。 |

#### 知识库目录结构（publish 自动归类）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `kb_category_root` | string | `02-技术` | publish 自动归类时的技术文章顶层目录名。`scripts/publish_plan.py` 的 auto 模式在此目录下递归找最佳子目录。KB 树命名不同的 fork 改这个字段即可，无须改源码。 |
| `kb_uncategorized_dir` | string | `未分类` | 没有任何目录匹配时的兜底子目录名，最终路径为 `{kb_category_root}/{kb_uncategorized_dir}`。 |

#### 截图 cookie 注入（B1，v1.6.6+）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `browser_cookies_path` | string | `""`（未配置） | Playwright 格式 cookies JSON 路径，`screenshot_tool.py` 在 `new_context` 之后注入，解锁登录墙后的页面（HN-HTTPS / Reddit / 知乎 / 微博 / 小红书 等）。空时回落到 `~/.cache/article-craft/cookies.json`（若存在），仍无则跳过 cookie 注入。 |

**格式**：顶层 JSON 数组（Playwright `BrowserContext.cookies()` 输出格式），或 `{"cookies": [...]}` 包装。每条至少需要 `name`、`value`、且 `url` 或 `domain` 至少有一个。示例：

```json
[
  {"name": "session", "value": "abc123", "domain": ".example.com", "path": "/", "secure": true, "sameSite": "Lax"}
]
```

**导出来源**：gstack `setup-browser-cookies` skill、Playwright 自身的 `context.cookies()` dump、浏览器扩展（如 EditThisCookie）的 JSON 导出，或手写。Playwright 按域名自动过滤，加载全部 cookies 安全无副作用。

**CLI 覆盖**：`screenshot_tool.py screenshot --cookies PATH`（高优先级）或 `--no-cookies`（禁用）。

#### CDN 白名单（verify-claims / lint）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `verify_cdn_whitelist` | string[] | `["cdn.jsdelivr.net", "mmbiz.qpic.cn", "pbs.twimg.com"]` | 校验外链时被认为"可直接引用"的 CDN 主机名列表。不在此列的 URL 会被提示需要 rehost 到自家 CDN。 |

如果你用了自己的 CDN（例如 `file.your-domain.com` 或 S3 公开桶），把它加进数组即可。

#### Screenshot 平台主内容识别（v1.5.5+）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `screenshot_main_content_selectors` | `{host: [selector]}` | `{}` | 按域名追加/覆盖 screenshot_tool 的主内容选择器。键是 host 子串（如 `x.com`、`mp.weixin.qq.com`），值是按优先级排序的 CSS selector 列表。`anchor` 关键词搜索 + `suggest_selector` 都用这份配置。 |

内置已经覆盖 X/Twitter、微博、小红书、知乎、微信公众号、Reddit、HN、Stack Overflow、YouTube、B 站、GitHub、Medium、arxiv、npm 等。**只有当你引用的站点不在内置列表里**（自己的博客、私有平台、新平台等），才需要在 env.json 里加：

```json
"screenshot_main_content_selectors": {
  "myblog.com": [".post-body"],
  "internal.tools": ["#article-content"]
}
```

也可以**覆盖**内置默认（比如某平台改版了，你想用更新的 selector）：

```json
"screenshot_main_content_selectors": {
  "weibo.com": [".New_Feed_Content_Container"]
}
```

匹配是 host 子串匹配，所以 `x.com` 会匹配 `x.com` 和 `m.x.com`，`weibo.com` 会匹配 `weibo.com` 和 `m.weibo.com`。

#### 超时配置

| 字段 | 类型 | 默认值（秒） | 说明 |
|------|------|-------------|------|
| `timeouts.image_generation` | int | 120 | 单张图片生成超时 |
| `timeouts.upload` | int | 60 | 图片上传超时 |
| `timeouts.dependency_check` | int | 5 | 依赖检测超时 |
| `timeouts.npm_install` | int | 120 | npm 安装超时 |

#### S3 图床（可选）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `s3.enabled` | bool | `false` | 是否启用 S3 图床 |
| `s3.endpoint_url` | string | `""` | S3 兼容存储的端点 URL |
| `s3.access_key_id` | string | `""` | S3 Access Key |
| `s3.secret_access_key` | string | `""` | S3 Secret Key |
| `s3.bucket_name` | string | `""` | S3 Bucket 名称 |
| `s3.public_url_prefix` | string | `""` | 公开访问的 URL 前缀 |

## 环境变量覆盖

S3 配置支持通过环境变量覆盖 JSON 中的值：

| 环境变量 | 对应 JSON 字段 |
|---------|---------------|
| `S3_ENDPOINT` | `s3.endpoint_url` |
| `S3_ACCESS_KEY` | `s3.access_key_id` |
| `S3_SECRET_KEY` | `s3.secret_access_key` |
| `S3_BUCKET` | `s3.bucket_name` |
| `S3_PUBLIC_URL` | `s3.public_url_prefix` |

### 缓存目录覆盖

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `ARTICLE_CRAFT_CACHE_DIR` | `~/.cache/article-craft/` | 持久化缓存目录（verify cache、screenshot cache 等）。所有跨进程缓存都通过 `scripts/config.py:cache_dir()` 解析此路径，CI 和容器环境中可用此变量重定向到可写目录。 |

## 验证配置

安装完成后，运行以下命令验证配置是否正确：

```bash
cd ~/.claude/plugins/article-craft
bash install.sh
```

## 常见问题

### Q: `minimax_api_key` 缺失

当前图片主链路默认走 Minimax。请在 `~/.claude/env.json` 中配置 `minimax_api_key`，或导出 `MINIMAX_API_KEY` 环境变量。

### Q: `gemini_api_key` 报错 403

Gemini fallback Key 无效或未设置。前往 [Google AI Studio](https://aistudio.google.com/app/apikey) 创建新 Key。

### Q: `gemini_api_key` 报错 429

API 配额超限。可降级图片模型为 `gemini-2.5-flash-image`，或等待配额重置后重试。

### Q: 图片上传失败

确保配置了 PicGo 或 S3：
- **PicGo**: `npm install -g picgo && picgo set uploader`
- **S3**: 将 `s3.enabled` 设为 `true` 并填写相关配置

## 相关文档

- [INSTALL.md](./INSTALL.md) — 完整安装指南
- [scripts/config.py](./scripts/config.py) — 配置加载源码
