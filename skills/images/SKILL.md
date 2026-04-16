---
name: article-craft:images
version: 1.4.16
description: "Generate and upload images for technical articles using Gemini API. Use when adding cover images, rhythm images, or screenshots to an article."
allowed-tools:
  - Read
  - Edit
  - Bash
  - Grep
  - AskUserQuestion
---

# Images

Generate and upload images for technical articles using Gemini API, with screenshot support via screenshot_tool.py (Playwright).

## Inputs

- **article.md file path** -- article containing image placeholders in the format:
  ```markdown
  <!-- IMAGE: name - description (ratio) -->
  <!-- PROMPT: detailed prompt for Gemini image generation -->
  ```
- **Standalone mode:** If no file path is provided as argument, use `AskQuestion` to ask the user for the article file path.

## Process

### 1. Resolve Absolute Path

```bash
realpath article.md
```

All downstream scripts require absolute paths. Relative paths cause misleading errors.

### 2. Gemini Probe Test

Run a lightweight single-image probe to verify API availability before batch processing.

```bash
# Step 1: Probe with default model (pro -- highest quality)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nanobanana.py \
  --prompt "test" --size 1024x1024 --output /tmp/gemini_probe.jpg
```

- **Success** -- proceed to batch processing with the default model.
- **Fail (503/429/No data received)** -- fall back to flash model:

```bash
# Step 2: Probe with flash model
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nanobanana.py \
  --prompt "test" --size 1024x1024 --output /tmp/gemini_probe.jpg \
  --model gemini-2.5-flash-image
```

- **Flash succeeds** -- proceed to batch processing with `--model gemini-2.5-flash-image`.
- **Flash also fails** -- skip AI image generation, keep placeholders, warn user.

**Full model fallback chain:**

```
env.json:gemini_image_model (default, highest quality)
  -> gemini-3.1-flash-image-preview (mid-tier fallback)
    -> gemini-2.5-flash-image (fast, highest availability)
      -> give up, keep placeholders
```

### 3. Batch Process Article

After a successful probe, run the batch processor in the same session:

```bash
# Default model succeeded
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_and_upload_images.py \
  --process-file /ABSOLUTE/PATH/article.md

# Or if fell back to flash model
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_and_upload_images.py \
  --process-file /ABSOLUTE/PATH/article.md --model gemini-2.5-flash-image
```

### 3.5 Incremental Mode (skip already-uploaded images)

When re-running images on an article that already has some CDN URLs (e.g., after editing and adding new placeholders), use incremental mode to skip images that were already processed:

**How it works:** Before processing, scan the article for existing `![...](https://cdn...)` lines. Extract image names. Skip any `<!-- IMAGE: name -->` placeholder whose name matches an existing CDN image.

**Execution:**
1. Grep for existing CDN URLs in the article: `grep -o '!\[.*\](https://cdn[^)]*)'`
2. Extract placeholder names from `<!-- IMAGE: name - description -->`
3. Compare: if a name already has a CDN URL in the article, skip it
4. Only process remaining `<!-- IMAGE: -->` placeholders that have no CDN equivalent

```bash
# Manual incremental: first check what's already done
grep -c 'cdn.jsdelivr.net' /ABSOLUTE/PATH/article.md  # existing images
grep -c '<!-- IMAGE:' /ABSOLUTE/PATH/article.md        # remaining placeholders

# If remaining > 0, run batch (it only processes <!-- IMAGE: --> placeholders)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_and_upload_images.py \
  --process-file /ABSOLUTE/PATH/article.md --continue-on-error
```

> [!tip] The batch processor already skips replaced placeholders
> `generate_and_upload_images.py --process-file` only matches `<!-- IMAGE: -->` comments.
> Already-replaced images (now `![...](url)`) are not matched. So re-running the
> batch processor on a partially-processed article is inherently incremental.

This script performs the full pipeline:
1. Parses `<!-- IMAGE: ... -->` and `<!-- PROMPT: ... -->` placeholders from the article
2. Generates images via Gemini API
3. Uploads to CDN (PicGo or S3)
4. Replaces placeholders with CDN URLs in the article file (in-place)

Additional flags:
- `--resolution 2K` -- higher resolution output
- `--parallel` -- parallel generation (2 workers, ~1.87x faster)
- `--continue-on-error` -- skip failed images instead of aborting

### 4. Verify No Placeholder Residue

```bash
grep -n '<!-- IMAGE:' /ABSOLUTE/PATH/article.md
```

- No matches -- all images processed successfully.
- Matches found -- some images failed; list them in the completion summary.

### 5. Screenshots (Independent of Gemini)

Screenshots use `screenshot_tool.py` (Playwright) and always work regardless of Gemini API status.

When using `--process-file`, screenshots (`<!-- SCREENSHOT: ... -->`) are handled automatically. For standalone screenshots:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/screenshot_tool.py screenshot "https://example.com" \
  -o /tmp/screenshot.png -w 3
picgo upload /tmp/screenshot.png
```

Screenshot placeholder format:
```markdown
<!-- SCREENSHOT: https://example.com -->
<!-- SCREENSHOT: https://example.com #element-selector -->
<!-- SCREENSHOT: https://example.com WAIT:3 -->
```

Optional parameters:
- `#selector` — CSS 选择器，只截取该元素
- `WAIT:N` — 额外等待 N 秒（SPA 页面）
- `WIDTH:N` — 视口宽度（默认 1280）

**截图流程**（自动执行）：
1. HEAD 请求预检 URL（检测 404/403/5xx）
2. Playwright 渲染（等待网络空闲）
3. 空页面 / 404 文本检测
4. 智能选择器推荐（GitHub/Twitter/Stack Overflow 等）
5. 截图 → Pillow 压缩 → CDN 上传

## CRITICAL Rules

### Absolute Paths Only

**ALWAYS use absolute paths, never relative.** Relative paths cause misleading "missing API key" errors.

```bash
# WRONG
--process-file ./article.md

# CORRECT
--process-file /Users/you/articles/article.md
```

### Image Placeholder Format

Two consecutive HTML comments:

```markdown
<!-- IMAGE: name - description (ratio) -->
<!-- PROMPT: detailed prompt for Gemini image generation -->
```

### Supported Aspect Ratios

| Ratio | Resolution | Usage |
|-------|-----------|-------|
| `16:9` | 1344x768 | Cover image |
| `3:2` | 1248x832 | Rhythm image (recommended) |
| `5:4` | 1152x896 | Architecture / flow diagrams |
| `1:1` | 1024x1024 | Square |
| `9:16` | 768x1344 | Vertical / mobile |
| `21:9` | 1536x672 | Ultra-wide / panorama |

### Image Placement Rules

- **Cover image:** 16:9 (1344x768), placed at the top of the article
- **Rhythm images:** 3:2 (1248x832), one every 400-600 words
- **Typical count:** 1 cover + 4-6 rhythm images per 3000-word article
- **No duplicate images** in the same section (e.g., two versions of the same diagram)
- **SCREENSHOT placeholders must NOT be inserted between Markdown list items** -- place after the list block

### Script Distinction

- `nanobanana.py` -- single-image generation, used for **probes only** (does NOT auto-create output directories; run `mkdir -p` first)
- `generate_and_upload_images.py` -- batch processor with `--process-file`, used for **all production image generation**

## Error Handling

Graceful degradation:

1. **Gemini probe fails on all models** -- keep `<!-- IMAGE: ... -->` placeholders in the article. Log which images were not generated. Screenshots still execute.
2. **Individual image fails during batch** -- with `--continue-on-error`, skip that image and continue. Failed placeholders remain in the article.
3. **Upload fails** -- fail-fast to prevent broken image links in the article.
4. **Network/SSL errors** -- auto-retry 3 times with 2-3 second delays.
5. **Directory errors** -- auto-fix with `mkdir -p`.

Always report in the completion summary:
- Total images: X generated / Y total
- Failed images: list names and placeholder locations
- Executable command for re-trying failed images

## Outputs

- `article.md` updated in-place with CDN URLs replacing image placeholders
- Any remaining `<!-- IMAGE: ... -->` placeholders indicate failed generations

## Hand-off

Next skill: **article-craft:review**

## Standalone Mode

This skill operates in **dual-mode**:

1. **Pipeline mode:** Receives the article file path as an argument from the orchestrator or a previous skill.
2. **Standalone mode:** If invoked directly without a file path, uses `AskQuestion` to prompt the user for the article file path.

Reference: [image-guide.md](./image-guide.md) for detailed placeholder syntax, prompt patterns, and aspect ratio details.
