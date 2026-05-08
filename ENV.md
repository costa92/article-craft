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
  "gemini_api_key": "YOUR_GEMINI_API_KEY",
  "gemini_image_model": "gemini-3-pro-image-preview",
  "gemini_text_model": "gemini-2.0-flash",
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
| `gemini_api_key` | string | Gemini API Key，用于图片生成。从 [Google AI Studio](https://aistudio.google.com/app/apikey) 获取 |

### 可选配置

#### 图片模型

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `gemini_image_model` | string | `gemini-3-pro-image-preview` | Gemini 图片生成模型，支持链式降级 |

可用模型（按优先级）：
- `gemini-3-pro-image-preview` — 最新最强，优先使用
- `gemini-3.1-flash-image-preview` — 快速版本
- `gemini-2.5-flash-image` — 轻量级兜底

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

### Q: `gemini_api_key` 报错 403

API Key 无效或未设置。前往 [Google AI Studio](https://aistudio.google.com/app/apikey) 创建新 Key。

### Q: `gemini_api_key` 报错 429

API 配额超限。可降级图片模型为 `gemini-2.5-flash-image`，或等待配额重置后重试。

### Q: 图片上传失败

确保配置了 PicGo 或 S3：
- **PicGo**: `npm install -g picgo && picgo set uploader`
- **S3**: 将 `s3.enabled` 设为 `true` 并填写相关配置

## 相关文档

- [INSTALL.md](./INSTALL.md) — 完整安装指南
- [scripts/config.py](./scripts/config.py) — 配置加载源码
