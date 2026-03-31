# env.json 配置指南

article-craft 通过 `~/.claude/env.json` 统一管理所有配置项。这是 Claude Code 插件的共享配置中心，所有 API Key 和偏好设置都集中存放于此。

## 文件位置

```
~/.claude/env.json
```

如果文件不存在，请手动创建。

## 完整配置示例

```json
{
  "gemini_api_key": "YOUR_GEMINI_API_KEY",
  "gemini_image_model": "gemini-3-pro-image-preview",
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
