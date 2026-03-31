#!/usr/bin/env python3
"""
Article-Craft Screenshot Tool

智能截图：验证 URL → 渲染页面 → 检测真实内容 → 截图 → 压缩 → 上传

使用 Playwright 进行渲染，支持：
- URL 可用性验证（HEAD 请求）
- 404/403/5xx 检测
- JS 渲染页面支持
- 等待网络空闲
- 空页面检测（避免截到 loading 状态）
- 智能元素选择器推荐
- 图片压缩
"""

import argparse
import json
import os
import re
import sys
import hashlib
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

# 延迟导入，方便快速失败时显示友好错误
try:
    import requests
except ImportError:
    print("❌ Missing dependency: requests")
    print("   Run: pip install requests")
    sys.exit(1)

try:
    from playwright.sync_api import sync_playwright, Error as PlaywrightError
except ImportError:
    print("❌ Missing dependency: playwright")
    print("   Run: pip install playwright && playwright install chromium")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print("❌ Missing dependency: Pillow")
    print("   Run: pip install Pillow")
    sys.exit(1)


# ─── 配置 ───────────────────────────────────────────────────────────────────

DEFAULT_VIEWPORT_WIDTH = 1280
DEFAULT_VIEWPORT_HEIGHT = 800
MAX_IMAGE_SIZE_KB = 500  # KB，超过此大小则压缩
COMPRESSION_QUALITY = 85  # JPEG 压缩质量
SCREENSHOT_TIMEOUT_MS = 30000  # 页面加载超时
NETWORK_IDLE_WAIT_MS = 3000  # 等待网络空闲时间
MIN_CONTENT_HEIGHT_PX = 100  # 最小内容高度，低于此值认为页面为空

# 可信的 404 页面特征（域名特有页面）
GITHUB_404_PATTERNS = [
    r"This is not the page you are looking for",
    r"404 — File not found",
    r"page not found",
]
TWITTER_404_PATTERNS = [
    r"This account doesn’t exist",
    r"doesn't exist",
    r"Sorry, page not found",
]


# ─── 工具函数 ────────────────────────────────────────────────────────────────

def sanitize_filename(url: str) -> str:
    """从 URL 生成安全的文件名"""
    parsed = urlparse(url)
    path = parsed.path.strip("/").replace("/", "-").replace("?", "-").replace("&", "-")
    if not path:
        path = parsed.netloc
    # 截断并加 hash 避免过长
    name = path[:60] if len(path) > 60 else path
    hash_suffix = hashlib.md5(url.encode()).hexdigest()[:6]
    return f"{name}-{hash_suffix}"


VERIFY_CACHE_FILE = os.path.join(os.path.expanduser("~"), ".cache", "article-craft", "verify-cache.json")
CACHE_TTL_SECONDS = 3600  # 缓存有效期 1 小时


def _load_verify_cache() -> dict:
    """加载 verify skill 的 URL 缓存"""
    if not os.path.exists(VERIFY_CACHE_FILE):
        return {}
    try:
        with open(VERIFY_CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def check_url_status(url: str, timeout: int = 10,
                     _from_cache: bool = True) -> dict:
    """
    用 HEAD 请求检查 URL 状态，跟踪重定向，返回诊断信息。

    优先读取 verify skill 缓存，避免重复请求。
    缓存路径: /tmp/article-craft-verify-cache.json
    缓存 TTL: 1 小时

    Returns:
        dict with keys: status_code, final_url, redirect_count, is_404, is_403,
                        is_5xx, is_valid, reason, from_cache
    """
    result = {
        "status_code": None,
        "final_url": url,
        "redirect_count": 0,
        "is_404": False,
        "is_403": False,
        "is_5xx": False,
        "is_valid": False,
        "reason": "",
        "redirect_chain": [],
        "from_cache": False,
    }

    # Step 1: 尝试从 verify 缓存读取
    if _from_cache:
        cache = _load_verify_cache()
        if url in cache:
            cached = cache[url]
            age = time.time() - cached.get("_checked_at", 0)
            if age < CACHE_TTL_SECONDS:
                result.update({k: v for k, v in cached.items() if k != "_checked_at"})
                result["from_cache"] = True
                result["reason"] = f"(verify cache, {int(age)}s ago) {result['reason']}"
                return result

    # Step 2: 执行 HEAD 请求
    try:
        response = requests.head(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
        )
        result["status_code"] = response.status_code
        result["final_url"] = response.url
        result["redirect_chain"] = [r.url for r in response.history]

        # 检测重定向
        if response.history:
            result["redirect_count"] = len(response.history)
            if response.url != url:
                result["reason"] = f"Redirected to: {response.url}"
        else:
            result["reason"] = "Direct access"

        # 状态码判断
        if response.status_code == 200:
            result["is_valid"] = True
        elif response.status_code == 404:
            result["is_404"] = True
            result["reason"] = "404 Not Found"
        elif response.status_code == 403:
            result["is_403"] = True
            result["reason"] = "403 Forbidden (may be blocked)"
        elif response.status_code >= 500:
            result["is_5xx"] = True
            result["reason"] = f"{response.status_code} Server Error"
        else:
            result["reason"] = f"HTTP {response.status_code}"

    except requests.exceptions.Timeout:
        result["reason"] = "Connection timeout"
    except requests.exceptions.ConnectionError as e:
        result["reason"] = f"Connection error: {type(e).__name__}"
    except requests.exceptions.RequestException as e:
        result["reason"] = f"Request error: {type(e).__name__}"
    except Exception as e:
        result["reason"] = f"Unexpected error: {e}"

    # 写入缓存（不包含 from_cache 标记）
    if result["status_code"] is not None:
        try:
            cache = _load_verify_cache()
            cache[url] = {k: v for k, v in result.items() if k != "from_cache"}
            cache[url]["_checked_at"] = time.time()
            with open(VERIFY_CACHE_FILE, "w") as f:
                json.dump(cache, f)
        except Exception:
            pass  # 缓存写入失败不影响主流程

    return result


def is_404_content(page_text: str, url: str) -> bool:
    """检测页面文本中是否包含 404 特征"""
    url_lower = url.lower()

    if "github.com" in url_lower:
        for pattern in GITHUB_404_PATTERNS:
            if re.search(pattern, page_text, re.IGNORECASE):
                return True

    if "twitter.com" in url_lower or "x.com" in url_lower:
        for pattern in TWITTER_404_PATTERNS:
            if re.search(pattern, page_text, re.IGNORECASE):
                return True

    # 通用 404 特征
    generic_404 = [
        r"404\s*[:\-]?\s*Not Found",
        r"Page\s+Not\s+Found",
        r"The\s+page\s+(you\s+)?(were\s+)?looking\s+for",
        r"404\s+—?\s*$",
    ]
    for pattern in generic_404:
        if re.search(pattern, page_text, re.IGNORECASE):
            return True

    return False


def suggest_selector(url: str, page_title: str = "", content_type: str = "") -> str:
    """
    根据 URL 和页面特征推荐最佳截图元素选择器。
    只返回可信的选择器。
    """
    url_lower = url.lower()

    # GitHub
    if "github.com" in url_lower:
        parsed = urlparse(url)
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]

        if len(path_parts) == 2:  # user/repo
            return "#repo-content-pjax-container" if not content_type else ""
        elif len(path_parts) >= 3 and path_parts[2] in ("issues", "pulls"):
            return ".Timeline-Message" if content_type == "comments" else "#repo-content-pjax-container"
        elif len(path_parts) >= 3 and path_parts[2] == "readme":
            return ".markdown-body" if not content_type else ""
        return ""

    # Twitter/X
    if "twitter.com" in url_lower or "x.com" in url_lower:
        if "status" in url_lower:
            return '[data-testid="tweet"]' if not content_type else ""
        return ""

    # Stack Overflow
    if "stackoverflow.com" in url_lower:
        return "#question" if not content_type else ""

    # npm
    if "npmjs.com" in url_lower:
        return ".npm__container" if not content_type else ""

    # 文档类
    doc_patterns = ["docs.", "documentation", "/docs/", "readme", "wiki"]
    for pattern in doc_patterns:
        if pattern in url_lower:
            return "article, main, .content, .documentation, .docs-content"

    # 默认：空字符串表示截全页
    return ""


def compress_image(image_path: str, max_size_kb: int = MAX_IMAGE_SIZE_KB) -> bool:
    """
    压缩图片到指定大小以内。使用 Pillow。

    Returns:
        True if compressed, False if already small enough
    """
    try:
        img = Image.open(image_path)
        img = img.convert("RGB")  # 确保是 RGB

        file_size = os.path.getsize(image_path) / 1024  # KB

        if file_size <= max_size_kb:
            return False

        # 计算缩放比例
        scale = (max_size_kb / file_size) ** 0.5
        if scale < 1.0:
            new_width = int(img.width * scale)
            new_height = int(img.height * scale)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # 保存为 PNG 或 JPEG
        output_path = image_path
        if not image_path.endswith(".png"):
            output_path = image_path.rsplit(".", 1)[0] + ".png"

        img.save(output_path, "PNG", optimize=True)
        return True
    except Exception as e:
        print(f"   ⚠️  Compression failed: {e}")
        return False


def crop_whitespace(image_path: str) -> bool:
    """
    裁剪图片底部大量空白区域，减少无效空间。
    """
    try:
        img = Image.open(image_path)
        img = img.convert("RGB")

        # 检查底部空白
        bg_color = img.getpixel((img.width // 2, img.height - 10))
        threshold = 20  # 颜色差异阈值

        crop_line = img.height
        for y in range(img.height - 1, img.height // 2, -5):
            row_colors = [img.getpixel((x, y)) for x in range(0, img.width, max(1, img.width // 20))]
            avg_diff = sum(
                max(abs(c[0] - bg_color[0]), abs(c[1] - bg_color[1]), abs(c[2] - bg_color[2]))
                for c in row_colors
            ) / len(row_colors)
            if avg_diff < threshold:
                crop_line = y
            else:
                break

        # 只有空白超过 20% 才裁剪
        if crop_line < img.height * 0.8:
            img = img.crop((0, 0, img.width, crop_line + 10))
            img.save(image_path, "PNG", optimize=True)
            return True
        return False
    except Exception:
        return False


# ─── 核心截图函数 ─────────────────────────────────────────────────────────────

def capture_screenshot(url: str, output_path: str = "", selector: str = "",
                       wait: int = 0, width: int = DEFAULT_VIEWPORT_WIDTH,
                       height: int = DEFAULT_VIEWPORT_HEIGHT,
                       article_keywords: list = None) -> dict:
    """
    完整的智能截图流程。

    Args:
        url: 要截图的 URL
        output_path: 输出文件路径（为空时自动生成到 /tmp）
        selector: CSS 选择器（只截取该元素）
        wait: 额外等待秒数
        width: 视口宽度
        height: 视口高度
        article_keywords: 文章关键词（用于判断截图相关性）

    Returns:
        dict with keys: success, url, output_path, file_size_kb, error, warnings
    """
    result = {
        "success": False,
        "url": url,
        "output_path": "",
        "file_size_kb": 0,
        "error": "",
        "warnings": [],
        "selector_used": selector or "full-page",
        "page_title": "",
        "content_detected": False,
        "is_404_page": False,
    }

    article_keywords = article_keywords or []

    # Step 1: URL 状态预检（HEAD 请求）
    print(f"  🔍 Checking URL: {url}")
    status = check_url_status(url)
    cache_tag = " (verify cache hit)" if status.get("from_cache") else ""
    print(f"     Status: {status['status_code'] or 'N/A'} — {status['reason']}{cache_tag}")

    if status["redirect_count"] > 0:
        print(f"     ↳ Redirect chain: {' → '.join(u.split('?')[0] for u in status['redirect_chain'])} → {status['final_url'].split('?')[0]}")

    if status.get("is_404"):
        result["error"] = f"404 Not Found — {url}"
        result["warnings"].append(f"URL 返回 404，不截图")
        return result

    if status.get("is_5xx"):
        result["error"] = f"Server Error {status.get('status_code')} — {url}"
        result["warnings"].append(f"服务器错误，不截图")
        return result

    if not status.get("is_valid") and status["status_code"] is None:
        result["error"] = f"无法访问: {status['reason']}"
        result["warnings"].append(f"连接失败，不截图")
        return result

    # 生成输出路径
    if not output_path:
        filename = sanitize_filename(url) + ".png"
        output_path = os.path.join(tempfile.gettempdir(), filename)

    # Step 2: Playwright 渲染截图
    print(f"  🌐 Rendering with Playwright...")

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": width, "height": height},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                locale="zh-CN",
            )
            page = context.new_page()

            # 拦截无效资源加速加载
            def block_unnecessary(route):
                req = route.request
                resource_type = req.resource_type
                # 仍保留图片和主要内容，只拦截字体广告等
                if resource_type in ("font", "websocket"):
                    route.abort()
                else:
                    route.continue_()

            context.route("**/*", block_unnecessary)

            # 导航
            response = page.goto(url, timeout=SCREENSHOT_TIMEOUT_MS, wait_until="domcontentloaded")
            actual_status = response.status if response else 0

            if actual_status == 404:
                result["is_404_page"] = True
                result["error"] = f"404 after render — {url}"
                result["warnings"].append(f"页面渲染后返回 404")
                browser.close()
                return result

            # 等待网络空闲
            try:
                page.wait_for_load_state("networkidle", timeout=NETWORK_IDLE_WAIT_MS + wait * 1000)
            except Exception:
                result["warnings"].append("Network idle timeout, continuing anyway")

            # 额外等待（用于 SPA / JS 渲染）
            if wait > 0:
                page.wait_for_timeout(wait * 1000)

            # 获取页面标题
            result["page_title"] = page.title()

            # Step 3: 检测真实内容
            print(f"  📄 Page title: {result['page_title']}")

            # 检查 body 高度（是否有真实内容）
            body_height = page.evaluate("""() => {
                const body = document.body;
                return body ? Math.max(body.scrollHeight, body.offsetHeight) : 0;
            }""")

            if body_height < MIN_CONTENT_HEIGHT_PX:
                result["warnings"].append(f"页面内容过少（{body_height}px），可能是 loading 状态")
                result["content_detected"] = False
            else:
                result["content_detected"] = True

            # 检查 404 文本特征
            page_text = page.inner_text("body")[:500]
            if is_404_content(page_text, url):
                result["is_404_page"] = True
                result["warnings"].append("页面包含 404 特征文本")

            # Step 4: 智能选择器（未指定时推荐）
            if not selector:
                suggested = suggest_selector(url, result["page_title"])
                if suggested:
                    # 验证选择器存在
                    try:
                        el = page.query_selector(suggested.split(",")[0].strip())
                        if el:
                            selector = suggested.split(",")[0].strip()
                            print(f"  🎯 Auto selector: {selector}")
                    except Exception:
                        pass

            # Step 5: 截图
            if selector:
                # 只截取指定元素
                el = page.query_selector(selector)
                if el:
                    el.screenshot(path=output_path, timeout=15000)
                    result["selector_used"] = selector
                    print(f"  📸 Element screenshot saved: {output_path}")
                else:
                    result["warnings"].append(f"选择器 '{selector}' 未找到，回退到全页截图")
                    page.screenshot(path=output_path, full_page=True, timeout=15000)
                    result["selector_used"] = "full-page (fallback)"
                    print(f"  📸 Full page screenshot saved: {output_path}")
            else:
                # 全页截图
                page.screenshot(path=output_path, full_page=True, timeout=15000)
                print(f"  📸 Full page screenshot saved: {output_path}")

            browser.close()

        except PlaywrightError as e:
            result["error"] = f"Playwright error: {e}"
            return result
        except Exception as e:
            result["error"] = f"Unexpected error: {e}"
            return result

    # Step 6: 验证截图
    if not os.path.exists(output_path):
        result["error"] = "Screenshot file not created"
        return result

    result["file_size_kb"] = os.path.getsize(output_path) / 1024
    print(f"     File size: {result['file_size_kb']:.1f} KB")

    # Step 7: 裁剪空白 + 压缩
    print(f"  ✂️  Optimizing image...")
    was_compressed = compress_image(output_path)
    crop_whitespace(output_path)

    result["file_size_kb"] = os.path.getsize(output_path) / 1024
    print(f"     Final size: {result['file_size_kb']:.1f} KB")

    if was_compressed:
        result["warnings"].append(f"图片已压缩（原始可能更大）")

    result["success"] = True
    result["output_path"] = output_path
    return result


def batch_capture(entries: list, output_dir: str = "", article_keywords: list = None) -> list:
    """
    批量截图。

    Args:
        entries: list of dicts with keys: url, selector (optional), wait (optional)
        output_dir: 输出目录（默认为 /tmp）
        article_keywords: 文章关键词

    Returns:
        list of result dicts
    """
    if not output_dir:
        output_dir = tempfile.gettempdir()

    results = []
    for i, entry in enumerate(entries):
        url = entry.get("url", "")
        if not url:
            continue

        print(f"\n{'='*60}")
        print(f"  [{i+1}/{len(entries)}] Processing: {url}")
        print("=" * 60)

        output_path = os.path.join(output_dir, sanitize_filename(url) + ".png")

        res = capture_screenshot(
            url=url,
            output_path=output_path,
            selector=entry.get("selector", ""),
            wait=entry.get("wait", 0),
            width=entry.get("width", DEFAULT_VIEWPORT_WIDTH),
            article_keywords=article_keywords,
        )
        results.append(res)

    return results


def upload_to_cdn(image_path: str) -> str:
    """
    上传截图到 CDN（通过 PicGo）。
    失败时返回本地路径。
    """
    import shutil
    picgo = shutil.which("picgo")
    if not picgo:
        return image_path

    try:
        import subprocess
        result = subprocess.run(
            ["picgo", "upload", image_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            # PicGo 输出通常是 JSON
            output = result.stdout.strip()
            try:
                data = json.loads(output)
                if isinstance(data, list) and len(data) > 0:
                    return data[0].get("url", image_path)
                elif isinstance(data, dict):
                    return data.get("url", image_path)
            except json.JSONDecodeError:
                # 直接返回输出作为 URL
                return output if output.startswith("http") else image_path
        return image_path
    except Exception:
        return image_path


# ─── CLI 入口 ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Article-Craft Screenshot Tool — 智能截图，验证后渲染"
    )
    sub = parser.add_subparsers(dest="command", help="子命令")

    # screenshot 子命令
    sc = sub.add_parser("screenshot", help="截取单个 URL")
    sc.add_argument("url", help="要截图的 URL")
    sc.add_argument("-o", "--output", default="", help="输出文件路径")
    sc.add_argument("-s", "--selector", default="", help="CSS 选择器（只截取该元素）")
    sc.add_argument("-w", "--wait", type=int, default=0, help="额外等待秒数")
    sc.add_argument("--width", type=int, default=DEFAULT_VIEWPORT_WIDTH, help="视口宽度")
    sc.add_argument("--no-upload", action="store_true", help="跳过 CDN 上传")
    sc.add_argument("--keywords", nargs="*", default=[], help="文章关键词（用于相关性判断）")

    # batch 子命令
    ba = sub.add_parser("batch", help="批量截图（从 JSON 文件读取）")
    ba.add_argument("file", help="JSON 文件，每行一个 URL 或结构化对象")
    ba.add_argument("-o", "--output-dir", default="", help="输出目录")
    ba.add_argument("--no-upload", action="store_true", help="跳过 CDN 上传")
    ba.add_argument("--keywords", nargs="*", default=[], help="文章关键词")

    # check 子命令
    ck = sub.add_parser("check", help="只验证 URL 可用性，不截图")
    ck.add_argument("url", help="要检查的 URL")
    ck.add_argument("--timeout", type=int, default=10, help="超时秒数")

    args = parser.parse_args()

    if args.command == "check":
        status = check_url_status(args.url, timeout=args.timeout)
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return

    if args.command == "screenshot":
        res = capture_screenshot(
            url=args.url,
            output_path=args.output,
            selector=args.selector,
            wait=args.wait,
            width=args.width,
            article_keywords=args.keywords,
        )

        print(json.dumps(res, indent=2, ensure_ascii=False))

        if res["success"] and not args.no_upload:
            cdn_url = upload_to_cdn(res["output_path"])
            if cdn_url != res["output_path"]:
                print(f"\n  🌐 CDN URL: {cdn_url}")
        return

    if args.command == "batch":
        # 支持 JSONL 或 JSON 数组
        entries = []
        with open(args.file) as f:
            content = f.read().strip()
            if content.startswith("["):
                entries = json.loads(content)
            else:
                for line in content.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        entries.append({"url": line})

        results = batch_capture(entries, args.output_dir, args.keywords)

        # 汇总报告
        total = len(results)
        success = sum(1 for r in results if r["success"])
        skipped = sum(1 for r in results if not r["success"] and "404" in r.get("error", ""))
        failed = total - success - skipped

        print(f"\n{'='*60}")
        print(f"  📊 Batch Summary: {success}/{total} succeeded, {skipped} skipped (404), {failed} failed")
        print("=" * 60)

        for r in results:
            status_icon = "✅" if r["success"] else "❌"
            print(f"  {status_icon} {r['url']}")
            if r.get("warnings"):
                for w in r["warnings"]:
                    print(f"     ⚠️  {w}")
            if r.get("error"):
                print(f"     {r['error']}")
            if r["success"]:
                print(f"     → {r['output_path']} ({r['file_size_kb']:.1f} KB)")

        if not args.no_upload:
            print(f"\n  🌐 Uploading to CDN...")
            for r in results:
                if r["success"]:
                    cdn_url = upload_to_cdn(r["output_path"])
                    if cdn_url != r["output_path"]:
                        print(f"     {cdn_url}")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
