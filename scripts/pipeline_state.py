#!/usr/bin/env python3
"""
pipeline_state.py — cross-stage state for article-craft pipelines.

Single source of truth for which stages have run against a given article.
Written by the orchestrator at each stage boundary; read by --upgrade mode
to decide what to resume.

File: `.article-craft-state.json` next to article.md (co-located, survives
git mv with the article).

Invariant: the article.md content is ground truth. If state says
`images: completed` but the article still contains `<!-- IMAGE: -->`
placeholders, the stage is flagged as `stale_completion` and will be
re-run. The state file is advisory, not authoritative.

CLI:
  init         — create a fresh state file (or no-op if exists)
  start        — mark a stage running
  complete     — mark a stage completed, attach result payload
  fail         — mark a stage failed, attach error
  skip         — mark a stage skipped, attach reason
  show         — print full state as JSON
  missing-stages — compute what still needs to run for a given mode
  cleanup      — delete the state file (called by publish on success)
  reset        — same as cleanup, for manual "start over"

Exit codes: 0 on success, 1 on error, 2 on invalid usage.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1"
STATE_FILENAME = ".article-craft-state.json"

STAGE_STATUSES = {"pending", "running", "completed", "failed", "skipped"}

MODE_STAGES: dict[str, list[str]] = {
    "standard": [
        "requirements", "verify", "evidence",
        "write", "screenshot", "share_card", "images",
        "verify_claims", "review", "publish",
    ],
    "quick": [
        "requirements", "evidence",
        "write", "screenshot", "images",
    ],
    "draft": ["requirements", "evidence", "write"],
    "series": [
        "requirements", "verify", "evidence",
        "write", "screenshot", "share_card", "images",
        "verify_claims", "review", "publish",
    ],
}


def _pipeline_version() -> str:
    plugin_json = Path(__file__).resolve().parent.parent / ".claude-plugin" / "plugin.json"
    try:
        return json.loads(plugin_json.read_text(encoding="utf-8")).get("version", "unknown")
    except (OSError, json.JSONDecodeError):
        return "unknown"


def _atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".state.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class PipelineState:
    def __init__(self, article_path: str):
        self.article_path = Path(article_path).resolve()
        self.state_file = self.article_path.parent / STATE_FILENAME
        self._state = self._load()

    def _load(self) -> dict[str, Any]:
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                if data.get("schema_version") == SCHEMA_VERSION:
                    return data
                sys.stderr.write(
                    f"warning: state schema mismatch "
                    f"(file={data.get('schema_version')}, expected={SCHEMA_VERSION}) "
                    f"— ignoring stale state\n"
                )
            except (OSError, json.JSONDecodeError) as e:
                sys.stderr.write(f"warning: could not read state ({e}) — starting fresh\n")
        return self._blank()

    def _blank(self) -> dict[str, Any]:
        now = time.time()
        return {
            "schema_version": SCHEMA_VERSION,
            "pipeline_version": _pipeline_version(),
            "article_path": str(self.article_path),
            "mode": None,
            "writing_style": None,
            "created_at": now,
            "last_updated_at": now,
            "stages": {},
            "artifacts": {},
        }

    def save(self) -> None:
        self._state["last_updated_at"] = time.time()
        if str(self.article_path) != self._state.get("article_path"):
            self._state["article_path"] = str(self.article_path)
        _atomic_write(
            self.state_file,
            json.dumps(self._state, ensure_ascii=False, indent=2) + "\n",
        )

    def set_meta(self, mode: str | None, writing_style: str | None) -> None:
        if mode is not None:
            self._state["mode"] = mode
        if writing_style is not None:
            self._state["writing_style"] = writing_style

    def set_artifact(self, key: str, value: str) -> None:
        self._state["artifacts"][key] = value

    def start_stage(self, stage: str, meta: dict[str, Any] | None = None) -> None:
        self._state["stages"][stage] = {
            "status": "running",
            "started_at": time.time(),
            "completed_at": None,
            "result": meta or {},
        }

    def complete_stage(self, stage: str, result: dict[str, Any] | None = None) -> None:
        cur = self._state["stages"].get(stage, {"started_at": time.time()})
        cur.update({
            "status": "completed",
            "completed_at": time.time(),
            "result": result or {},
        })
        self._state["stages"][stage] = cur

    def fail_stage(self, stage: str, error: str, partial: dict[str, Any] | None = None) -> None:
        cur = self._state["stages"].get(stage, {"started_at": time.time()})
        payload = dict(partial or {})
        payload["error"] = error
        cur.update({
            "status": "failed",
            "completed_at": time.time(),
            "result": payload,
        })
        self._state["stages"][stage] = cur

    def skip_stage(self, stage: str, reason: str) -> None:
        self._state["stages"][stage] = {
            "status": "skipped",
            "started_at": time.time(),
            "completed_at": time.time(),
            "result": {"reason": reason},
        }

    def get_stage(self, stage: str) -> dict[str, Any] | None:
        return self._state["stages"].get(stage)

    def cleanup(self) -> None:
        if self.state_file.exists():
            self.state_file.unlink()

    @property
    def state(self) -> dict[str, Any]:
        return self._state


def _scan_article(article_path: Path) -> dict[str, Any]:
    if not article_path.exists():
        return {}
    text = article_path.read_text(encoding="utf-8", errors="replace")
    return {
        "image_placeholders": len(re.findall(r"<!--\s*IMAGE:", text)),
        "screenshot_placeholders": len(re.findall(r"<!--\s*SCREENSHOT:", text)),
        "harvest_placeholders": len(re.findall(r"<!--\s*HARVEST:", text)),
        "cdn_images": len(re.findall(r"!\[[^\]]*\]\(https?://[^)]*cdn", text)),
        "has_frontmatter": text.lstrip().startswith("---"),
        "in_kb": "/02-技术/" in str(article_path),
        # Style H signals: publish (v1.4.15+) copies these sidecars into the KB
        # alongside the article, so their presence lets --upgrade know Style H
        # even when no state file exists.
        "has_evidence": (article_path.parent / "_evidence.json").exists(),
        "has_harvest_menu": (article_path.parent / "_harvest_menu.md").exists(),
    }


def _stage_done_heuristic(stage: str, scan: dict[str, Any]) -> bool:
    """Infer whether a stage has been run by inspecting article content."""
    if stage == "requirements":
        return scan.get("has_frontmatter", False)
    if stage == "evidence":
        # Presence of _evidence.json sidecar (v1.4.15+ survives publish) means
        # evidence was run for this article.
        return scan.get("has_evidence", False)
    if stage == "write":
        return scan.get("has_frontmatter", False)
    if stage == "screenshot":
        return scan.get("screenshot_placeholders", 0) == 0 and scan.get("harvest_placeholders", 0) == 0
    if stage == "images":
        return scan.get("image_placeholders", 0) == 0 and scan.get("cdn_images", 0) > 0
    if stage == "publish":
        return scan.get("in_kb", False)
    return False


def _is_stale(stage: str, stage_state: dict[str, Any], scan: dict[str, Any]) -> bool:
    """State says completed, but article content contradicts."""
    if stage_state.get("status") != "completed":
        return False
    if stage == "screenshot":
        return scan.get("screenshot_placeholders", 0) > 0 or scan.get("harvest_placeholders", 0) > 0
    if stage == "images":
        return scan.get("image_placeholders", 0) > 0
    if stage == "publish":
        return not scan.get("in_kb", False)
    return False


def _compute_missing(state: PipelineState, mode: str) -> dict[str, Any]:
    pipeline_mode = mode if mode in MODE_STAGES else "standard"
    want = list(MODE_STAGES[pipeline_mode])
    writing_style = state.state.get("writing_style")
    scan = _scan_article(state.article_path)
    # Style H inference: if state doesn't know the style but sidecars exist on
    # disk (v1.4.15+ publish-preserved _evidence.json), treat as H so evidence
    # stage is retained in `want` instead of pruned.
    if writing_style is None and scan.get("has_evidence"):
        writing_style = "H"
    if writing_style != "H" and "evidence" in want:
        want.remove("evidence")
    stages = state.state.get("stages", {})
    have_any_state = bool(stages)

    missing, done, stale, skipped = [], [], [], []
    for stg in want:
        sstate = stages.get(stg)
        if sstate is None:
            if _stage_done_heuristic(stg, scan):
                done.append(stg)
            else:
                missing.append(stg)
            continue
        status = sstate.get("status")
        if status == "completed":
            if _is_stale(stg, sstate, scan):
                stale.append(stg)
                missing.append(stg)
            else:
                done.append(stg)
        elif status == "skipped":
            skipped.append(stg)
        else:
            missing.append(stg)

    source = "state_file" if have_any_state else "heuristic"
    if have_any_state and stale:
        source = "hybrid"

    return {
        "missing": missing,
        "done": done,
        "stale": stale,
        "skipped": skipped,
        "source": source,
        "mode": pipeline_mode,
        "writing_style": writing_style,
        "article_scan": scan,
    }


def cmd_init(args) -> int:
    ps = PipelineState(args.article)
    ps.set_meta(args.mode, args.writing_style)
    ps.save()
    print(ps.state_file)
    return 0


def cmd_start(args) -> int:
    ps = PipelineState(args.article)
    if args.mode or args.writing_style:
        ps.set_meta(args.mode, args.writing_style)
    meta = json.loads(args.meta) if args.meta else None
    ps.start_stage(args.stage, meta)
    ps.save()
    return 0


def cmd_complete(args) -> int:
    ps = PipelineState(args.article)
    if args.mode or args.writing_style:
        ps.set_meta(args.mode, args.writing_style)
    result = json.loads(args.result) if args.result else None
    ps.complete_stage(args.stage, result)
    ps.save()
    return 0


def cmd_fail(args) -> int:
    ps = PipelineState(args.article)
    partial = json.loads(args.partial) if args.partial else None
    ps.fail_stage(args.stage, args.error, partial)
    ps.save()
    return 0


def cmd_skip(args) -> int:
    ps = PipelineState(args.article)
    ps.skip_stage(args.stage, args.reason)
    ps.save()
    return 0


def cmd_show(args) -> int:
    ps = PipelineState(args.article)
    print(json.dumps(ps.state, ensure_ascii=False, indent=2))
    return 0


def cmd_missing(args) -> int:
    ps = PipelineState(args.article)
    out = _compute_missing(ps, args.mode or ps.state.get("mode") or "standard")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_cleanup(args) -> int:
    ps = PipelineState(args.article)
    ps.cleanup()
    return 0


def cmd_artifact(args) -> int:
    ps = PipelineState(args.article)
    ps.set_artifact(args.key, args.value)
    ps.save()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pipeline_state", description=__doc__.splitlines()[1])
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_article(sp):
        sp.add_argument("--article", required=True, help="absolute path to article.md")

    sp = sub.add_parser("init"); add_article(sp)
    sp.add_argument("--mode"); sp.add_argument("--writing-style", dest="writing_style")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("start"); add_article(sp)
    sp.add_argument("--stage", required=True)
    sp.add_argument("--mode"); sp.add_argument("--writing-style", dest="writing_style")
    sp.add_argument("--meta", help="JSON payload to attach")
    sp.set_defaults(func=cmd_start)

    sp = sub.add_parser("complete"); add_article(sp)
    sp.add_argument("--stage", required=True)
    sp.add_argument("--mode"); sp.add_argument("--writing-style", dest="writing_style")
    sp.add_argument("--result", help="JSON result payload")
    sp.set_defaults(func=cmd_complete)

    sp = sub.add_parser("fail"); add_article(sp)
    sp.add_argument("--stage", required=True)
    sp.add_argument("--error", required=True)
    sp.add_argument("--partial", help="JSON partial result (optional)")
    sp.set_defaults(func=cmd_fail)

    sp = sub.add_parser("skip"); add_article(sp)
    sp.add_argument("--stage", required=True)
    sp.add_argument("--reason", required=True)
    sp.set_defaults(func=cmd_skip)

    sp = sub.add_parser("show"); add_article(sp); sp.set_defaults(func=cmd_show)

    sp = sub.add_parser("missing-stages"); add_article(sp)
    sp.add_argument("--mode", help="override mode (defaults to state's mode)")
    sp.set_defaults(func=cmd_missing)

    sp = sub.add_parser("cleanup"); add_article(sp); sp.set_defaults(func=cmd_cleanup)
    sp = sub.add_parser("reset"); add_article(sp); sp.set_defaults(func=cmd_cleanup)

    sp = sub.add_parser("artifact"); add_article(sp)
    sp.add_argument("--key", required=True); sp.add_argument("--value", required=True)
    sp.set_defaults(func=cmd_artifact)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if hasattr(args, "stage") and args.stage and hasattr(args, "cmd"):
            if args.cmd in ("start", "complete", "fail", "skip") and args.stage not in {
                "requirements", "verify", "evidence", "write", "screenshot",
                "share_card", "images", "verify_claims", "review", "publish",
            }:
                sys.stderr.write(f"error: unknown stage '{args.stage}'\n")
                return 2
        return args.func(args)
    except (OSError, json.JSONDecodeError) as e:
        sys.stderr.write(f"error: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
