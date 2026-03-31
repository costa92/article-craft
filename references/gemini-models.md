# Gemini Image Model Fallback Chain

> Adapted from article-generator v3.3 for article-craft plugin
> Model and fallback info for Gemini image generation.

## Default Model

The default image generation model is configured via `env.json`:

```
env.json key: gemini_image_model
```

If not set, the script defaults to `gemini-3-pro-image-preview`.

## Model Fallback Chain

When a model returns 503/429 (overloaded or rate-limited), try the next model in this order:

```
env.json:gemini_image_model (default, highest quality)
  → gemini-3.1-flash-image-preview (mid-tier fallback)
    → gemini-2.5-flash-image (fast, highest availability)
      → give up, keep placeholders
```

## Probe-Then-Batch Strategy

Use `nanobanana.py` for a single lightweight probe, then `generate_and_upload_images.py --process-file` for batch processing.

### Step 1: Probe with default model (pro)

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nanobanana.py \
  --prompt "test" --size 1024x1024 --output /tmp/gemini_probe.jpg
```

If the probe succeeds, proceed with batch:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_and_upload_images.py \
  --process-file /absolute/path/to/article.md
```

### Step 2: Pro fails (503/429) -- fall back to flash probe

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/nanobanana.py \
  --prompt "test" --size 1024x1024 --output /tmp/gemini_probe.jpg \
  --model gemini-2.5-flash-image
```

If flash probe succeeds, batch with flash:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_and_upload_images.py \
  --process-file /absolute/path/to/article.md --model gemini-2.5-flash-image
```

### Step 3: Flash also fails -- skip AI images

Keep `<!-- IMAGE: ... -->` placeholders in the article. Screenshots (shot-scraper) are independent of Gemini and should still execute.

## nanobanana.py Parameters

| Parameter | Required | Description | Default |
|-----------|----------|-------------|---------|
| `--prompt` | yes | Image description prompt (Chinese or English) | - |
| `--size` | no | Image dimensions (see supported sizes) | 768x1344 |
| `--output` | no | Output file path | nanobanana-<UUID>.png |
| `--model` | no | Gemini model override | gemini-3-pro-image-preview |
| `--resolution` | no | Resolution quality (1K/2K/4K) | 1K |

## Supported Image Sizes

Only these exact sizes are accepted by the Gemini API:

| Size | Aspect | Typical Use |
|------|--------|-------------|
| `1344x768` | 16:9 | Cover image (crop to 900x383 for WeChat) |
| `1248x832` | 3:2 | Body landscape image (most common) |
| `1152x896` | 5:4 | Architecture / flow diagrams |
| `1024x1024` | 1:1 | Square product images |
| `832x1248` | 2:3 | Portrait / mobile screenshots |
| `768x1344` | 9:16 | Mobile vertical |
| `1536x672` | 21:9 | Ultra-wide / panorama |
| `896x1152` | 4:5 | - |
| `1184x864` | 4:3 | - |
| `864x1184` | 3:4 | - |

## Retry Strategy

On transient failure (network, SSL, rate-limit):

1. Wait 2 seconds, retry
2. Wait 3 seconds, retry
3. After 3 total failures, ask user whether to continue

## Key Reminders

- `nanobanana.py` does NOT auto-create output directories -- run `mkdir -p` first.
- Screenshots (shot-scraper) are independent of Gemini and always execute.
- After a successful probe, batch processing must happen in the same session.
