#!/usr/bin/env python3
"""Minimal series state manager for article-craft."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SeriesArticle:
    index: int
    title: str
    summary: str
    status: str
    path: str


def _payload(ok: bool, message: str, details: dict[str, Any], error_code: str | None = None) -> dict[str, Any]:
    payload = {"ok": ok, "message": message, "details": details}
    if error_code is not None:
        payload["error_code"] = error_code
    return payload


def _print_payload(ok: bool, message: str, details: dict[str, Any], error_code: str | None = None) -> None:
    print(json.dumps(_payload(ok, message, details, error_code), ensure_ascii=False, indent=2))


def _parse_frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return {}
    fm: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"')
    return fm


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "_", title).strip("_").lower()
    return slug[:40] or "article"


def _parse_series_file(series_file: Path) -> dict[str, Any]:
    text = series_file.read_text(encoding="utf-8")
    fm = _parse_frontmatter(text)
    articles: list[SeriesArticle] = []
    in_table = False
    for line in text.splitlines():
        if line.startswith("| # |"):
            in_table = True
            continue
        if in_table:
            if not line.startswith("|"):
                break
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) >= 5 and parts[0].isdigit():
                articles.append(
                    SeriesArticle(
                        index=int(parts[0]),
                        title=parts[1],
                        summary=parts[2],
                        status=parts[3],
                        path=parts[4],
                    )
                )
    return {"frontmatter": fm, "articles": articles, "path": series_file}


def _validate_series(series: dict[str, Any]) -> tuple[bool, str | None, str]:
    if not series["articles"]:
        return False, "series_table_missing", "series article table missing"
    return True, None, "series file is valid"


def _planned_articles(series: dict[str, Any]) -> list[SeriesArticle]:
    return [a for a in series["articles"] if "planned" in a.status]


def _published_count(series: dict[str, Any]) -> int:
    return sum(1 for a in series["articles"] if "published" in a.status)


def _next_planned(series: dict[str, Any]) -> SeriesArticle | None:
    planned = _planned_articles(series)
    return planned[0] if planned else None


def _article_filename(index: int, title: str) -> str:
    return f"{index:02d}_{_slugify(title)}.md"


def _update_series_status(series_file: Path, index: int, path: str) -> bool:
    """Mark the row whose ``#`` column equals ``index`` as published.

    Returns ``True`` if a matching row was found and rewritten, ``False``
    otherwise. When no row matches, the file is left untouched — the caller
    must surface the miss rather than reporting a silent success.
    """
    text = series_file.read_text(encoding="utf-8")
    lines = text.splitlines()
    matched = False
    for i, line in enumerate(lines):
        if re.match(rf"^\|\s*{index}\s*\|", line):
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) >= 5:
                parts[3] = "✅ published"
                parts[4] = path
                lines[i] = "| " + " | ".join(parts) + " |"
                matched = True
            break
    if matched:
        series_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return matched


def cmd_status(args) -> int:
    series_file = Path(args.series)
    if not series_file.exists():
        _print_payload(False, "series file not found", {"series": str(series_file)}, error_code="series_not_found")
        return 1
    series = _parse_series_file(series_file)
    next_article = _next_planned(series)
    articles = series["articles"]
    total = len(articles)
    done = _published_count(series)
    details = {
        "series_file": str(series_file.resolve()),
        "series_name": series["frontmatter"].get("series_name", series_file.stem),
        "progress": {"done": done, "total": total},
        "next": None,
        "articles": [a.__dict__ for a in articles],
    }
    if next_article:
        details["next"] = next_article.__dict__
    _print_payload(True, "series status ready", details)
    return 0


def cmd_next(args) -> int:
    series_file = Path(args.series)
    if not series_file.exists():
        _print_payload(False, "series file not found", {"series": str(series_file)}, error_code="series_not_found")
        return 1
    series = _parse_series_file(series_file)
    next_article = _next_planned(series)
    if not next_article:
        _print_payload(False, "no planned articles remain", {"series_file": str(series_file.resolve())}, error_code="series_complete")
        return 1

    series_dir = series_file.parent
    article_path = series_dir / _article_filename(next_article.index, next_article.title)
    total = len(series["articles"])
    prev_article = series["articles"][next_article.index - 2] if next_article.index > 1 and len(series["articles"]) >= next_article.index - 1 else None
    next_next = series["articles"][next_article.index] if len(series["articles"]) > next_article.index else None
    details = {
        "series_file": str(series_file.resolve()),
        "article": {
            "index": next_article.index,
            "title": next_article.title,
            "summary": next_article.summary,
            "save_path": str(article_path.resolve()),
            "series_order": next_article.index,
            "series_total": total,
            "prev_title": prev_article.title if prev_article else None,
            "next_title": next_next.title if next_next else None,
        },
    }
    _print_payload(True, "next article ready", details)
    return 0


def cmd_mark_published(args) -> int:
    series_file = Path(args.series)
    if not series_file.exists():
        _print_payload(False, "series file not found", {"series": str(series_file)}, error_code="series_not_found")
        return 1
    index = int(args.index)
    matched = _update_series_status(series_file, index, args.path)
    if not matched:
        _print_payload(
            False,
            f"no series row found with index {index}",
            {"series_file": str(series_file.resolve()), "index": index},
            error_code="series_row_not_found",
        )
        return 1
    _print_payload(
        True,
        "series updated",
        {"series_file": str(series_file.resolve()), "index": index, "path": args.path, "matched": True},
    )
    return 0


def cmd_validate(args) -> int:
    series_file = Path(args.series)
    if not series_file.exists():
        _print_payload(False, "series file not found", {"series": str(series_file)}, error_code="series_not_found")
        return 1
    series = _parse_series_file(series_file)
    ok, error_code, message = _validate_series(series)
    if ok:
        _print_payload(True, message, {"series_file": str(series_file.resolve()), "article_count": len(series["articles"])})
        return 0
    _print_payload(False, message, {"series_file": str(series_file.resolve())}, error_code=error_code)
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="series_state", description="series state manager")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("status", help="show series progress")
    sp.add_argument("--series", required=True)
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("next", help="get next planned article")
    sp.add_argument("--series", required=True)
    sp.set_defaults(func=cmd_next)

    sp = sub.add_parser("mark-published", help="mark article as published")
    sp.add_argument("--series", required=True)
    sp.add_argument("--index", required=True)
    sp.add_argument("--path", required=True)
    sp.set_defaults(func=cmd_mark_published)

    sp = sub.add_parser("validate", help="validate series file")
    sp.add_argument("--series", required=True)
    sp.set_defaults(func=cmd_validate)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
