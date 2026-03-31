#!/usr/bin/env python3
"""
Article-Craft Share Card Generator

生成各平台分享卡片图片（PNG）：
- 微信封面 / 微信分享
- 小红书封面 / 小红书方图
- Twitter/X / LinkedIn / Facebook
- 掘金 / 知乎

使用 Playwright 渲染 HTML → 截图 → 上传 CDN
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, Error as PlaywrightError
except ImportError:
    print("❌ Missing: playwright. Run: pip install playwright && playwright install chromium")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print("❌ Missing: Pillow. Run: pip install Pillow")
    sys.exit(1)

# ─── 平台配置 ────────────────────────────────────────────────────────────────

PLATFORMS = {
    # 平台名: (宽度, 高度, 标题字号, 描述字号, 描述行数)
    "wechat-cover":    (900,  383, 36, 16, 2),   # 公众号封面
    "wechat-share":    (500,  400, 28, 14, 2),   # 微信分享
    "xiaohongshu":     (1080, 1440, 48, 20, 3),  # 小红书竖图
    "xiaohongshu-sq":  (1080, 1080, 44, 18, 3),  # 小红书方图
    "twitter":         (1200, 628,  42, 18, 2),  # Twitter/X
    "linkedin":        (1200, 627,  42, 18, 2),  # LinkedIn
    "facebook":        (1200, 630,  42, 18, 2),  # Facebook
    "juejin":          (1200, 600,  42, 18, 2),  # 掘金
    "zhihu":           (1200, 600,  42, 18, 2),   # 知乎
    "twitter-card":    (1200, 628,  42, 18, 2),   # Twitter Card (alias)
}

# 预设色板
COLOR_PRESETS = {
    "tech-blue": {
        "bg": "linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%)",
        "accent": "#00d4ff",
        "tag_bg": "rgba(0,212,255,0.15)",
        "tag_border": "rgba(0,212,255,0.3)",
    },
    "sunset": {
        "bg": "linear-gradient(135deg, #2b1055 0%, #7597de 50%, #ff6b95 100%)",
        "accent": "#ff6b95",
        "tag_bg": "rgba(255,107,149,0.15)",
        "tag_border": "rgba(255,107,149,0.3)",
    },
    "forest": {
        "bg": "linear-gradient(135deg, #0f3443 0%, #34e89e 50%, #0f3443 100%)",
        "accent": "#34e89e",
        "tag_bg": "rgba(52,232,158,0.15)",
        "tag_border": "rgba(52,232,158,0.3)",
    },
    "midnight": {
        "bg": "linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 50%, #16213e 100%)",
        "accent": "#ffd700",
        "tag_bg": "rgba(255,215,0,0.15)",
        "tag_border": "rgba(255,215,0,0.3)",
    },
    "ember": {
        "bg": "linear-gradient(135deg, #1e130c 0%, #9a3807 50%, #eaaf0b 100%)",
        "accent": "#eaaf0b",
        "tag_bg": "rgba(234,175,11,0.15)",
        "tag_border": "rgba(234,175,11,0.3)",
    },
    "deep-blue": {
        "bg": "linear-gradient(135deg, #0c3483 0%, #a2b6df 50%, #6b8cce 100%)",
        "accent": "#ffffff",
        "tag_bg": "rgba(255,255,255,0.15)",
        "tag_border": "rgba(255,255,255,0.25)",
    },
    "slate": {
        "bg": "linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 50%, #1a1a1a 100%)",
        "accent": "#10b981",
        "tag_bg": "rgba(16,185,129,0.15)",
        "tag_border": "rgba(16,185,129,0.3)",
    },
}

DEFAULT_PRESET = "tech-blue"


# ─── HTML 模板生成 ─────────────────────────────────────────────────────────────

def make_card_html(title: str, description: str, tags: list, author: str,
                   width: int, height: int, title_size: int,
                   desc_size: int, desc_lines: int, preset: dict,
                   platform: str) -> str:
    """生成卡片 HTML"""

    # 截断标题和描述
    title = title.strip()
    if len(title) > 60:
        title = title[:57] + "..."

    description = description.strip()
    if len(description) > 150:
        description = description[:147] + "..."

    # 生成标签 HTML
    tags_html = ""
    for tag in tags[:5]:  # 最多 5 个标签
        tag = tag.strip()
        if tag:
            tags_html += f'<span class="tag">{tag}</span>'

    # 平台 Logo（可选）
    logo_html = ""
    if platform in ("twitter", "twitter-card"):
        logo_html = '<div class="platform-icon">𝕏</div>'
    elif platform == "linkedin":
        logo_html = '<div class="platform-icon">in</div>'

    # 布局调整（根据尺寸）
    is_vertical = height > width  # 小红书竖图等
    padding = int(min(width, height) * 0.06)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width={width}">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  width: {width}px;
  height: {height}px;
  background: {preset['bg']};
  font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans SC", -apple-system, sans-serif;
  color: #fff;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}}

/* 装饰性背景元素 */
body::before {{
  content: '';
  position: absolute;
  top: -{height * 0.3}px;
  right: -{width * 0.2}px;
  width: {width * 0.6}px;
  height: {width * 0.6}px;
  background: {preset['accent']};
  opacity: 0.05;
  border-radius: 50%;
  filter: blur(40px);
}}
body::after {{
  content: '';
  position: absolute;
  bottom: -{height * 0.2}px;
  left: -{width * 0.1}px;
  width: {width * 0.4}px;
  height: {width * 0.4}px;
  background: {preset['accent']};
  opacity: 0.04;
  border-radius: 50%;
  filter: blur(30px);
}}

/* 顶部装饰线 */
.top-line {{
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: {preset['accent']};
  opacity: 0.8;
}}

/* 主内容区 */
.content {{
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: {padding}px {padding * 1.5}px;
  z-index: 1;
  gap: {int(min(width, height) * 0.025)}px;
}}

/* 标题 */
.title {{
  font-size: {title_size}px;
  font-weight: 700;
  line-height: 1.3;
  letter-spacing: -0.02em;
  color: #fff;
  text-shadow: 0 2px 10px rgba(0,0,0,0.3);
  max-height: {title_size * 3}px;
  overflow: hidden;
}}

/* 描述 */
.description {{
  font-size: {desc_size}px;
  color: rgba(255,255,255,0.7);
  line-height: 1.6;
  max-height: {desc_size * desc_lines * 1.6}px;
  overflow: hidden;
}}

/* 标签区 */
.tags {{
  display: flex;
  gap: {int(min(width, height) * 0.012)}px;
  flex-wrap: wrap;
  margin-top: {int(min(width, height) * 0.01)}px;
}}

.tag {{
  background: {preset['tag_bg']};
  border: 1px solid {preset['tag_border']};
  border-radius: 4px;
  padding: {max(3, int(desc_size * 0.3))}px {max(8, int(desc_size * 0.6))}px;
  font-size: {max(11, int(desc_size * 0.8))}px;
  font-family: "SF Mono", "Fira Code", "Consolas", monospace;
  color: {preset['accent']};
  letter-spacing: 0.02em;
}}

/* 底部栏 */
.footer {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: {int(padding * 0.5)}px {padding * 1.5}px;
  border-top: 1px solid rgba(255,255,255,0.06);
  z-index: 1;
}}

.author {{
  font-size: {max(12, int(desc_size * 0.9))}px;
  color: rgba(255,255,255,0.4);
  display: flex;
  align-items: center;
  gap: 8px;
}}

.author::before {{
  content: '';
  display: inline-block;
  width: 20px;
  height: 20px;
  background: {preset['accent']};
  opacity: 0.7;
  border-radius: 50%;
}}

.platform-icon {{
  font-size: {max(12, int(desc_size * 0.85))}px;
  font-weight: 700;
  color: rgba(255,255,255,0.3);
  font-family: -apple-system, sans-serif;
}}

.logo {{
  font-size: {max(12, int(desc_size * 0.85))}px;
  color: rgba(255,255,255,0.25);
  font-weight: 300;
  letter-spacing: 0.1em;
}}

/* 小红书特别样式（更宽的留白，更文艺） */
{"#xiaohongshu .title { font-weight: 600; }" if platform in ("xiaohongshu", "xiaohongshu-sq") else ""}
</style>
</head>
<body id="{platform}">
  <div class="top-line"></div>
  <div class="content">
    <div class="title">{title}</div>
    <div class="description">{description}</div>
    <div class="tags">{tags_html}</div>
  </div>
  <div class="footer">
    <div class="author">{author}</div>
    {logo_html}
    <div class="logo">article-craft</div>
  </div>
</body>
</html>"""


# ─── 核心生成函数 ─────────────────────────────────────────────────────────────

def generate_card(title: str, description: str, tags: list,
                  author: str = "月影",
                  platform: str = "wechat-cover",
                  color_preset: str = "tech-blue",
                  output_dir: str = "") -> dict:
    """
    生成单张分享卡片。

    Returns:
        dict with keys: success, platform, output_path, file_size_kb, error
    """

    if platform not in PLATFORMS:
        return {"success": False, "platform": platform, "error": f"Unknown platform: {platform}"}

    width, height, title_size, desc_size, desc_lines = PLATFORMS[platform]
    preset = COLOR_PRESETS.get(color_preset, COLOR_PRESETS[DEFAULT_PRESET])

    # 生成 HTML
    html_content = make_card_html(
        title, description, tags, author,
        width, height, title_size, desc_size, desc_lines,
        preset, platform
    )

    # 写入临时 HTML
    tmp_fd, tmp_html = tempfile.mkstemp(suffix=".html", prefix="share-card-")
    with os.fdopen(tmp_fd, "w") as f:
        f.write(html_content)

    # 输出 PNG 路径
    if not output_dir:
        output_dir = tempfile.gettempdir()
    filename = f"card-{platform}-{hash(title) & 0xFFFFFF:06x}.png"
    output_path = os.path.join(output_dir, filename)

    # Playwright 截图
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_viewport_size({"width": width, "height": height})

            page.goto(f"file://{tmp_html}", wait_until="networkidle", timeout=10000)
            page.screenshot(path=output_path, type="png")
            browser.close()
        except PlaywrightError as e:
            return {"success": False, "platform": platform, "error": f"Playwright: {e}"}
        finally:
            try:
                os.unlink(tmp_html)
            except Exception:
                pass

    # 压缩
    file_size = os.path.getsize(output_path) / 1024
    if file_size > 300:
        try:
            img = Image.open(output_path).convert("RGB")
            img.save(output_path, "PNG", optimize=True)
        except Exception:
            pass

    file_size = os.path.getsize(output_path) / 1024

    return {
        "success": True,
        "platform": platform,
        "output_path": output_path,
        "file_size_kb": round(file_size, 1),
        "dimensions": f"{width}×{height}",
    }


def batch_generate(title: str, description: str, tags: list,
                   author: str = "月影",
                   platforms: list = None,
                   color_preset: str = "tech-blue",
                   output_dir: str = "") -> list:
    """
    批量生成多张分享卡片。

    Args:
        platforms: list of platform names (None = all platforms)
    """

    if platforms is None:
        platforms = list(PLATFORMS.keys())

    results = []
    for platform in platforms:
        print(f"  🎨 {platform}...", end=" ", flush=True)
        res = generate_card(title, description, tags, author, platform,
                            color_preset, output_dir)
        if res["success"]:
            print(f"✅ {res['dimensions']} ({res['file_size_kb']} KB)")
        else:
            print(f"❌ {res['error']}")
        results.append(res)

    return results


def upload_all(results: list) -> None:
    """上传所有卡片到 CDN"""
    import shutil

    picgo = shutil.which("picgo")
    if not picgo:
        print("  ⚠️  picgo not found, skipping upload")
        return

    import subprocess
    for res in results:
        if not res.get("success"):
            continue
        path = res.get("output_path", "")
        if not path:
            continue
        try:
            result = subprocess.run(
                ["picgo", "upload", path],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                output = result.stdout.strip()
                # 提取 URL
                for line in output.splitlines():
                    if line.startswith("http"):
                        print(f"  🌐 {res['platform']}: {line}")
                        res["cdn_url"] = line
                        break
        except Exception:
            pass


# ─── CLI 入口 ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Article-Craft Share Card Generator — 生成分享卡片图片"
    )
    parser.add_argument("--title", "-t", default="技术文章标题", help="文章标题")
    parser.add_argument("--description", "-d", default="文章摘要描述内容",
                        help="文章摘要")
    parser.add_argument("--tags", nargs="*", default=[], help="标签（最多 5 个）")
    parser.add_argument("--author", "-a", default="月影", help="作者名")
    parser.add_argument("--platforms", "-p", default="",
                        help=f"平台，逗号分隔。可选: {', '.join(PLATFORMS.keys())}")
    parser.add_argument("--color", "-c", default="tech-blue",
                        help=f"配色方案。可选: {', '.join(COLOR_PRESETS.keys())}")
    parser.add_argument("--output", "-o", default="", help="输出目录")
    parser.add_argument("--upload", action="store_true", help="上传到 CDN")

    # 从文件读取文章信息
    parser.add_argument("--from-file", "-f", default="", help="从 Markdown 文件读取 frontmatter")

    args = parser.parse_args()

    # 从文件读取
    if args.from_file:
        title, description, tags, author = parse_frontmatter(args.from_file)
        if title:
            args.title = title
        if description:
            args.description = description
        if tags:
            args.tags = tags
        if author:
            args.author = author

    # 解析平台列表
    platforms = None
    if args.platforms:
        platforms = [p.strip() for p in args.platforms.split(",")]

    print(f"\n📝 Title: {args.title}")
    print(f"📝 Description: {args.description}")
    print(f"🏷️  Tags: {', '.join(args.tags) or 'none'}")
    print(f"🎨 Color: {args.color}")
    print(f"📐 Platforms: {', '.join(platforms) if platforms else 'all'}")

    results = batch_generate(
        title=args.title,
        description=args.description,
        tags=args.tags,
        author=args.author,
        platforms=platforms,
        color_preset=args.color,
        output_dir=args.output,
    )

    # 汇总
    success = [r for r in results if r["success"]]
    print(f"\n{'='*60}")
    print(f"  ✅ Generated {len(success)}/{len(results)} cards")
    print("=" * 60)
    for r in success:
        print(f"  {r['platform']:20s}  {r['dimensions']}  {r['file_size_kb']:6.1f} KB  {r['output_path']}")

    if args.upload:
        print(f"\n  🌐 Uploading to CDN...")
        upload_all(results)
        for r in success:
            if r.get("cdn_url"):
                print(f"  {r['platform']:20s}  {r['cdn_url']}")


def parse_frontmatter(filepath: str) -> tuple:
    """从 Markdown 文件解析 YAML frontmatter"""
    try:
        with open(filepath) as f:
            content = f.read()
    except Exception:
        return "", "", [], ""

    if not content.startswith("---"):
        return "", "", [], ""

    end = content.find("\n---", 4)
    if end == -1:
        return "", "", [], ""

    fm = content[4:end].strip()
    lines = fm.splitlines()
    data = {}
    for line in lines:
        if ": " in line:
            key, val = line.split(": ", 1)
            data[key.strip()] = val.strip().strip('"\'')
        elif line.strip().startswith("-"):
            pass  # 简单处理

    title = data.get("title", "")
    description = data.get("description", "") or data.get("summary", "")
    tags_raw = data.get("tags", "")
    if isinstance(tags_raw, str):
        # 尝试解析 YAML 列表
        tags = [t.strip().strip('"\'') for t in tags_raw.strip("[]").split(",")]
    else:
        tags = tags_raw if isinstance(tags_raw, list) else []
    author = data.get("author", "月影")

    return title, description, tags, author


if __name__ == "__main__":
    main()
