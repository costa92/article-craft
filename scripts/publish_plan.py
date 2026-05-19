#!/usr/bin/env python3
"""Plan and apply article publish moves."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import config
from utils import SmartDirectoryMatcher


SIDECAR_FILES = ("_evidence.json", "_harvest_menu.md")


def _payload(ok: bool, message: str, details: dict[str, Any], error_code: str | None = None) -> dict[str, Any]:
    payload = {
        "ok": ok,
        "message": message,
        "details": details,
    }
    if error_code is not None:
        payload["error_code"] = error_code
    return payload


def _print_payload(ok: bool, message: str, details: dict[str, Any], error_code: str | None = None) -> None:
    print(json.dumps(_payload(ok, message, details, error_code), ensure_ascii=False, indent=2))


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _timestamped_name(path: Path) -> Path:
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return path.with_name(f"{path.stem}_{stamp}{path.suffix}")


def _detect_collision(target_file: Path, source_file: Path) -> tuple[Path, dict[str, Any]]:
    if not target_file.exists():
        return target_file, {"status": "none"}

    if _file_sha256(target_file) == _file_sha256(source_file):
        return target_file, {"status": "identical"}

    renamed = _timestamped_name(target_file)
    return renamed, {
        "status": "rename",
        "existing": str(target_file.resolve()),
        "renamed_to": str(renamed.resolve()),
    }


def _collect_sidecars(article: Path) -> list[str]:
    found = []
    for sidecar in SIDECAR_FILES:
        if (article.parent / sidecar).exists():
            found.append(sidecar)
    return found


def _extract_title(article: Path) -> str:
    text = article.read_text(encoding="utf-8", errors="replace")
    if text.startswith("---"):
        lines = text.splitlines()
        for line in lines[1:]:
            if line.strip() == "---":
                break
            if line.lower().startswith("title:"):
                return line.split(":", 1)[1].strip().strip('"')
    return article.stem


def _resolve_auto_output_dir(article: Path, kb_root: Path) -> tuple[Path, dict[str, Any]]:
    matcher = SmartDirectoryMatcher(str(kb_root))
    title = _extract_title(article)
    matched = matcher.match_directory(title)
    if matched:
        target_dir = kb_root / matched
        return target_dir, {"strategy": "matcher", "title": title, "matched_dir": matched}

    category_root = config.kb_category_root()
    candidates = sorted(
        [p for p in (kb_root / category_root).rglob("*") if p.is_dir()],
        key=lambda p: len(p.parts),
        reverse=True,
    )
    if candidates:
        target_dir = candidates[0]
        return target_dir, {
            "strategy": "directory_fallback",
            "title": title,
            "matched_dir": str(target_dir.relative_to(kb_root)),
        }

    uncategorized = config.kb_uncategorized_dir()
    fallback = kb_root / category_root / uncategorized
    return fallback, {
        "strategy": "fallback",
        "title": title,
        "matched_dir": f"{category_root}/{uncategorized}",
    }


def build_publish_plan(article: Path, output_dir: Path, mode: str = "explicit_output", auto_meta: dict[str, Any] | None = None) -> dict[str, Any]:
    article = article.resolve()
    output_dir = output_dir.resolve()

    target_file, collision = _detect_collision(output_dir / article.name, article)
    sidecars = _collect_sidecars(article)

    return {
        "article": str(article),
        "mode": mode,
        "source_dir": str(article.parent.resolve()),
        "target_dir": str(output_dir),
        "target_file": str(target_file.resolve()),
        "collision": collision,
        "sidecars": sidecars,
        "auto_meta": auto_meta or {},
    }


def apply_publish_plan(plan: dict[str, Any]) -> dict[str, Any]:
    target_dir = Path(plan["target_dir"])
    source_article = Path(plan["article"])
    target_file = Path(plan["target_file"])

    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_article, target_file)

    copied_sidecars = []
    for sidecar in plan.get("sidecars", []):
        src = source_article.parent / sidecar
        dst = target_dir / sidecar
        shutil.copy2(src, dst)
        copied_sidecars.append(sidecar)

    applied = dict(plan)
    applied["copied_sidecars"] = copied_sidecars
    return applied


def _resolve_plan(args) -> tuple[dict[str, Any] | None, int]:
    """Build a publish plan from args.

    Returns ``(plan, exit_code)``. ``plan`` is ``None`` when validation
    failed — the error payload has already been printed and ``exit_code``
    is non-zero. This function performs **no filesystem mutation**:
    directory creation is deferred to ``apply_publish_plan()`` so that a
    ``--dry-run`` invocation leaves the disk untouched.
    """
    article = Path(args.article)
    if not article.exists():
        _print_payload(False, "article not found", {"article": str(article)}, error_code="article_not_found")
        return None, 1

    if args.output_dir:
        output_dir = Path(args.output_dir)
        if not output_dir.exists() or not output_dir.is_dir():
            _print_payload(False, "output directory not found", {"output_dir": str(output_dir)}, error_code="output_dir_not_found")
            return None, 1
        return build_publish_plan(article, output_dir), 0

    kb_root = Path(args.kb_root) if args.kb_root else article.parent
    target_dir, auto_meta = _resolve_auto_output_dir(article, kb_root)
    return build_publish_plan(article, target_dir, mode="auto", auto_meta=auto_meta), 0


def cmd_run(args) -> int:
    plan, code = _resolve_plan(args)
    if plan is None:
        return code

    if args.dry_run:
        _print_payload(True, "publish plan ready (dry run)", plan)
        return 0

    applied = apply_publish_plan(plan)
    _print_payload(True, "publish apply complete", applied)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="publish_plan",
        description="plan and apply an article publish move",
    )
    parser.add_argument("--article", required=True, help="absolute path to article.md")
    parser.add_argument("--output-dir", help="explicit target directory (skips KB auto-detection)")
    parser.add_argument("--kb-root", help="knowledge base root for auto-placement")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the publish plan without creating directories or copying files",
    )
    parser.set_defaults(func=cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
