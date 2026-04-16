#!/usr/bin/env python3
"""
Article-Craft Evidence Collector (Style H — 爆料自媒体)

读取用户提供的 materials.md，批量跑 screenshot_tool.py harvest，
合并为 _evidence.json，供 write skill 在 Style H 模式下消费。

用法:
    python3 evidence.py collect materials.md -o _evidence.json
    python3 evidence.py collect materials.md -o _evidence.json --keywords AI Claude

materials.md 格式（简易）:
    # Evidence Materials

    ## 公开源（auto-harvest）
    - https://mp.weixin.qq.com/s/xxx  tier=T3 note="新智元爆料"
    - https://x.com/anthropic/status/123  tier=T0
    - https://claude.com/blog/foo  tier=T0

    ## 本地截图（manual）
    - /abs/path/leaked-code.png  desc="泄露的 .map 文件 KAIROS 段"
    - /abs/path/stock-chart.png  desc="Adobe 股价跌 2%"

    ## 登录墙说明（manual）
    - https://www.theinformation.com/xxx  desc="The Information 独家爆料，引用原文 3 段"

输出 _evidence.json 结构:
{
  "materials_path": "/abs/path/materials.md",
  "collected_at": ISO8601,
  "sources": [
    {
      "url": "https://...",
      "tier": "T0" | "T1" | ... | "T5",
      "note": "...",
      "title": "...",
      "method": "playwright" | "baoyu-fetch",
      "cover": "url or ''",            # og:image / twitter:image / coverImage
      "images": [{ "idx", "url", "alt", "context", "width", "height" }, ...]
    }
  ],
  "manual": [
    { "path": "/abs/path/img.png", "desc": "..." },
    { "url": "https://paywalled", "desc": "..." }
  ],
  "summary": {
    "public_count": N,
    "manual_count": M,
    "total_images": K,
    "failed": [ { "url": "...", "error": "..." } ]
  }
}
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
SCREENSHOT_TOOL = SCRIPT_DIR / "screenshot_tool.py"


# ─── materials.md 解析 ──────────────────────────────────────────────────────

TIER_RE = re.compile(r"tier\s*=\s*(T[0-5])", re.IGNORECASE)
NOTE_RE = re.compile(r'note\s*=\s*"([^"]*)"')
DESC_RE = re.compile(r'desc\s*=\s*"([^"]*)"')
URL_RE = re.compile(r"https?://[^\s)\"'<>]+")


def parse_materials(path: str) -> dict:
    """
    解析 materials.md，分拣为三类：
      public  — 带 URL、需要 auto-harvest
      local   — 本地绝对路径（图片）
      gated   — 带 URL 但登录墙/付费墙（只记录引用，不 harvest）
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"materials.md not found: {path}")

    with open(path) as f:
        text = f.read()

    sections = _split_sections(text)

    public, local, gated = [], [], []

    for section_name, lines in sections.items():
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            # 支持 "- xxx" 或 "* xxx" 或纯 URL/path
            line = re.sub(r"^[-*]\s*", "", line)

            url_match = URL_RE.search(line)
            tier_match = TIER_RE.search(line)
            note_match = NOTE_RE.search(line)
            desc_match = DESC_RE.search(line)

            if section_name == "local":
                # 本地路径
                path_token = re.split(r"\s+(?:desc=|$)", line)[0].strip()
                if os.path.isabs(path_token):
                    local.append({
                        "path": path_token,
                        "desc": desc_match.group(1) if desc_match else "",
                    })
                continue

            if url_match:
                url = url_match.group(0).rstrip(".,;")
                entry = {
                    "url": url,
                    "tier": (tier_match.group(1).upper() if tier_match else "T5"),
                    "note": note_match.group(1) if note_match else "",
                    "desc": desc_match.group(1) if desc_match else "",
                }
                if section_name == "gated":
                    gated.append(entry)
                else:
                    public.append(entry)

    return {"public": public, "local": local, "gated": gated}


def _split_sections(text: str) -> dict:
    """
    粗略识别 ## 小节，按中文/英文关键词归类：
      "公开" / "auto" / "harvest" → public
      "本地" / "manual" / "screenshot" / "截图" → local
      "登录" / "付费" / "gated" / "paywall" → gated
    未识别的小节归入 public（按 URL 与否再分拣）
    """
    sections = {"public": [], "local": [], "gated": []}
    current = "public"
    for line in text.splitlines():
        if line.startswith("## "):
            header = line[3:].strip().lower()
            if any(k in header for k in ("本地", "manual", "截图", "screenshot", "local")):
                current = "local"
            elif any(k in header for k in ("登录", "付费", "gated", "paywall", "墙")):
                current = "gated"
            else:
                current = "public"
            continue
        sections[current].append(line)
    return sections


# ─── 批量 harvest ────────────────────────────────────────────────────────────

def harvest_public_sources(public: list, wait: int = 2,
                            min_width: int = 200) -> list:
    """对每条公开 URL 跑 screenshot_tool.py harvest，返回 sources 清单。"""
    import subprocess

    results = []
    for i, item in enumerate(public):
        url = item["url"]
        print(f"\n  [{i+1}/{len(public)}] Harvesting: {url}")
        try:
            proc = subprocess.run(
                [sys.executable, str(SCREENSHOT_TOOL), "harvest", url,
                 "-w", str(wait), "--min-width", str(min_width)],
                capture_output=True, text=True, timeout=240,
            )
            if proc.returncode != 0:
                results.append({
                    **item,
                    "title": "",
                    "method": "failed",
                    "images": [],
                    "error": f"exit {proc.returncode}: {proc.stderr[:200]}",
                })
                continue

            # 从 stdout 里抓 JSON（harvest 默认输出 JSON 到 stdout）
            stdout = proc.stdout.strip()
            # stdout 可能混了 print 进度行，取最后一个 {...} 块
            json_start = stdout.find("{")
            if json_start == -1:
                results.append({
                    **item, "title": "", "method": "failed",
                    "images": [], "error": "no JSON in stdout",
                })
                continue
            try:
                data = json.loads(stdout[json_start:])
            except json.JSONDecodeError:
                # 回退：抓最后一个顶层 JSON 对象
                data = _extract_last_json(stdout)
                if not data:
                    results.append({
                        **item, "title": "", "method": "failed",
                        "images": [], "error": "malformed JSON",
                    })
                    continue

            results.append({
                **item,
                "title": data.get("title", ""),
                "cover": data.get("cover", ""),
                "method": data.get("method", "unknown"),
                "images": data.get("images", []),
                "warnings": data.get("warnings", []),
                "error": data.get("error", ""),
            })
        except subprocess.TimeoutExpired:
            results.append({
                **item, "title": "", "method": "failed",
                "images": [], "error": "harvest timeout (240s)",
            })
        except Exception as e:
            results.append({
                **item, "title": "", "method": "failed",
                "images": [], "error": f"{type(e).__name__}: {e}",
            })
    return results


def _extract_last_json(text: str):
    """暴力从文本尾部反向找最大的 {...} JSON 对象。"""
    depth = 0
    end = -1
    for i in range(len(text) - 1, -1, -1):
        c = text[i]
        if c == "}":
            if depth == 0:
                end = i
            depth += 1
        elif c == "{":
            depth -= 1
            if depth == 0 and end != -1:
                try:
                    return json.loads(text[i:end + 1])
                except json.JSONDecodeError:
                    continue
    return None


# ─── 主流程 ──────────────────────────────────────────────────────────────────

def collect(materials_path: str, output_path: str,
            wait: int = 2, min_width: int = 200) -> dict:
    parsed = parse_materials(materials_path)

    print(f"\n📋 Materials breakdown:")
    print(f"   public (auto-harvest): {len(parsed['public'])}")
    print(f"   local  (manual paths): {len(parsed['local'])}")
    print(f"   gated  (cite-only):    {len(parsed['gated'])}")

    # 本地路径校验
    for item in parsed["local"]:
        if not os.path.exists(item["path"]):
            print(f"   ⚠️  local path missing: {item['path']}")

    # 批量 harvest 公开源
    sources = harvest_public_sources(parsed["public"], wait, min_width)

    # 登录墙源只记录引用，不 harvest
    for g in parsed["gated"]:
        sources.append({
            **g,
            "title": "",
            "method": "gated",
            "images": [],
            "error": "",
        })

    failed = [{"url": s["url"], "error": s["error"]}
              for s in sources if s.get("error")]
    total_images = sum(len(s.get("images", [])) for s in sources)

    evidence = {
        "materials_path": os.path.abspath(materials_path),
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sources": sources,
        "manual": parsed["local"],
        "summary": {
            "public_count": len(parsed["public"]),
            "manual_count": len(parsed["local"]),
            "gated_count": len(parsed["gated"]),
            "total_images": total_images,
            "failed": failed,
        },
    }

    with open(output_path, "w") as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Evidence saved: {output_path}")
    print(f"   sources harvested: {len(sources)}")
    print(f"   images collected:  {total_images}")
    print(f"   manual refs:       {len(parsed['local'])}")
    if failed:
        print(f"   ❌ failed: {len(failed)}")
        for f_entry in failed:
            print(f"      {f_entry['url']} — {f_entry['error'][:80]}")

    return evidence


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Article-Craft Evidence Collector (Style H)"
    )
    sub = parser.add_subparsers(dest="command")

    cl = sub.add_parser("collect", help="解析 materials.md 并批量 harvest")
    cl.add_argument("materials", help="materials.md 路径")
    cl.add_argument("-o", "--output", default="_evidence.json",
                     help="输出 JSON 路径（默认 _evidence.json）")
    cl.add_argument("-w", "--wait", type=int, default=2,
                     help="每个源的额外等待秒数")
    cl.add_argument("--min-width", type=int, default=200,
                     help="最小图片宽度（默认 200px）")

    pr = sub.add_parser("parse", help="只解析 materials.md，不 harvest")
    pr.add_argument("materials", help="materials.md 路径")

    args = parser.parse_args()

    if args.command == "parse":
        parsed = parse_materials(args.materials)
        print(json.dumps(parsed, ensure_ascii=False, indent=2))
        return

    if args.command == "collect":
        collect(args.materials, args.output, args.wait, args.min_width)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
