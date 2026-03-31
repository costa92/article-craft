#!/usr/bin/env python3
"""
将 verify skill 的 URL 验证结果写入共享缓存。

Usage:
    # 单个 URL
    python3 write_verify_cache.py --url https://example.com --status 200 --reason "Direct access"

    # 批量（JSONL 格式）
    python3 write_verify_cache.py --batch

    # 从文件读取结果
    python3 write_verify_cache.py --from-file /tmp/verify-results.txt
"""

import argparse
import json
import os
import sys
import time
import re
from pathlib import Path

CACHE_FILE = os.environ.get(
    "VERIFY_CACHE_FILE",
    os.path.join(os.path.expanduser("~"), ".cache", "article-craft", "verify-cache.json")
)
CACHE_TTL = 3600  # 1 hour


def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_cache(cache: dict) -> None:
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️  Cache write failed: {e}", file=sys.stderr)


def parse_curl_output(text: str) -> list:
    """从 curl 输出解析 URL 验证结果"""
    results = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        # 格式: "FAIL 404 https://..." 或 "200 https://..." 或 "FAIL CODE https://..."
        m = re.match(r"(?:FAIL\s+)?(\d{3}|CODE)\s+(https?://\S+)", line)
        if m:
            code = m.group(1)
            url = m.group(2)
            status = int(code) if code.isdigit() else None
            results.append({"url": url, "status_code": status})
    return results


def write_result(url: str, status_code: int = None, reason: str = "",
                 is_valid: bool = None, final_url: str = None) -> None:
    """写入单个 URL 的验证结果"""
    cache = load_cache()
    entry = {
        "url": url,
        "status_code": status_code,
        "final_url": final_url or url,
        "is_valid": is_valid if is_valid is not None else (status_code == 200),
        "is_404": status_code == 404,
        "is_403": status_code == 403,
        "is_5xx": status_code and status_code >= 500,
        "reason": reason or (f"HTTP {status_code}" if status_code else "unknown"),
        "redirect_chain": [],
        "_checked_at": time.time(),
    }
    cache[url] = entry
    save_cache(cache)


def write_batch(urls: list) -> None:
    """批量写入 URL 结果"""
    cache = load_cache()
    for item in urls:
        if isinstance(item, str):
            url = item
            status_code, reason = None, "unknown"
        else:
            url = item.get("url", "")
            status_code = item.get("status_code")
            reason = item.get("reason", "")
        if not url:
            continue
        cache[url] = {
            "url": url,
            "status_code": status_code,
            "final_url": url,
            "is_valid": status_code == 200,
            "is_404": status_code == 404,
            "is_403": status_code == 403,
            "is_5xx": status_code and status_code >= 500,
            "reason": reason,
            "redirect_chain": [],
            "_checked_at": time.time(),
        }
    save_cache(cache)


def main():
    parser = argparse.ArgumentParser(description="Write verify URL results to shared cache")
    parser.add_argument("--url", help="URL to cache")
    parser.add_argument("--status", type=int, help="HTTP status code")
    parser.add_argument("--reason", default="", help="Reason string")
    parser.add_argument("--valid", action="store_true", help="Mark as valid (200)")
    parser.add_argument("--invalid", action="store_true", help="Mark as invalid (not 200)")
    parser.add_argument("--batch", action="store_true", help="Read JSON lines from stdin")
    parser.add_argument("--from-file", help="Read curl output from file")
    args = parser.parse_args()

    if args.batch:
        # 从 stdin 读取 JSONL
        items = []
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        write_batch(items)
        print(f"✅ Wrote {len(items)} URL results to cache")
        return

    if args.from_file:
        with open(args.from_file) as f:
            content = f.read()
        items = parse_curl_output(content)
        write_batch(items)
        print(f"✅ Parsed and wrote {len(items)} URL results to cache")
        return

    if args.url:
        is_valid = True
        if args.invalid:
            is_valid = False
        elif args.status:
            is_valid = args.status == 200
        write_result(args.url, args.status, args.reason, is_valid)
        print(f"✅ Cached: {args.url} -> {args.status or '?'}")
        return

    # No args: read from previous curl output saved by verify skill
    tmp_file = "/tmp/article-craft-verify-tmp.txt"
    if os.path.exists(tmp_file):
        with open(tmp_file) as f:
            content = f.read()
        items = parse_curl_output(content)
        write_batch(items)
        print(f"✅ Wrote {len(items)} results from {tmp_file}")
    else:
        print("No input provided. Use --url, --batch, or --from-file.")


if __name__ == "__main__":
    main()
