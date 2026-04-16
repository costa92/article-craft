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


# ─── Rehost：下载远端 CDN 图片（带正确 Referer），重新上传到自己图床 ───────────
#
# 缘起：微信 mmbiz.qpic.cn 等 CDN 对非同源 Referer 会**静默**返回 ~2KB 占位图
# （HTTP 200，没法用状态码判断坏掉）。当 HARVEST 出来的文章发布到非公众号
# 平台（Obsidian / 博客 / 知乎），读者浏览器带的 Referer 不匹配 → 图片糊成
# 灰占位。rehost 的工作：下载原图（带正确 Referer）→ 上传我方 CDN → 返回新
# URL，由 HARVEST 占位符 expander 替换进 article.md。
#
# 默认 mode=auto：只对白名单 CDN 做 rehost，其他 URL 保持现状。

REHOST_CDN_WHITELIST: dict[str, str] = {
    # (url-substring → canonical Referer)
    "mmbiz.qpic.cn":   "https://mp.weixin.qq.com/",
    "mmbiz.qlogo.cn":  "https://mp.weixin.qq.com/",
    "sinaimg.cn":      "https://weibo.com/",      # covers ww1/ww2/tva*/wx1-4.sinaimg.cn
    "zhimg.com":       "https://www.zhihu.com/",  # covers pic1-4.zhimg.com
}

REHOST_MIN_BYTES = 4096   # defensive stub-detection bar; real source images are 20KB+


def _rehost_match_whitelist(url: str) -> tuple[bool, str]:
    for cdn, referer in REHOST_CDN_WHITELIST.items():
        if cdn in url:
            return True, referer
    return False, ""


def _infer_image_extension(url: str, content_type: str = "") -> tuple[str, bool]:
    """Return (extension-with-dot, is_animated)."""
    m = re.search(r"[?&]wx_fmt=(gif|png|jpeg|jpg|webp)", url)
    if m:
        fmt = m.group(1).lower()
        if fmt == "gif":
            return ".gif", True
        if fmt in ("jpeg", "jpg"):
            return ".jpg", False
        return f".{fmt}", False
    path = url.split("?", 1)[0].split("#", 1)[0].lower()
    for ext in (".gif", ".png", ".webp", ".jpg", ".jpeg"):
        if path.endswith(ext):
            return (".jpg" if ext == ".jpeg" else ext), ext == ".gif"
    ct = content_type.lower()
    if "gif" in ct: return ".gif", True
    if "png" in ct: return ".png", False
    if "webp" in ct: return ".webp", False
    return ".jpg", False


def rehost_image(url: str, mode: str = "auto") -> dict:
    """
    Download a remote image with the correct Referer and re-upload via our CDN.

    Args:
        url: remote image URL
        mode: 'auto' (rehost only if URL matches CDN whitelist, DEFAULT),
              'always' (rehost every URL),
              'never' (short-circuit, return unchanged).

    Returns:
        dict with keys: ok, rehosted, original_url, final_url, reason, is_animated.
        On any failure (network, upload, suspected hotlink stub), ok=False,
        final_url=original_url (graceful degradation — caller can keep remote URL).
    """
    result = {
        "ok": True, "rehosted": False,
        "original_url": url, "final_url": url,
        "reason": "", "is_animated": False,
    }

    if mode == "never":
        result["reason"] = "mode=never"
        return result

    matched, referer = _rehost_match_whitelist(url)
    if mode == "auto" and not matched:
        result["reason"] = "url not in rehost whitelist"
        return result

    # At this point: mode=always OR (mode=auto AND matched)
    ext, is_animated = _infer_image_extension(url)
    result["is_animated"] = is_animated

    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
    if referer:
        headers["Referer"] = referer

    try:
        r = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
    except requests.exceptions.RequestException as e:
        result["ok"] = False
        result["reason"] = f"download error: {type(e).__name__}: {e}"
        return result

    if r.status_code != 200:
        result["ok"] = False
        result["reason"] = f"HTTP {r.status_code}"
        return result

    content = r.content
    # Silent-hotlink-stub guard: mmbiz returns ~2KB placeholder w/ HTTP 200 on
    # wrong Referer. A real Style H source image is basically never < 2KB.
    if len(content) < REHOST_MIN_BYTES:
        result["ok"] = False
        result["reason"] = f"suspected hotlink stub ({len(content)}B < {REHOST_MIN_BYTES}B)"
        return result

    # Refine extension from Content-Type if we couldn't decide from URL
    ct = r.headers.get("content-type", "")
    if not is_animated and "gif" in ct.lower():
        ext, is_animated = ".gif", True
        result["is_animated"] = True

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(prefix="rehost-", suffix=ext, delete=False) as f:
            f.write(content)
            tmp_path = f.name
    except OSError as e:
        result["ok"] = False
        result["reason"] = f"tempfile error: {e}"
        return result

    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from generate_and_upload_images import upload_image  # type: ignore
        cdn_url = upload_image(tmp_path)
    except Exception as e:
        result["ok"] = False
        result["reason"] = f"upload error: {type(e).__name__}: {e}"
        return result
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    result["rehosted"] = True
    result["final_url"] = cdn_url
    result["reason"] = f"rehosted (referer={referer or 'none'}, ext={ext}, {len(content)}B)"
    return result


# ─── Expand-harvest：把 article.md 里的 <!-- HARVEST: --> 占位符就地替换为图片 ──
#
# 替代 screenshot/SKILL.md 里的 pseudocode：在一个原子、可测试、带完整日志的
# 子命令里做查表 + rehost + 替换。SKILL.md 只需要 subprocess.run 一下。

HARVEST_PLACEHOLDER_RE = re.compile(
    r"<!--\s*HARVEST:\s*(\S+)(.*?)-->",
    re.DOTALL,
)


def _parse_harvest_opts(opts_str: str) -> dict:
    """Parse `idx=N alt=\"…\" caption=\"…\" rehost=auto|always|never --cover`."""
    out: dict = {}
    if re.search(r"(?:^|\s)(?:--cover|cover\s*=\s*(?:1|true|yes))(?=\s|$)", opts_str, re.IGNORECASE):
        out["cover"] = True
    m = re.search(r"\bidx\s*=\s*(\d+)", opts_str)
    if m:
        out["idx"] = int(m.group(1))
    m = re.search(r'\balt\s*=\s*"([^"]+)"', opts_str)
    if m:
        out["alt"] = m.group(1)
    m = re.search(r'\bcaption\s*=\s*"([^"]+)"', opts_str)
    if m:
        out["caption"] = m.group(1)
    m = re.search(r"\brehost\s*=\s*(auto|always|never)\b", opts_str)
    if m:
        out["rehost"] = m.group(1)
    return out


def _pick_harvest_image(source: dict, opts: dict) -> dict | None:
    """Return `{url, alt?}` or None. Cover beats idx beats alt."""
    if opts.get("cover"):
        cover_url = source.get("cover")
        return {"url": cover_url, "alt": "cover"} if cover_url else None
    imgs = source.get("images") or []
    if "idx" in opts:
        i = opts["idx"]
        return imgs[i] if 0 <= i < len(imgs) else None
    if opts.get("alt"):
        needle = opts["alt"].lower()
        for img in imgs:
            if needle in (img.get("alt") or "").lower():
                return img
    return None


def expand_harvest(article_path: str, evidence_path: str | None = None,
                   dry_run: bool = False, strict: bool = False) -> dict:
    """
    Resolve every `<!-- HARVEST: url ... -->` in article.md against `_evidence.json`,
    optionally rehost the image URL, and rewrite the article in place.

    Args:
        article_path: absolute path to article.md
        evidence_path: optional absolute path to _evidence.json (default: article dir)
        dry_run: if True, do not call rehost and do not write article.md
                 (useful for preflight / CI validation / preview)
        strict: if True, any `failed > 0` causes exit code 1 and the article.md
                is NOT written (even when not dry_run)

    Returns a summary dict: counts + per-placeholder trace.
    """
    article = Path(article_path).resolve()
    if not article.exists():
        return {"ok": False, "error": f"article not found: {article}"}

    ev_path = Path(evidence_path) if evidence_path else article.parent / "_evidence.json"
    if not ev_path.exists():
        return {"ok": False, "error": f"_evidence.json not found: {ev_path}"}

    evidence = json.loads(ev_path.read_text(encoding="utf-8"))
    sources_by_url: dict[str, dict] = {
        s.get("url"): s for s in (evidence.get("sources") or []) if s.get("url")
    }

    body = article.read_text(encoding="utf-8")
    summary = {
        "ok": True,
        "article": str(article),
        "evidence": str(ev_path),
        "dry_run": dry_run,
        "strict": strict,
        "expanded": 0,
        "rehosted": 0,
        "failed": 0,
        "total": 0,
        "would_write": False,
        "trace": [],
    }

    def replace_one(match: re.Match) -> str:
        summary["total"] += 1
        src_url = match.group(1).strip()
        opts_str = match.group(2) or ""
        opts = _parse_harvest_opts(opts_str)
        trace: dict = {"src_url": src_url, "opts": opts, "status": "", "final_url": ""}

        source = sources_by_url.get(src_url)
        if source is None:
            trace["status"] = "source_not_in_evidence"
            summary["failed"] += 1
            summary["trace"].append(trace)
            return match.group(0)  # keep placeholder intact

        img = _pick_harvest_image(source, opts)
        if img is None or not img.get("url"):
            trace["status"] = "no_matching_image"
            summary["failed"] += 1
            summary["trace"].append(trace)
            return match.group(0)

        final_url = img["url"]
        rehost_mode = opts.get("rehost", "auto")
        if dry_run:
            # Don't hit the network or mutate the upload CDN — preview only.
            # Report what would happen based on whitelist match.
            matched, _ = _rehost_match_whitelist(img["url"])
            if rehost_mode == "never":
                trace["rehost"] = "skipped_mode_never"
            elif rehost_mode == "auto" and not matched:
                trace["rehost"] = "skipped_not_whitelisted"
            else:
                trace["rehost"] = "would_rehost"
                # count as would-be rehosted for preview totals
                summary["rehosted"] += 1
        elif rehost_mode != "never":
            rh = rehost_image(img["url"], mode=rehost_mode)
            if rh.get("ok") and rh.get("rehosted"):
                final_url = rh["final_url"]
                summary["rehosted"] += 1
                trace["rehost"] = "yes"
                trace["rehost_reason"] = rh.get("reason", "")
            elif not rh.get("ok"):
                trace["rehost"] = "failed_degraded"
                trace["rehost_reason"] = rh.get("reason", "")

        caption = opts.get("caption") or img.get("alt") or ""
        trace["status"] = "expanded"
        trace["final_url"] = final_url
        trace["caption"] = caption
        summary["expanded"] += 1
        summary["trace"].append(trace)
        return f"![{caption}]({final_url})"

    new_body = HARVEST_PLACEHOLDER_RE.sub(replace_one, body)
    summary["would_write"] = new_body != body

    # Strict mode + failures: do NOT write, flip ok=False so CLI exits 1
    if strict and summary["failed"] > 0:
        summary["ok"] = False
        summary["error"] = f"strict mode: {summary['failed']} placeholder(s) failed, article not modified"
        return summary

    # Dry run: never write
    if dry_run:
        return summary

    if summary["would_write"]:
        article.write_text(new_body, encoding="utf-8")
    return summary


# ─── Harvest-menu：根据 _evidence.json 生成一张 HARVEST 可选图清单 ──────────
#
# 目的：write skill 决定写 <!-- HARVEST: url idx=N --> 时，不能靠记忆猜 N。
# 本菜单一次性列出每个源可选的 cover + 每张图的 (数组位置, 尺寸, 格式, alt 片段)，
# 以及付费墙/本地图的 cite-only 清单。write skill 必须把菜单读进上下文后再落占位符。

MENU_ALT_TRUNC = 50


def _truncate(s: str, n: int) -> str:
    s = (s or "").replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _infer_format_from_url(url: str) -> str:
    m = re.search(r"[?&]wx_fmt=(gif|png|jpe?g|webp)", url, re.IGNORECASE)
    if m:
        return m.group(1).lower().replace("jpeg", "jpg")
    path = url.split("?", 1)[0].split("#", 1)[0].lower()
    for ext in ("gif", "png", "webp", "jpg", "jpeg"):
        if path.endswith(f".{ext}"):
            return ext.replace("jpeg", "jpg")
    return "?"


def _recommend_picks(source: dict) -> dict:
    """
    Classify a source's images into buckets a writer actually thinks about:

      cover:  one best cover candidate (prefers source.cover; else biggest
              wide non-GIF)
      main:   up to 5 main-visual candidates (non-GIF, wide enough to read,
              ranked by area descending, cover excluded)
      demo:   every GIF (animations, ranked by area)
      avoid:  very small / skinny images likely to be icons, QR codes,
              decorative flourishes

    Returns sorted idx lists so the writer can just pick from the top.
    """
    has_cover = bool(source.get("cover"))
    imgs = source.get("images") or []

    classified = []
    for pos, img in enumerate(imgs):
        w = int(img.get("width") or 0)
        h = int(img.get("height") or 0)
        fmt = _infer_format_from_url(img.get("url", ""))
        area = w * h
        aspect = (w / h) if h else 0
        classified.append({
            "idx": pos, "w": w, "h": h, "fmt": fmt,
            "area": area, "aspect": aspect,
        })

    is_gif = lambda x: x["fmt"] == "gif"
    is_tiny = lambda x: x["w"] < 400 or x["h"] < 200
    is_wide_enough = lambda x: x["w"] >= 400 and x["h"] >= 200

    cover_idx: int | None = None
    if not has_cover:
        wide_non_gif = sorted(
            [c for c in classified if not is_gif(c) and c["aspect"] >= 1.3 and not is_tiny(c)],
            key=lambda c: c["area"], reverse=True,
        )
        if wide_non_gif:
            cover_idx = wide_non_gif[0]["idx"]

    main_pool = sorted(
        [c for c in classified
         if not is_gif(c) and is_wide_enough(c) and c["idx"] != cover_idx],
        key=lambda c: c["area"], reverse=True,
    )
    main_picks = [c["idx"] for c in main_pool[:5]]

    demo_picks = [c["idx"] for c in sorted(
        [c for c in classified if is_gif(c)],
        key=lambda c: c["area"], reverse=True,
    )]

    avoid_picks = sorted([c["idx"] for c in classified if is_tiny(c)])

    return {
        "use_cover_flag": has_cover,
        "cover_idx": cover_idx,
        "main": main_picks,
        "demo": demo_picks,
        "avoid": avoid_picks,
    }


def harvest_menu(evidence_path: str, as_json: bool = False) -> str | dict:
    """
    Emit a writer-facing menu of HARVEST options from _evidence.json.

    Output format (markdown): one section per source, listing cover availability
    + a compact table of images with array-position indices (what HARVEST idx=N
    actually selects). Gated and manual entries get cite-only lists at the end.
    """
    ev_path = Path(evidence_path)
    if not ev_path.exists():
        msg = f"_evidence.json not found: {ev_path}"
        return {"ok": False, "error": msg} if as_json else f"❌ {msg}\n"

    data = json.loads(ev_path.read_text(encoding="utf-8"))
    sources = data.get("sources") or []
    manual = data.get("manual") or []
    summary = data.get("summary") or {}

    if as_json:
        return {
            "ok": True,
            "evidence": str(ev_path),
            "sources": [
                {
                    "url": s.get("url"),
                    "tier": s.get("tier", ""),
                    "title": s.get("title", ""),
                    "method": s.get("method", ""),
                    "cover": bool(s.get("cover")),
                    "images": [
                        {
                            "position": i,
                            "format": _infer_format_from_url(img.get("url", "")),
                            "width": img.get("width", 0),
                            "height": img.get("height", 0),
                            "alt": _truncate(img.get("alt", ""), MENU_ALT_TRUNC),
                        }
                        for i, img in enumerate(s.get("images") or [])
                    ],
                    "recommend": _recommend_picks(s),
                }
                for s in sources
            ],
            "manual": manual,
            "summary": summary,
        }

    out: list[str] = []
    out.append("# HARVEST Menu\n")
    out.append(
        f"**Pick from this menu only.** idx=N refers to the array position in the "
        f"table below (exactly what `expand-harvest --dry-run --strict` will validate).\n"
    )

    public_sources = [s for s in sources if s.get("method") not in ("gated", "failed")]
    gated_sources = [s for s in sources if s.get("method") == "gated"]
    failed_sources = [s for s in sources if s.get("method") == "failed"]

    for i, src in enumerate(public_sources, 1):
        url = src.get("url", "")
        tier = src.get("tier", "?")
        title = src.get("title", "") or "(untitled)"
        method = src.get("method", "?")
        has_cover = bool(src.get("cover"))
        imgs = src.get("images") or []

        out.append(f"\n## Source {i}: {url}\n")
        out.append(f"- tier: **{tier}**, method: `{method}`, title: {title}")
        if has_cover:
            out.append(f'- cover: available ✅  `<!-- HARVEST: {url} --cover caption="..." -->`')
        else:
            out.append("- cover: not available ❌")
        out.append(f"- images: **{len(imgs)}** filtered")

        if imgs:
            out.append("")
            out.append("| idx | dim | fmt | alt / context |")
            out.append("|----:|:----|:----|:---------------|")
            for pos, img in enumerate(imgs):
                w = img.get("width") or 0
                h = img.get("height") or 0
                dim = f"{w}×{h}" if (w or h) else "—"
                fmt = _infer_format_from_url(img.get("url", ""))
                alt = _truncate(img.get("alt", "") or img.get("context", ""), MENU_ALT_TRUNC)
                out.append(f"| {pos} | {dim} | {fmt} | {alt or '(empty)'} |")
            out.append("")
            out.append(f'Example: `<!-- HARVEST: {url} idx=0 caption="your caption" -->`')

            # Recommended picks block — writer-directed, not exhaustive.
            picks = _recommend_picks(src)
            out.append("")
            out.append("**📌 Recommended picks** (guidance — not exhaustive, override freely):")
            if picks["use_cover_flag"]:
                out.append(f'- **Cover**: use `--cover` (source has og:image) → `<!-- HARVEST: {url} --cover caption="..." -->`')
            elif picks["cover_idx"] is not None:
                out.append(f'- **Cover**: `idx={picks["cover_idx"]}` (biggest wide non-GIF)')
            else:
                out.append("- **Cover**: no strong candidate; consider IMAGE-generated cover instead of HARVEST")
            if picks["main"]:
                out.append(f'- **Main visuals** (non-GIF, ranked by area): {", ".join(f"idx={i}" for i in picks["main"])}')
            else:
                out.append("- **Main visuals**: none wide enough (≥400×200 non-GIF)")
            if picks["demo"]:
                out.append(f'- **Animation demos** (GIFs): {", ".join(f"idx={i}" for i in picks["demo"])}')
            if picks["avoid"]:
                out.append(f'- **Likely avoid** (icons / tiny, <400×200): {", ".join(f"idx={i}" for i in picks["avoid"])}')

            # Drop-in placeholders: copy-paste ready, writer only fills captions.
            out.append("")
            out.append("**🧱 Drop-in HARVEST placeholders** — copy any into article.md, replace `...` with your caption:")
            out.append("")
            out.append("```markdown")
            if picks["use_cover_flag"]:
                out.append(f'<!-- HARVEST: {url} --cover caption="..." -->')
            elif picks["cover_idx"] is not None:
                out.append(f'<!-- HARVEST: {url} idx={picks["cover_idx"]} caption="..." -->   # cover candidate')
            for i in picks["main"]:
                out.append(f'<!-- HARVEST: {url} idx={i} caption="..." -->')
            for i in picks["demo"]:
                out.append(f'<!-- HARVEST: {url} idx={i} caption="..." -->   # GIF / 动图')
            out.append("```")

    if gated_sources:
        out.append("\n## Paywall / login-gated (cite-only, NO HARVEST)\n")
        out.append("Use in-text citation phrasing, do not emit HARVEST placeholders:")
        out.append("")
        for src in gated_sources:
            desc = src.get("note") or src.get("desc") or ""
            out.append(f"- {src.get('url', '')}" + (f" — {desc}" if desc else ""))
        out.append("")
        out.append("Citation examples: `据 The Information 独家爆料，…` / `知情人士透露，…` / `泄露文件显示，…`")

    local_manual = [m for m in manual if m.get("path")]
    cite_manual = [m for m in manual if not m.get("path") and m.get("url")]
    if local_manual:
        out.append("\n## Local manual files (use SCREENSHOT, not HARVEST)\n")
        for m in local_manual:
            desc = m.get("desc", "")
            out.append(f"- `<!-- SCREENSHOT: {m['path']} caption=\"{desc}\" -->`")
    if cite_manual:
        out.append("\n## Other cite-only URLs\n")
        for m in cite_manual:
            out.append(f"- {m['url']}" + (f" — {m.get('desc','')}" if m.get('desc') else ""))

    if failed_sources:
        out.append("\n## ⚠️ Harvest failures (no images available)\n")
        for src in failed_sources:
            err = src.get("error", "unknown")
            out.append(f"- {src.get('url', '')} — {err}")

    total_imgs = sum(len(s.get("images") or []) for s in public_sources)
    covers = sum(1 for s in public_sources if s.get("cover"))
    out.append(f"\n---\n\nMenu summary: {len(public_sources)} public source(s), "
               f"{total_imgs} image(s), {covers} cover(s), "
               f"{len(gated_sources)} gated, {len(local_manual)} local, "
               f"{len(cite_manual)} cite-only.\n")
    return "\n".join(out)


# ─── Harvest：从源文章提取图片清单（直引远端 URL，不截图不下载）───────────────

# Style H (爆料自媒体) 依赖：新智元等公众号爆款的"图"其实都是直引源站，
# 不是自己去截。harvest 就是把这件事自动化——给一个源页面 URL，列出
# 页面里所有 <img> 的 src + alt + 上下文文字 + 顺序索引。
# 返回的 JSON 给 write skill 消费，最终生成 `![desc](远端 url)`。

HARVEST_IMG_MIN_WIDTH = 200   # 忽略小于此宽度的图（多半是图标/按钮）
HARVEST_IMG_MAX_COUNT = 80    # 单页最多收集的图数量


def harvest_images(source_url: str, wait: int = 2,
                   width: int = DEFAULT_VIEWPORT_WIDTH,
                   min_width: int = HARVEST_IMG_MIN_WIDTH,
                   use_fallback: bool = True) -> dict:
    """
    从源文章 URL 提取图片清单（直引远端 URL）。

    Playwright 优先（快、支持 JS 渲染）。如遇 CAPTCHA / 登录墙 /
    HTTP 错误，自动尝试 baoyu-fetch CLI 兜底（处理微信/X/HN 等）。

    Returns:
        {
          "source_url": ...,
          "title": ...,
          "captured_at": ISO8601,
          "method": "playwright" | "baoyu-fetch" | "none",
          "images": [
            {"idx": 0, "url": "...", "alt": "...", "context": "...",
             "width": 800, "height": 600}
          ],
          "warnings": [...],
          "error": "" (on failure)
        }
    """
    result = {
        "source_url": source_url,
        "title": "",
        "cover": "",
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "method": "none",
        "images": [],
        "warnings": [],
        "error": "",
    }

    # ── Step 1: Playwright 优先 ────────────────────────────────────────────
    print(f"  🌾 Harvesting images from: {source_url}")

    playwright_ok = False
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": width, "height": DEFAULT_VIEWPORT_HEIGHT},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                locale="zh-CN",
            )
            page = context.new_page()

            response = page.goto(source_url, timeout=SCREENSHOT_TIMEOUT_MS,
                                 wait_until="domcontentloaded")
            actual_status = response.status if response else 0

            if actual_status >= 400:
                result["warnings"].append(
                    f"Playwright got HTTP {actual_status}, will try baoyu-fetch fallback"
                )
            else:
                try:
                    page.wait_for_load_state("networkidle",
                                              timeout=NETWORK_IDLE_WAIT_MS + wait * 1000)
                except Exception:
                    pass
                if wait > 0:
                    page.wait_for_timeout(wait * 1000)

                # Lazy-load kick: many Style H sources (WeChat, Weibo) defer
                # <img src> until the element scrolls into view. Without this,
                # a 31-image 新智元 article returns only 6. Scroll the page
                # incrementally from top to bottom so every lazy <img> fires
                # its IntersectionObserver / manual-trigger loader.
                try:
                    page.evaluate("""async () => {
                        const step = Math.max(400, window.innerHeight);
                        for (let y = 0; y < document.body.scrollHeight; y += step) {
                            window.scrollTo(0, y);
                            await new Promise(r => setTimeout(r, 150));
                        }
                        window.scrollTo(0, document.body.scrollHeight);
                        await new Promise(r => setTimeout(r, 400));
                        window.scrollTo(0, 0);
                    }""")
                    # Let any final network requests settle
                    try:
                        page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:
                        pass
                except Exception:
                    pass

                result["title"] = page.title() or ""

                # 检 CAPTCHA / 登录墙
                page_text = (page.inner_text("body")[:800] if page.query_selector("body") else "")
                gate_markers = [
                    "环境异常", "完成验证", "去验证", "Log in", "Sign in",
                    "Just a moment", "cf-challenge", "verify you are human",
                    "需要登录", "微信公众平台", "Enable JavaScript",
                ]
                gated = any(m in page_text for m in gate_markers)

                if gated:
                    result["warnings"].append(
                        "Playwright 命中验证/登录墙，尝试 baoyu-fetch 兜底"
                    )
                else:
                    # og:image / twitter:image → source cover
                    cover = page.evaluate("""() => {
                        const sel = [
                            'meta[property="og:image"]',
                            'meta[name="og:image"]',
                            'meta[name="twitter:image"]',
                            'meta[property="twitter:image"]',
                        ];
                        for (const s of sel) {
                            const el = document.querySelector(s);
                            if (el && el.content) return el.content;
                        }
                        return '';
                    }""")
                    if cover:
                        result["cover"] = cover

                    # 取所有 <img>
                    raw_imgs = page.evaluate("""() => {
                        const imgs = Array.from(document.querySelectorAll('img'));
                        return imgs.map((img, idx) => {
                            const rect = img.getBoundingClientRect();
                            const parent = img.closest('figure, p, div') || img.parentElement;
                            const ctx = parent ? (parent.innerText || '').trim().slice(0, 200) : '';
                            return {
                                idx,
                                url: img.currentSrc || img.src || '',
                                alt: img.alt || '',
                                context: ctx,
                                width: Math.round(rect.width || img.naturalWidth || 0),
                                height: Math.round(rect.height || img.naturalHeight || 0),
                            };
                        });
                    }""")

                    filtered = _filter_harvest_images(raw_imgs, min_width)
                    result["images"] = filtered[:HARVEST_IMG_MAX_COUNT]
                    result["method"] = "playwright"
                    playwright_ok = True
                    print(f"     ✅ Playwright harvested {len(result['images'])} images"
                          + (f" (cover: yes)" if cover else ""))

            browser.close()
    except PlaywrightError as e:
        result["warnings"].append(f"Playwright error: {e}")
    except Exception as e:
        result["warnings"].append(f"Playwright unexpected error: {e}")

    if playwright_ok and result["images"]:
        return result

    # ── Step 2: baoyu-fetch 兜底（处理 CAPTCHA/微信/X/付费墙）─────────────
    if not use_fallback:
        result["error"] = result.get("error") or "Playwright 失败，且未启用 fallback"
        return result

    print(f"  🔄 Falling back to baoyu-fetch...")
    try:
        fb = _harvest_via_baoyu_fetch(source_url, min_width)
        if fb.get("images"):
            result["images"] = fb["images"][:HARVEST_IMG_MAX_COUNT]
            result["title"] = fb.get("title") or result["title"]
            result["cover"] = fb.get("cover") or result["cover"]
            result["method"] = "baoyu-fetch"
            result["warnings"].extend(fb.get("warnings", []))
            print(f"     ✅ baoyu-fetch harvested {len(result['images'])} images")
        else:
            result["error"] = fb.get("error") or "baoyu-fetch 未返回图片"
            result["warnings"].extend(fb.get("warnings", []))
    except Exception as e:
        result["error"] = f"baoyu-fetch error: {e}"

    return result


def _filter_harvest_images(raw_imgs: list, min_width: int) -> list:
    """按尺寸、URL 去重、过滤 data:/base64/小图标/0尺寸/非图片 URL。"""
    seen = set()
    out = []
    for img in raw_imgs or []:
        url = (img.get("url") or "").strip()
        if not url:
            continue
        if url.startswith("data:") or url.startswith("blob:"):
            continue
        if url in seen:
            continue
        w = int(img.get("width") or 0)
        h = int(img.get("height") or 0)
        # 0x0 尺寸：通常是隐藏的 share button <img> 或页面自指引用，不是真图
        if w == 0 and h == 0:
            continue
        # 小图标/emoji/头像：跳过
        if w and w < min_width:
            continue
        if w and h and (w < 100 or h < 100):
            continue
        seen.add(url)
        out.append({
            "idx": len(out),
            "url": url,
            "alt": (img.get("alt") or "").strip()[:200],
            "context": (img.get("context") or "").strip()[:200],
            "width": w,
            "height": h,
        })
    return out


def _harvest_via_baoyu_fetch(source_url: str, min_width: int) -> dict:
    """
    调 baoyu-fetch CLI 作为兜底。仅当 baoyu-fetch 可用时成功。
    返回同 harvest_images 的 images/title 子集。
    """
    import subprocess, shutil

    # 寻找 baoyu-fetch vendor 目录（按 CLAUDE_PLUGIN_ROOT 或已知缓存路径）
    candidates = []
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    if plugin_root:
        candidates.append(Path(plugin_root) / "scripts" / "vendor" / "baoyu-fetch" / "src" / "cli.ts")
    # 已知 baoyu-skills 缓存路径（skills 之间共享 bun vendor）
    home = Path.home()
    for p in home.glob(".claude/plugins/cache/baoyu-skills/*/skills/baoyu-url-to-markdown/scripts/vendor/baoyu-fetch/src/cli.ts"):
        candidates.append(p)

    cli_path = next((c for c in candidates if c.exists()), None)
    if not cli_path:
        return {
            "images": [],
            "error": "baoyu-fetch CLI 未安装",
            "warnings": ["install baoyu-skills plugin or vendor baoyu-fetch into scripts/vendor/"],
        }

    bun = shutil.which("bun")
    if not bun:
        return {
            "images": [],
            "error": "bun 未安装，无法运行 baoyu-fetch",
            "warnings": ["run: curl -fsSL https://bun.sh/install | bash"],
        }

    tmp_json = tempfile.mktemp(suffix=".json")
    try:
        proc = subprocess.run(
            [bun, str(cli_path), source_url, "--format", "json",
             "--output", tmp_json, "--wait-for", "interaction",
             "--interaction-timeout", "60000"],
            capture_output=True, text=True, timeout=180,
        )
        if proc.returncode != 0:
            return {
                "images": [],
                "error": f"baoyu-fetch exit {proc.returncode}",
                "warnings": [proc.stderr.strip()[:300]],
            }
        if not os.path.exists(tmp_json):
            return {"images": [], "error": "baoyu-fetch 未输出 JSON"}

        with open(tmp_json) as f:
            data = json.load(f)

        raw_imgs = []
        for m in (data.get("media") or []):
            if m.get("kind") != "image":
                continue
            raw_imgs.append({
                "url": m.get("url") or "",
                "alt": m.get("alt") or m.get("role") or "",
                "context": m.get("caption") or "",
                "width": m.get("width") or 0,
                "height": m.get("height") or 0,
            })

        # 兜底：从 markdown 里正则扒 ![alt](url)
        if not raw_imgs and data.get("markdown"):
            md = data["markdown"]
            for m in re.finditer(r"!\[([^\]]*)\]\((https?://[^)\s]+)\)", md):
                raw_imgs.append({
                    "url": m.group(2),
                    "alt": m.group(1),
                    "context": "",
                    "width": 0, "height": 0,
                })

        filtered = _filter_harvest_images(raw_imgs, min_width)
        doc = data.get("document", {}) or {}
        cover = doc.get("coverImage") or doc.get("featuredMedia") or ""
        # baoyu-fetch may put cover in media[] with role="cover"
        if not cover:
            for m in (data.get("media") or []):
                if m.get("role") == "cover" and m.get("url"):
                    cover = m["url"]
                    break
        return {
            "images": filtered,
            "title": doc.get("title", ""),
            "cover": cover,
            "warnings": [],
        }
    except subprocess.TimeoutExpired:
        return {"images": [], "error": "baoyu-fetch 超时"}
    finally:
        try:
            os.unlink(tmp_json)
        except Exception:
            pass


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

    # harvest 子命令（Style H 爆料型）
    hv = sub.add_parser("harvest",
                         help="从源文章提取图片清单（直引远端 URL，不截图）")
    hv.add_argument("url", help="源文章 URL")
    hv.add_argument("-o", "--output", default="",
                     help="输出 JSON 路径（默认 stdout）")
    hv.add_argument("-w", "--wait", type=int, default=2,
                     help="额外等待秒数")
    hv.add_argument("--min-width", type=int, default=HARVEST_IMG_MIN_WIDTH,
                     help=f"最小图片宽度（默认 {HARVEST_IMG_MIN_WIDTH}px）")
    hv.add_argument("--no-fallback", action="store_true",
                     help="禁用 baoyu-fetch 兜底")

    # rehost 子命令（带正确 Referer 重新下载并上传到自己 CDN）
    rh = sub.add_parser("rehost",
                         help="把带 hotlink 保护的远端图重新托管到我方 CDN")
    rh.add_argument("--url", required=True, help="远端图片 URL")
    rh.add_argument("--mode", default="auto",
                     choices=["auto", "always", "never"],
                     help="auto=仅白名单 CDN (默认), always=全部, never=跳过")

    # harvest-menu 子命令（从 _evidence.json 打印给 writer 的 cheat-sheet）
    hm = sub.add_parser("harvest-menu",
                         help="从 _evidence.json 生成 HARVEST 可选图菜单，喂给 write skill 避免猜 idx")
    hm.add_argument("--evidence", required=True, help="_evidence.json 绝对路径")
    hm.add_argument("--json", action="store_true",
                     help="输出结构化 JSON（默认 markdown 给人/Claude 看）")

    # expand-harvest 子命令（把 article.md 里的 HARVEST 占位符原地展开）
    eh = sub.add_parser("expand-harvest",
                         help="查 _evidence.json 展开 article.md 里的 HARVEST 占位符")
    eh.add_argument("--article", required=True, help="article.md 绝对路径")
    eh.add_argument("--evidence", default="",
                     help="_evidence.json 路径，默认取 article 同目录")
    eh.add_argument("--dry-run", action="store_true",
                     help="预览：不调用 rehost、不写 article.md，仅输出将发生的 trace")
    eh.add_argument("--strict", action="store_true",
                     help="严格模式：任何 placeholder 失败即退出 1，且不修改 article.md")

    args = parser.parse_args()

    if args.command == "check":
        status = check_url_status(args.url, timeout=args.timeout)
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return

    if args.command == "harvest":
        res = harvest_images(
            source_url=args.url,
            wait=args.wait,
            min_width=args.min_width,
            use_fallback=not args.no_fallback,
        )
        out_json = json.dumps(res, indent=2, ensure_ascii=False)
        if args.output:
            with open(args.output, "w") as f:
                f.write(out_json)
            print(f"\n  💾 Saved harvest → {args.output}")
            print(f"     method={res['method']}, images={len(res['images'])}")
            if res.get("error"):
                print(f"     ❌ error: {res['error']}")
            for w in res.get("warnings", []):
                print(f"     ⚠️  {w}")
        else:
            print(out_json)
        return

    if args.command == "rehost":
        # rehost calls upload_image(), which prints PicGo/S3 progress to stdout.
        # Redirect those prints to stderr so our final JSON is the *only* thing
        # on stdout — machine consumers can pipe to jq without filtering noise.
        import contextlib
        with contextlib.redirect_stdout(sys.stderr):
            res = rehost_image(args.url, mode=args.mode)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        sys.exit(0 if res["ok"] else 1)

    if args.command == "harvest-menu":
        res = harvest_menu(args.evidence, as_json=args.json)
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
            sys.exit(0 if res.get("ok") else 1)
        print(res)
        return

    if args.command == "expand-harvest":
        # Same rationale as rehost: expand_harvest calls rehost_image per
        # placeholder which prints upload progress. Keep stdout clean for JSON.
        import contextlib
        with contextlib.redirect_stdout(sys.stderr):
            res = expand_harvest(args.article, args.evidence or None,
                                  dry_run=args.dry_run, strict=args.strict)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        sys.exit(0 if res.get("ok") else 1)

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
